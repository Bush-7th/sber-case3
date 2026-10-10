import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.http_api import schemas as s
from app.main import create_app

FILE_ID = uuid4()
VERSION_ID = uuid4()


def evidence():
    return {
        "location": {"kind": "page", "file_id": FILE_ID, "file_version_id": VERSION_ID, "page": 2},
        "excerpt": "500.00",
        "extraction_method": "native",
    }


def fact(**changes):
    return {
        "field_id": "own_funds",
        "data_type": "money",
        "raw": "500.00",
        "normalized": "500.00",
        "known_state": "known",
        "evidence": [evidence()],
        **changes,
    }


def report(**changes):
    return {
        "id": uuid4(),
        "package_id": uuid4(),
        "run_id": uuid4(),
        "input_revision": 1,
        "progress_version": 2,
        "program_version_id": uuid4(),
        "created_at": "2026-10-10T10:00:00Z",
        "reference_date": "2026-10-10",
        "timezone": "Europe/Moscow",
        "coverage": "complete",
        "provisional": False,
        "freshness": "current",
        "verdict": "pass",
        **changes,
    }


@pytest.mark.parametrize("value", [500, 500.0, True, "5e2", "500,00", "NaN"])
def test_money_is_a_decimal_string(value):
    with pytest.raises(ValidationError):
        s.FieldObservation.model_validate(fact(normalized=value))


def test_money_serialization_preserves_precision_and_missing_is_null():
    known = s.FieldObservation.model_validate(fact(normalized="500.000000000000000001"))
    assert known.model_dump(mode="json")["normalized"] == "500.000000000000000001"
    missing = s.FieldObservation.model_validate(
        fact(raw=None, normalized=None, known_state="missing", evidence=[]),
    )
    assert missing.model_dump(mode="json")["normalized"] is None


def test_known_machine_fact_requires_value_and_evidence():
    for changes in ({"evidence": []}, {"normalized": None}, {"source": "human"}):
        with pytest.raises(ValidationError):
            s.FieldObservation.model_validate(fact(**changes))


@pytest.mark.parametrize("value", ["2026-W41-6", "20261010", "2026-02-30", "2026-10-10T10:00:00Z"])
def test_date_facts_require_calendar_iso_dates(value):
    with pytest.raises(ValidationError):
        s.FieldObservation.model_validate(fact(data_type="date", normalized=value))


def test_source_locations_are_discriminated_and_coordinates_are_optional():
    page = s.EvidenceRef.model_validate(evidence())
    assert page.location.page == 2
    assert page.location.bbox is None
    with pytest.raises(ValidationError):
        s.EvidenceRef.model_validate({**evidence(), "extraction_method": "ocr"})
    ocr = s.EvidenceRef.model_validate(
        {
            **evidence(),
            "extraction_method": "ocr",
            "ocr_result_id": uuid4(),
        }
    )
    assert ocr.ocr_result_id is not None
    with pytest.raises(ValidationError):
        s.EvidenceRef.model_validate(
            {
                **evidence(),
                "location": {**evidence()["location"], "sheet": "Лист1"},
            }
        )
    with pytest.raises(ValidationError):
        s.BoundingBox(x=0.9, y=0, width=0.2, height=0.2)


@pytest.mark.parametrize(
    "changes",
    [
        {"coverage": "partial"},
        {"provisional": True},
        {
            "rules": [
                {
                    "rule_id": "ratio",
                    "status": "UNKNOWN",
                    "severity": "warning",
                    "message": "Нет суммы",
                }
            ]
        },
        {
            "requirements": [
                {
                    "requirement_id": "certificate",
                    "document_type": "certificate",
                    "kind": "conditional",
                    "status": "missing",
                    "severity": "warning",
                    "message": "Нет сертификата",
                }
            ]
        },
    ],
)
def test_report_cannot_pass_while_partial_or_unresolved(changes):
    with pytest.raises(ValidationError):
        s.MachineReport.model_validate(report(**changes))


def test_decision_is_independent_of_machine_verdict():
    command = s.DecisionCreate(expected_revision=2, action="accepted", reason="Проверено вручную")
    assert command.report_id is None
    assert "verdict" not in s.DecisionCreate.model_fields
    assert s.MachineReport.model_validate(report()).basis == "machine"
    with pytest.raises(ValidationError):
        s.DecisionCreate(expected_revision=2, action="accepted", reason=" ")


def test_conditional_deficit_cannot_be_promoted_to_error():
    with pytest.raises(ValidationError):
        s.RequirementDefinition(
            id="certificate",
            document_type="certificate",
            kind="conditional",
            quantity=1,
            missing_severity="error",
        )
    with pytest.raises(ValidationError):
        s.RequirementResult(
            requirement_id="certificate",
            document_type="certificate",
            kind="conditional",
            status="missing",
            severity="error",
            message="Нет сертификата",
        )


def test_revision_and_progress_counters_cannot_be_coerced_or_miscounted():
    for revision in (True, -1, "1"):
        with pytest.raises(ValidationError):
            s.VerificationCreate(expected_revision=revision)
    with pytest.raises(ValidationError):
        s.RunProgress(total=3, accepted=1, determining=1, checked=0, processing_error=0)
    with pytest.raises(ValidationError):
        s.ConfigurationUpdate(expected_revision=1)


def test_predicates_accept_unknown_context_and_reject_arbitrary_code():
    context = s.ProjectContext(conditions={"requires_certificate": None})
    assert context.conditions["requires_certificate"] is None
    predicate = s.AllPredicate.model_validate(
        {
            "kind": "all",
            "operands": [
                {"kind": "equals", "field": "project_type", "value": "innovation"},
                {"kind": "is_true", "field": "requires_certificate"},
            ],
        }
    )
    assert len(predicate.operands) == 2
    with pytest.raises(ValidationError):
        s.AllPredicate.model_validate({"kind": "all", "operands": [{"kind": "eval", "code": "1"}]})


def test_openapi_is_current_and_operations_have_errors_and_correct_security():
    schema = create_app().openapi()
    checked_in = json.loads((Path(__file__).parents[1] / "openapi.json").read_text())
    assert checked_in == schema
    operations = [operation for path in schema["paths"].values() for operation in path.values()]
    assert len(operations) == 28
    assert len({operation["operationId"] for operation in operations}) == 28
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if path.startswith("/health/"):
                assert not operation.get("security")
                continue
            assert "422" in operation["responses"]
            if path == "/api/v1/sessions" and method == "post":
                assert not operation.get("security")
            elif method in ("post", "patch", "delete"):
                assert operation["security"] == [{"SessionCookie": [], "CsrfToken": []}]
            else:
                assert operation["security"] == [{"SessionCookie": []}]
    upload = schema["paths"]["/api/v1/packages/{package_id}/files"]["post"]
    assert "multipart/form-data" in upload["requestBody"]["content"]
    key = next(p for p in upload["parameters"] if p["name"] == "Idempotency-Key")
    assert key["required"] is True


def test_invalid_command_has_correlation_without_echoing_secret_input():
    with TestClient(create_app()) as client:
        correlation = str(uuid4())
        response = client.post(
            "/api/v1/sessions",
            json={"username": "", "password": "SECRET-INPUT", "role": "administrator"},
            headers={"X-Correlation-ID": correlation},
        )
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_command"
    assert response.json()["correlation_id"] == correlation
    assert response.headers["X-Correlation-ID"] == correlation
    assert "SECRET-INPUT" not in response.text


def test_unconfigured_server_denies_protected_operations():
    with TestClient(create_app()) as client:
        for path in ("/api/v1/packages", f"/api/v1/files/{uuid4()}/content"):
            response = client.get(path)
            assert response.status_code == 401
            assert response.json()["code"] == "session_required"
            UUID(response.json()["correlation_id"])
