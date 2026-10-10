import asyncio
from datetime import timedelta
from io import BytesIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.http_api import schemas as s
from app.main import create_app
from app.modules.recognition.facts import EvidenceRef, FieldObservation, PageLocation
from app.modules.recognition.model import (
    PinnedModelProfile,
)
from app.runtime.application import now
from app.runtime.cli import bootstrap
from app.runtime.rule_engine import evaluate
from app.runtime.settings import Settings
from app.runtime.worker import LeaseLost, claim, process, publish, snapshot
from app.runtime.workflow_storage import JobRow, ResourceRow

PASSWORD = "workflow-only-test-password"


@pytest.fixture()
def configured(database_url):
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=database_url.render_as_string(hide_password=False),
        bootstrap_specialist_password=PASSWORD,
        bootstrap_admin_password=PASSWORD,
    )
    from sqlalchemy import create_engine, text

    engine = create_engine(database_url, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE workflow_resources CASCADE"))
    engine.dispose()
    bootstrap(settings)
    return settings


def login(client, user="specialist"):
    response = client.post("/api/v1/sessions", json={"username": user, "password": PASSWORD})
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def package(client, headers):
    programs = client.get("/api/v1/programs").json()["items"]
    assert len(programs) == 3
    response = client.post(
        "/api/v1/packages",
        headers=headers,
        json={"title": "API contract test", "program_version_id": programs[0]["latest_version_id"]},
    )
    assert response.status_code == 201, response.json()
    return response.json()


def png():
    with Image.new("RGB", (1, 1), "white") as im:
        stream = BytesIO()
        im.save(stream, format="PNG")
        return stream.getvalue()


@pytest.mark.integration
def test_upload_revision_idempotency_sources_decision_restart(configured):
    with TestClient(create_app(configured)) as client:
        headers = login(client)
        p = package(client, headers)
        path = f"/api/v1/packages/{p['id']}/files"
        command = {**headers, "Idempotency-Key": str(uuid4())}
        payload = [("files", ("real-container.png", png(), "image/png"))]
        uploaded = client.post(
            path, headers=command, data={"expected_revision": "0"}, files=payload
        )
        assert uploaded.status_code == 202, uploaded.json()
        result = uploaded.json()
        assert result["input_revision"] == 1 and len(result["accepted"]) == 1
        assert (
            client.post(
                path, headers=command, data={"expected_revision": "0"}, files=payload
            ).json()
            == result
        )
        assert (
            client.post(
                path,
                headers=command,
                data={"expected_revision": "0"},
                files=[("files", ("different.png", png(), "image/png"))],
            ).status_code
            == 409
        )
        assert (
            client.post(
                path,
                headers={**headers, "Idempotency-Key": str(uuid4())},
                data={"expected_revision": "0"},
                files=payload,
            ).status_code
            == 409
        )
        file_id = result["accepted"][0]["id"]
        assert client.get(f"/api/v1/files/{file_id}/content").content == png()
        assert client.get(f"/api/v1/files/{file_id}/preview?page=2").status_code == 404
        run = client.get("/api/v1/verification-runs/" + result["run_id"])
        assert run.status_code == 200 and run.json()["status"] == "queued"
        assert "_input" not in run.json()
        decision = client.post(
            f"/api/v1/packages/{p['id']}/decisions",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={
                "expected_revision": 1,
                "action": "needs_revision",
                "reason": "Проверить источник",
            },
        )
        assert decision.status_code == 201
        assert client.get(f"/api/v1/packages/{p['id']}/audit").json()["total"] >= 3
        cookie = client.cookies["session"]
    with TestClient(create_app(configured)) as restarted:
        result = restarted.get(
            f"/api/v1/packages/{p['id']}", headers={"Cookie": "session=" + cookie}
        ).json()
        assert result["input_revision"] == 1 and result["decision_status"] == "needs_revision"
        admin = login(restarted, "administrator")
        assert restarted.get(f"/api/v1/files/{file_id}/content").status_code == 403
        draft = restarted.post(
            "/api/v1/admin/program-drafts",
            headers=admin,
            json={"name": "Updated program", "base_version_id": p["program_version_id"]},
        ).json()
        validation = restarted.post(
            f"/api/v1/admin/program-drafts/{draft['id']}/validate",
            headers=admin,
            json={"expected_revision": 0},
        )
        assert validation.json()["valid"] is True
        published = restarted.post(
            f"/api/v1/admin/program-drafts/{draft['id']}/publish",
            headers={**admin, "Idempotency-Key": str(uuid4())},
            json={"expected_revision": 0},
        )
        assert published.status_code == 201 and published.json()["version"] == 2


@pytest.mark.integration
def test_worker_errors_are_visible_and_expired_lease_cannot_publish(configured):
    with TestClient(create_app(configured)) as client:
        headers = login(client)
        p = package(client, headers)
        uploaded = client.post(
            f"/api/v1/packages/{p['id']}/files",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            data={"expected_revision": 0},
            files=[("files", ("document.doc", b"opaque-unit-input", "application/msword"))],
        ).json()
        container = client.app.state.container
        # claim the new run explicitly without depending on other test jobs.
        with container.unit_of_work() as uow:
            job = uow.session.get(JobRow, uploaded["run_id"])
            lease = uuid4()
            job.status, job.lease, job.lease_until = "running", lease, now() + timedelta(seconds=60)
            uow.commit()
        profile = PinnedModelProfile(
            provider="local",
            base_url="http://127.0.0.1:9",
            model=configured.local_model,
            generation_path="/api/chat",
            api_format="ollama-chat",
            prompt_version="test",
            prompt_hash="test",
            schema_hash="test",
            timeout_seconds=1,
            max_output_tokens=100,
            context_window_size=2048,
            max_input_bytes=10000,
            max_response_bytes=10000,
        )

        class Model:
            def __init__(self):
                self.profile = profile

            async def analyze(self, *args):
                raise AssertionError("Unsupported document must fail before model call")

            async def aclose(self):
                pass

        async def factory():
            return Model()

        container.create_document_model = factory
        asyncio.run(process(container, uploaded["run_id"], lease))
        run = client.get("/api/v1/verification-runs/" + uploaded["run_id"]).json()
        assert run["status"] == "completed"
        assert run["files"][0]["processing"] == "processing_error"
        assert run["report"]["verdict"] != "pass" and run["report"]["provisional"] is True
        with pytest.raises(LeaseLost):
            data, package_snapshot, version = snapshot(container, uploaded["run_id"])
            data.pop("_input", None)
            data.pop("_profile", None)
            publish(
                container,
                s.VerificationRun.model_validate(data),
                lease,
                package_snapshot,
                s.ProgramDefinition.model_validate(version["definition"]),
            )


def test_decimal_threshold_boundary_and_missing_fact():
    file_id, version_id = uuid4(), uuid4()
    evidence = [
        EvidenceRef(
            location=PageLocation(kind="page", file_id=file_id, file_version_id=version_id, page=1),
            excerpt="contract amount",
            extraction_method="native",
        )
    ]

    def field(name, value):
        return FieldObservation(
            field_id=name,
            data_type="money",
            raw=value,
            normalized=value,
            known_state="known",
            subject_role="applicant",
            unit="RUB",
            source="machine",
            evidence=evidence,
        )

    rule = s.RuleDefinition(
        id="ratio",
        family="ratio_gte",
        severity="error",
        bindings=[
            s.FieldBinding(operand="own", document_type="cost_justification", field_id="own_funds"),
            s.FieldBinding(
                operand="total", document_type="cost_justification", field_id="total_expenses"
            ),
        ],
        parameters=s.RuleParameters(factor="0.50"),
    )
    definition = s.ProgramDefinition(
        name="test", description="", document_types=[], requirements=[], rules=[rule]
    )
    for own, expected in [("49.99", "FAIL"), ("50", "PASS"), ("50.01", "PASS")]:
        document = s.DocumentUnit(
            id=uuid4(),
            version_id=uuid4(),
            predicted_type="cost_justification",
            effective_type="cost_justification",
            type_overridden=False,
            fragments=[s.SourceFragmentRef(id=uuid4(), location=evidence[0].location)],
            fields=[field("own_funds", own), field("total_expenses", "100")],
        )
        _, results, _ = evaluate(definition, [document], s.ProjectContext(), now().date(), True)
        assert results[0].status == expected
    document.fields = [field("total_expenses", "100")]
    _, results, _ = evaluate(definition, [document], s.ProjectContext(), now().date(), True)
    assert results[0].status == "UNKNOWN"


@pytest.mark.integration
def test_successful_worker_persists_fields_and_type_override(configured):
    from app.modules.recognition.model import (
        ExtractionPayload,
        ModelAnalysis,
        ModelInvocation,
        PinnedModelProfile,
        RecognizedFragment,
    )

    with TestClient(create_app(configured)) as client:
        headers = login(client)
        p = package(client, headers)
        uploaded = client.post(
            f"/api/v1/packages/{p['id']}/files",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            data={"expected_revision": 0},
            files=[("files", ("native.png", png(), "image/png"))],
        ).json()
        container = client.app.state.container
        profile = PinnedModelProfile(
            provider="local",
            base_url="http://127.0.0.1:9",
            model=configured.local_model,
            generation_path="/api/chat",
            api_format="ollama-chat",
            prompt_version="test",
            prompt_hash="test",
            schema_hash="test",
            timeout_seconds=1,
            max_output_tokens=100,
            context_window_size=2048,
            max_input_bytes=10000,
            max_response_bytes=10000,
        )
        invocation = ModelInvocation(
            id=uuid4(),
            correlation_id=uuid4(),
            profile=profile,
            duration_ms=1,
            input_sha256="0" * 64,
            output_sha256="1" * 64,
        )
        location = PageLocation(
            kind="page",
            file_id=uploaded["accepted"][0]["id"],
            file_version_id=uploaded["accepted"][0]["file_version_id"],
            page=1,
        )
        observation = FieldObservation(
            field_id="cadastral_number",
            data_type="text",
            raw="test-value",
            normalized="test-value",
            known_state="known",
            subject_role="applicant",
            source="machine",
            evidence=[
                EvidenceRef(location=location, excerpt="test-value", extraction_method="native")
            ],
        )
        payload = ExtractionPayload.model_validate(
            {
                "fragments": [
                    {
                        "document_type": "unknown",
                        "predicted_type": "unknown",
                        "source_ids": ["source-1"],
                        "classification_evidence": [
                            {"source_id": "source-1", "excerpt": "test-value"}
                        ],
                        "fields": {},
                    }
                ]
            }
        )

        class Model:
            def __init__(self):
                self.profile = profile

            async def analyze(self, request, *args):
                return ModelAnalysis(
                    fragments=(
                        RecognizedFragment(
                            "property_document", "property_document", ("source-1",), (observation,)
                        ),
                    ),
                    invocation=invocation,
                    payload=payload,
                )

            async def aclose(self):
                pass

        async def factory():
            return Model()

        container.create_document_model = factory
        with container.unit_of_work() as uow:
            job = uow.session.get(JobRow, uploaded["run_id"])
            lease = uuid4()
            job.status, job.lease, job.lease_until = "running", lease, now() + timedelta(seconds=60)
            uow.commit()
        asyncio.run(process(container, uploaded["run_id"], lease))
        run = client.get("/api/v1/verification-runs/" + uploaded["run_id"]).json()
        assert run["files"][0]["processing"] == "checked"
        assert run["documents"][0]["fields"][0]["normalized"] == "test-value"
        assert run["report"]["freshness"] == "current"
        changed = client.patch(
            "/api/v1/document-units/" + run["documents"][0]["id"] + "/type",
            headers=headers,
            json={
                "expected_revision": 1,
                "document_type": "property_document",
                "reason": "Подтверждение специалистом",
            },
        )
        assert changed.status_code == 200, changed.json()
        assert changed.json()["input_revision"] == 2
        old = client.get("/api/v1/verification-runs/" + uploaded["run_id"]).json()
        assert old["freshness"] == "outdated"
        with container.unit_of_work() as uow:
            stored = uow.session.get(ResourceRow, invocation.id)
            assert stored.kind == "model_result"
            newest = uow.session.get(ResourceRow, changed.json()["run_id"])
            assert newest.data["_input"]["type_overrides"]


@pytest.mark.integration
def test_owner_access_and_old_run_cannot_replace_current_report(configured):
    with TestClient(create_app(configured)) as first:
        headers = login(first)
        p = package(first, headers)
        started = first.post(
            f"/api/v1/packages/{p['id']}/verification-runs",
            headers={**headers, "Idempotency-Key": str(uuid4())},
            json={"expected_revision": 0},
        ).json()
        container = first.app.state.container
        with container.unit_of_work() as uow:
            job = uow.session.get(JobRow, started["run_id"])
            old_lease = uuid4()
            job.status, job.lease, job.lease_until = (
                "running",
                old_lease,
                now() - timedelta(seconds=1),
            )
            uow.commit()
        reclaimed = claim(container)
        assert str(reclaimed[0]) == started["run_id"] and reclaimed[1] != old_lease
        data, captured, version = snapshot(container, started["run_id"])
        data.pop("_input", None)
        with pytest.raises(LeaseLost):
            publish(
                container,
                s.VerificationRun.model_validate(data),
                old_lease,
                captured,
                s.ProgramDefinition.model_validate(version["definition"]),
            )
        new = first.patch(
            f"/api/v1/packages/{p['id']}/configuration",
            headers=headers,
            json={
                "expected_revision": 0,
                "project_context": {"conditions": {"requires_certificate": False}},
            },
        ).json()
        assert new["input_revision"] == 1
        publish(
            container,
            s.VerificationRun.model_validate(data),
            reclaimed[1],
            captured,
            s.ProgramDefinition.model_validate(version["definition"]),
            True,
        )
        latest = first.get(f"/api/v1/packages/{p['id']}").json()
        assert latest["current_run_id"] == new["run_id"] and latest["report"] is None
        assert (
            first.get("/api/v1/verification-runs/" + started["run_id"]).json()["freshness"]
            == "outdated"
        )
    other = configured.model_copy(
        update={
            "bootstrap_specialist_username": "other-specialist",
            "bootstrap_admin_username": "other-administrator",
        }
    )
    bootstrap(other)
    with TestClient(create_app(other)) as second:
        login(second, "other-specialist")
        assert second.get(f"/api/v1/packages/{p['id']}").status_code == 403
        assert second.get("/api/v1/verification-runs/" + started["run_id"]).status_code == 403
        assert all(item["id"] != p["id"] for item in second.get("/api/v1/packages").json()["items"])
