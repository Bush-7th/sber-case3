"""Strict JSON, source verification and deterministic raw-value normalization."""

import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import UUID

from pydantic import ValidationError

from app.modules.recognition.facts import (
    EvidenceRef,
    ExpenseItem,
    FieldDataType,
    FieldObservation,
    SubjectRole,
)
from app.modules.recognition.model import (
    ExtractedValue,
    ExtractionPayload,
    ModelFailure,
    ModelRequest,
    Quote,
    RecognizedFragment,
)


def strict_json(text: str):
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Nonfinite JSON value")

    return json.loads(text, object_pairs_hook=object_pairs, parse_constant=invalid_constant)


def folded(text: str) -> str:
    return " ".join(text.split())


def verify_quote(quote: Quote, request: ModelRequest, source_ids: list[str]) -> EvidenceRef:
    source = next((s for s in request.sources if s.id == quote.source_id), None)
    if source is None or source.id not in source_ids:
        raise ValueError("Unknown source")
    if not folded(quote.excerpt) or folded(quote.excerpt) not in folded(source.text):
        raise ValueError("Unverifiable quotation")
    return EvidenceRef(
        location=source.location.model_copy(deep=True),
        excerpt=quote.excerpt,
        extraction_method=source.extraction_method,
        ocr_result_id=source.ocr_result_id,
    )


def value_evidence(
    value: ExtractedValue, request: ModelRequest, source_ids: list[str]
) -> list[EvidenceRef]:
    refs = [verify_quote(q, request, source_ids) for q in value.evidence]
    if not folded(value.raw) or not all(
        folded(value.raw) in folded(q.excerpt) for q in value.evidence
    ):
        raise ValueError("Extracted string must occur in its source quotation")
    return refs


MONEY = {
    "requested_amount",
    "total_expenses",
    "own_funds",
    "requested_subsidy_amount",
    "balance",
    "amount",
}
DATES = {"date", "issue_date", "expiration_date"}


def decimal_string(raw: str) -> str:
    text = raw.strip()
    # Only unambiguous Russian/ISO numeric notation. No inferred multipliers or currency units.
    if not re.fullmatch(
        r"-?(?:[0-9]+|[0-9]{1,3}(?:[ \u00a0\u202f][0-9]{3})+)(?:[.,][0-9]+)?", text
    ):
        raise ValueError("Unrecognized number")
    text = re.sub(r"[ \u00a0\u202f]", "", text).replace(",", ".")
    result = Decimal(text)
    if not result.is_finite():
        raise ValueError("Nonfinite number")
    return format(result, "f")  # Never passes through binary float or performs rule arithmetic.


def normalized(raw: str, data_type: FieldDataType) -> str:
    if data_type in {FieldDataType.money, FieldDataType.decimal}:
        return decimal_string(raw)
    if data_type == FieldDataType.date:
        text = raw.strip()
        if re.fullmatch(r"[0-9]{2}\.[0-9]{2}\.[0-9]{4}", text):
            day, month, year = text.split(".")
            return date(int(year), int(month), int(day)).isoformat()
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
            raise ValueError("Unrecognized date")
        return date.fromisoformat(text).isoformat()
    return raw.strip()


def role_for(field_id: str, document_type: str) -> SubjectRole:
    if field_id == "applicant_inn":
        return SubjectRole.applicant
    if document_type == "guarantee_letter":
        return SubjectRole.guarantor
    if document_type == "consent":
        return SubjectRole.person
    return SubjectRole.applicant


def field_observation(field_id, value, fragment, request):
    data_type = (
        FieldDataType.money
        if field_id in MONEY
        else FieldDataType.date
        if field_id in DATES
        else FieldDataType.decimal
        if field_id == "area"
        else FieldDataType.expense_items
        if field_id == "expense_items"
        else FieldDataType.text
    )
    role = role_for(field_id, fragment.document_type)
    if value is None:
        return FieldObservation(
            field_id=field_id,
            data_type=data_type,
            raw=None,
            normalized=None,
            known_state="missing",
            subject_role=role,
        )
    if field_id == "expense_items":
        items, evidence = [], []
        unreadable = False
        for item in value:
            refs = value_evidence(item.description, request, fragment.source_ids)
            amount = None
            if item.amount:
                refs += value_evidence(item.amount, request, fragment.source_ids)
                try:
                    amount = decimal_string(item.amount.raw)
                except (ValueError, InvalidOperation):
                    unreadable = True
            evidence += refs
            items.append(
                ExpenseItem(description=item.description.raw, amount=amount, evidence=refs)
            )
        # An empty list cannot claim a known field without source evidence.
        return FieldObservation(
            field_id=field_id,
            data_type=data_type,
            raw=None,
            normalized=items if items and not unreadable else None,
            known_state="known" if items and not unreadable else "unreadable",
            evidence=evidence,
            subject_role=role,
        )
    evidence = value_evidence(value, request, fragment.source_ids)
    try:
        parsed = normalized(value.raw, data_type)
    except (ValueError, InvalidOperation):
        parsed = None
    return FieldObservation(
        field_id=field_id,
        data_type=data_type,
        raw=value.raw,
        normalized=parsed,
        known_state="known" if parsed is not None else "unreadable",
        evidence=evidence,
        subject_role=role,
    )


def validate_extraction(text: str, request: ModelRequest, correlation_id: UUID):
    try:
        parsed = strict_json(text)
    except (ValueError, RecursionError):
        raise ModelFailure(
            "invalid_model_output", correlation_id, stage="validating", reason="invalid_json"
        ) from None
    try:
        payload = ExtractionPayload.model_validate(parsed)
    except ValidationError:
        raise ModelFailure(
            "invalid_model_output", correlation_id, stage="validating", reason="invalid_schema"
        ) from None
    try:
        known = {s.id for s in request.sources}
        covered, results = set(), []
        for fragment in payload.fragments:
            if len(set(fragment.source_ids)) != len(fragment.source_ids):
                raise ValueError("Repeated fragment source")
            if not set(fragment.source_ids) <= known:
                raise ValueError("Unknown fragment source")
            covered.update(fragment.source_ids)
            for quote in fragment.classification_evidence:
                verify_quote(quote, request, fragment.source_ids)
            if request.forced_type is None:
                if fragment.predicted_type != fragment.document_type:
                    raise ValueError("Unrequested type override")
            elif fragment.document_type != request.forced_type.value:
                raise ValueError("Pinned type ignored")
            fields = (
                ()
                if fragment.document_type == "unknown"
                else tuple(
                    field_observation(name, getattr(fragment.fields, name), fragment, request)
                    for name in type(fragment.fields).model_fields
                )
            )
            results.append(
                RecognizedFragment(
                    fragment.predicted_type,
                    fragment.document_type,
                    tuple(fragment.source_ids),
                    fields,
                )
            )
        if covered != known:
            raise ValueError("Incomplete source coverage")
        return payload, tuple(results)
    except (ValueError, ValidationError, RecursionError, InvalidOperation):
        raise ModelFailure(
            "invalid_model_output", correlation_id, stage="validating", reason="invalid_provenance"
        ) from None
