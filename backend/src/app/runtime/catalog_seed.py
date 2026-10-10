"""M04 initial catalogue derived from specs 1.2; no applicant documents."""

import json
from datetime import UTC, datetime
from importlib.resources import files
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy.orm import Session

from app.http_api import schemas as s
from app.modules.recognition.model import FIELD_MODELS
from app.modules.recognition.validation import DATES, MONEY
from app.runtime.workflow_storage import ResourceRow

MINIMUM = {
    "application": ["organization", "inn", "requested_amount", "date"],
    "consent": ["full_name", "date"],
    "certificate": ["number", "expiration_date"],
    "presentation": ["project_name"],
    "cost_justification": ["total_expenses", "own_funds"],
    "bank_statement": ["organization", "balance", "date"],
    "property_document": ["cadastral_number"],
    "guarantee_letter": ["organization", "amount", "date"],
    "gims_declaration": [],
}
LABELS = [
    "Заявление",
    "Согласие на ПД",
    "Сертификат",
    "Презентация",
    "Обоснование затрат",
    "Банковская выписка",
    "Документ на недвижимость",
    "Гарантийное письмо",
    "Декларация ГИМС",
]


def seed_catalog(session: Session):
    meanings = json.loads(
        files("app.modules.inference").joinpath("prompts/local-fields-v1.json").read_text()
    )
    types = []
    rules = []
    for (kind, model), label in zip(FIELD_MODELS.items(), LABELS, strict=True):
        fields = [
            s.FieldDefinition(
                id=f,
                label=meanings[kind][f],
                data_type=(
                    "money"
                    if f in MONEY
                    else "date"
                    if f in DATES
                    else "decimal"
                    if f == "area"
                    else "expense_items"
                    if f == "expense_items"
                    else "text"
                ),
                unit="RUB" if f in MONEY else None,
            )
            for f in model.model_fields
        ]
        types.append(
            s.DocumentTypeDefinition(
                id=kind,
                label=label,
                description=label,
                fields=fields,
                minimum_field_ids=MINIMUM[kind],
                extension=kind == "gims_declaration",
            )
        )
        for f in MINIMUM[kind]:
            rules.append(
                s.RuleDefinition(
                    id=f"{kind}.{f}.required",
                    family="required_fields",
                    bindings=[s.FieldBinding(operand="value", document_type=kind, field_id=f)],
                    severity="warning",
                )
            )
        for f in model.model_fields:
            if f in DATES:
                rules.append(
                    s.RuleDefinition(
                        id=f"{kind}.{f}.date",
                        family="date_compare",
                        bindings=[s.FieldBinding(operand="value", document_type=kind, field_id=f)],
                        parameters=s.RuleParameters(
                            date_mode="not_expired" if f == "expiration_date" else "not_future"
                        ),
                        severity="error",
                    )
                )

    def binding(operand, kind, field):
        return s.FieldBinding(operand=operand, document_type=kind, field_id=field)

    rules.extend(
        [
            s.RuleDefinition(
                id="applicant.inn",
                family="matches_regex",
                bindings=[binding("value", "application", "inn")],
                parameters=s.RuleParameters(pattern=r"(?:[0-9]{10}|[0-9]{12})"),
                severity="error",
            ),
            s.RuleDefinition(
                id="property.cadastral",
                family="matches_regex",
                bindings=[binding("value", "property_document", "cadastral_number")],
                parameters=s.RuleParameters(pattern=None),
                severity="warning",
                needs_clarification=True,
            ),
            s.RuleDefinition(
                id="cost.own_ratio",
                family="ratio_gte",
                bindings=[
                    binding("own", "cost_justification", "own_funds"),
                    binding("total", "cost_justification", "total_expenses"),
                ],
                parameters=s.RuleParameters(factor="0.50"),
                severity="error",
            ),
            s.RuleDefinition(
                id="amount.consistency",
                family="amount_equal",
                bindings=[
                    binding("application", "application", "requested_amount"),
                    binding("cost", "cost_justification", "requested_subsidy_amount"),
                ],
                severity="error",
            ),
        ]
    )
    common = ["application", "consent", "cost_justification", "bank_statement"]
    programmes = [
        (
            "innovation",
            "Инновационный проект",
            common + ["presentation", "guarantee_letter"],
            "certificate",
        ),
        ("beach", "Обустройство пляжа", common + ["property_document"], "gims_declaration"),
        (
            "modernization",
            "Модернизация производства",
            common + ["guarantee_letter", "property_document"],
            "certificate",
        ),
    ]
    for key, name, required, conditional in programmes:
        program_id = uuid5(NAMESPACE_URL, "case3/program/" + key)
        version_id = uuid5(program_id, "version/1")
        if session.get(ResourceRow, version_id):
            continue
        requirements = [
            s.RequirementDefinition(
                id=k, document_type=k, kind="required", quantity=1, missing_severity="error"
            )
            for k in required
        ]
        requirements.append(
            s.RequirementDefinition(
                id=conditional,
                document_type=conditional,
                kind="conditional",
                quantity=1,
                missing_severity="warning",
                predicate=s.IsTruePredicate(kind="is_true", field="requires_" + conditional),
            )
        )
        version = s.ProgramVersion(
            id=version_id,
            program_id=program_id,
            version=1,
            published_at=datetime.now(UTC),
            definition=s.ProgramDefinition(
                name=name,
                description="Начальный каталог по спецификации; неоднозначности отмечены явно.",
                document_types=types,
                requirements=requirements,
                rules=rules,
            ),
        )
        session.add(
            ResourceRow(
                id=version_id,
                kind="version",
                parent_id=program_id,
                owner_id=None,
                data=version.model_dump(mode="json"),
                created_at=datetime.now(UTC),
            )
        )
