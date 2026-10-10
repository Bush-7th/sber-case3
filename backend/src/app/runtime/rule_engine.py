"""M07/M08 deterministic checks on machine facts; no model calls or float arithmetic."""

import re
from datetime import date
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from app.http_api import schemas as s


def issue(code, message, severity="warning", category="document", rule_id=None, sources=None):
    return s.Issue(
        id=uuid4(),
        code=code,
        severity=severity,
        category=category,
        message=message,
        rule_id=rule_id,
        sources=sources or [],
        next_action=s.IssueAction(
            action="clarify_rule" if category == "configuration" else "open_source"
        ),
    )


def validate_definition(definition):
    issues = []
    types = {str(t.id): t for t in definition.document_types}
    if not types or len(types) != len(definition.document_types):
        issues.append(
            issue("invalid_types", "Задайте уникальные виды документов.", category="configuration")
        )
    ids = [r.id for r in definition.rules]
    if len(ids) != len(set(ids)):
        issues.append(
            issue("duplicate_rule", "ID правил должны быть уникальными.", category="configuration")
        )
    for t in types.values():
        fields = {f.id for f in t.fields}
        if len(fields) != len(t.fields) or not set(t.minimum_field_ids) <= fields:
            issues.append(
                issue(
                    "invalid_fields",
                    "Проверьте поля и минимальный набор.",
                    category="configuration",
                )
            )
    for req in definition.requirements:
        if str(req.document_type) not in types:
            issues.append(
                issue(
                    "invalid_requirement",
                    "Вид из требования отсутствует в каталоге.",
                    category="configuration",
                )
            )
    for rule in definition.rules:
        for binding in rule.bindings:
            target = types.get(str(binding.document_type))
            if target is None or binding.field_id not in {f.id for f in target.fields}:
                issues.append(
                    issue(
                        "invalid_binding",
                        "Привязка правила ссылается на неизвестное поле.",
                        category="configuration",
                        rule_id=rule.id,
                    )
                )
        if rule.parameters.pattern:
            # Bound simple patterns; disallow nested groups/backreferences to avoid regex DoS.
            pattern = rule.parameters.pattern
            if (
                len(pattern) > 200
                or "\\1" in pattern
                or re.search(r"\([^)]*(?:[+*]|\|)[^)]*\)[+*{]", pattern)
            ):
                issues.append(
                    issue(
                        "unsafe_pattern",
                        "Упростите регулярное выражение.",
                        category="configuration",
                        rule_id=rule.id,
                    )
                )
            else:
                try:
                    re.compile(pattern)
                except re.error:
                    issues.append(
                        issue(
                            "invalid_pattern",
                            "Регулярное выражение некорректно.",
                            category="configuration",
                            rule_id=rule.id,
                        )
                    )
    return issues


def predicate(value, context):
    if value is None:
        return None
    if value.kind in {"all", "any"}:
        values = [predicate(v, context) for v in value.operands]
        if value.kind == "all":
            return False if False in values else None if None in values else True
        return True if True in values else None if None in values else False
    actual = (
        context.project_type
        if value.field == "project_type"
        else context.conditions.get(value.field)
    )
    if actual is None:
        return None
    return actual is True if value.kind == "is_true" else actual == value.value


def evaluate(definition, documents, context, reference_date, complete):
    requirements, rules, issues = [], [], []
    for req in definition.requirements:
        matches = [d for d in documents if d.effective_type == req.document_type]
        applies = predicate(req.predicate, context) if req.kind == "conditional" else True
        status = (
            "found"
            if len(matches) >= req.quantity
            else "not_applicable"
            if applies is False
            else "unknown"
            if applies is None or req.needs_clarification
            else "missing"
            if complete
            else "pending"
        )
        severity = (
            "error"
            if req.kind == "required" and status == "missing"
            else "warning"
            if status in {"missing", "unknown", "pending"}
            else "info"
        )
        message = (
            "Документ найден."
            if status == "found"
            else "Документ не требуется."
            if status == "not_applicable"
            else "Требуется документ или уточнение условия."
        )
        requirements.append(
            s.RequirementResult(
                requirement_id=req.id,
                document_type=req.document_type,
                kind=req.kind,
                status=status,
                severity=severity,
                message=message,
                document_unit_ids=[d.id for d in matches],
            )
        )
        if status in {"missing", "unknown"}:
            problem = issue(
                "missing_document" if status == "missing" else "requirement_unknown",
                message,
                severity,
                "configuration" if status == "unknown" else "document",
            )
            problem.next_action = s.IssueAction(
                action="upload_document" if status == "missing" else "clarify_rule"
            )
            issues.append(problem)
    for rule in definition.rules:
        operands, ambiguous, present = {}, False, False
        for binding in rule.bindings:
            docs = [d for d in documents if d.effective_type == binding.document_type]
            present = present or bool(docs)
            fields = [
                f
                for d in docs
                for f in d.fields
                if f.field_id == binding.field_id
                and (binding.subject_role == "unknown" or f.subject_role == binding.subject_role)
            ]
            known = [f for f in fields if f.known_state == "known"]
            if len({str(f.normalized) for f in known}) > 1:
                ambiguous = True
            if known:
                operands[binding.operand] = known[0]
        status, message, formula = "UNKNOWN", "Недостаточно подтверждённых значений.", None
        sources = [e for f in operands.values() for e in f.evidence]
        if not present:
            status, message = "NOT_APPLICABLE", "Документ для правила пока отсутствует."
        elif rule.needs_clarification:
            message = "Параметр правила требует уточнения."
        elif not ambiguous and len(operands) == len(rule.bindings) and operands:
            values = [f.normalized for f in operands.values()]
            try:
                passed = None
                if rule.family in {"required_fields", "non_empty"}:
                    passed = all(str(v).strip() for v in values)
                elif rule.family == "matches_regex" and rule.parameters.pattern:
                    passed = all(
                        re.fullmatch(rule.parameters.pattern, str(v)[:500]) is not None
                        for v in values
                    )
                elif rule.family == "date_compare" and rule.parameters.date_mode:
                    dates = [date.fromisoformat(str(v)) for v in values]
                    passed = all(
                        d <= reference_date
                        if rule.parameters.date_mode == "not_future"
                        else d >= reference_date
                        for d in dates
                    )
                elif (
                    rule.family == "ratio_gte"
                    and rule.parameters.factor is not None
                    and len(values) == 2
                ):
                    units = {f.unit for f in operands.values()}
                    own = (
                        Decimal(str(operands["own"].normalized))
                        if "own" in operands
                        else Decimal(str(values[0]))
                    )
                    total = (
                        Decimal(str(operands["total"].normalized))
                        if "total" in operands
                        else Decimal(str(values[1]))
                    )
                    if total > 0 and len(units) == 1 and None not in units:
                        factor = Decimal(rule.parameters.factor)
                        passed = own >= factor * total
                        formula = f"{own} >= {factor} * {total}"
                elif rule.family == "amount_equal" and len(values) == 2:
                    units = {f.unit for f in operands.values()}
                    if len(units) == 1 and None not in units:
                        passed = Decimal(str(values[0])) == Decimal(str(values[1]))
                        formula = f"{values[0]} == {values[1]}"
                elif rule.family == "same_subject_value":
                    roles = {f.subject_role for f in operands.values()}
                    if len(roles) == 1 and "unknown" not in roles:
                        passed = len(set(map(str, values))) == 1
                if passed is not None:
                    status, message = (
                        ("PASS", "Правило выполнено.") if passed else ("FAIL", "Правило нарушено.")
                    )
            except (ValueError, InvalidOperation, re.error, TypeError):
                pass
        if ambiguous:
            message = "Обнаружены конфликтующие значения."
        severity = (
            rule.severity if status == "FAIL" else "warning" if status == "UNKNOWN" else "info"
        )
        rules.append(
            s.RuleResult(
                rule_id=rule.id,
                status=status,
                severity=severity,
                message=message,
                operands=operands,
                formula=formula,
                sources=sources,
            )
        )
        if status in {"FAIL", "UNKNOWN"}:
            issues.append(
                issue(
                    "rule_failed" if status == "FAIL" else "rule_unknown",
                    message,
                    severity,
                    "configuration" if rule.needs_clarification else "document",
                    rule.id,
                    sources,
                )
            )
    return requirements, rules, issues
