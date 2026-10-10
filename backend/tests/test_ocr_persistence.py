import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.modules.assets.ocr import (
    OcrFailure,
    OcrProfile,
    OcrSource,
    OcrSourceConflict,
    OcrText,
    PreparedOcrPage,
)
from app.modules.assets.ocr_persistence import OcrResultRow, SqlOcrRepository
from app.modules.assets.ocr_service import OcrContentService
from app.modules.assets.persistence import PostgresBlobStore
from app.modules.inference.olmocr import OlmOcrClient
from app.runtime.container import AppContainer
from app.runtime.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture()
def ocr_setup(database_url):
    engine = create_engine(database_url, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE assets_ocr_results, assets_file_versions, "
                "assets_blob_references, assets_blobs CASCADE"
            )
        )
    settings = Settings(
        _env_file=None, database_url=database_url.render_as_string(hide_password=False)
    )
    container = AppContainer(settings)
    with container.unit_of_work() as uow:
        original = PostgresBlobStore(uow.session).put_immutable(uuid4(), b"\x01\x02", "image/png")
        source = OcrSource(uuid4(), uuid4(), original.id, original.sha256)
        SqlOcrRepository(uow.session).register_source(source)
        uow.commit()
    page = PreparedOcrPage(source, 2, "image/png", "contract-preparation-v1", b"\x03\x04")
    snapshot = OcrProfile("https://ocr.example", "1", model="reported-model", layout=True)
    try:
        yield container, settings, engine, page, snapshot
    finally:
        container.close()
        engine.dispose()


def test_saved_ocr_survives_restart_and_downstream_failure_without_another_post(ocr_setup):
    container, settings, engine, page, snapshot = ocr_setup
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(200, text="contract OCR text", headers={"Content-Type": "text/plain"})

    async def first():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient("https://ocr.example", client=http) as port:
                service = OcrContentService(port, container.ocr_result_store())
                return await service.prepare(page, snapshot, uuid4())

    saved = asyncio.run(first())
    assert not saved.reused and saved.result.page == 2
    with Session(engine) as session:
        row = session.get(OcrResultRow, saved.result.id)
        assert row.text == "contract OCR text" and row.prepared_sha256 == page.sha256
        assert row.file_version_id == page.source.file_version_id
        assert row.ocr_profile["model"] == "reported-model"
        assert "token" not in repr(row.ocr_profile) + repr(row.invocation)
    # A downstream error cannot roll back the earlier committed OCR transaction.
    with pytest.raises(RuntimeError):
        raise RuntimeError("downstream extraction failed")
    container.close()
    restarted = AppContainer(settings)

    async def retry():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient("https://ocr.example", client=http) as port:
                return await OcrContentService(port, restarted.ocr_result_store()).prepare(
                    replace(page, data=b"regenerated-serialization"), snapshot, uuid4()
                )

    try:
        reused = asyncio.run(retry())
        assert reused.reused and reused.result.id == saved.result.id
        assert reused.result.prepared_sha256 == page.sha256
        assert len(calls) == 1
    finally:
        restarted.close()


def test_no_open_transaction_during_http_and_provider_failure_keeps_previous_text(ocr_setup):
    container, _, engine, page, snapshot = ocr_setup
    original = OcrText("previous OCR text", "text/plain", 1, uuid4())
    saved = container.ocr_result_store().save(page, snapshot, original)

    async def handler(request):
        with engine.connect() as connection:
            count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND pid <> pg_backend_pid() "
                    "AND state IN ('active', 'idle in transaction') AND xact_start IS NOT NULL"
                )
            ).scalar_one()
            assert count == 0
        return httpx.Response(503, text="provider internal text", headers={"Retry-After": "3"})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient(
                "https://ocr.example", configuration_revision="2", client=http
            ) as port:
                return await OcrContentService(port, container.ocr_result_store()).prepare(
                    page, replace(snapshot, configuration_revision="2"), uuid4()
                )

    with pytest.raises(OcrFailure) as caught:
        asyncio.run(scenario())
    assert caught.value.retryable and caught.value.retry_after_seconds == 3
    assert container.ocr_result_store().find(page, snapshot).id == saved.id
    with Session(engine) as session:
        assert len(session.scalars(select(OcrResultRow)).all()) == 1


def test_source_mismatch_and_profile_changes_do_not_reuse_incompatible_text(ocr_setup):
    container, _, _, page, snapshot = ocr_setup
    store = container.ocr_result_store()
    output = OcrText("OCR text", "text/plain", 1, uuid4())
    original = store.save(page, snapshot, output)
    assert store.find(page, replace(snapshot, model="changed-model")) is None
    assert store.find(replace(page, preparation_profile="new-preparation"), snapshot) is None
    for source in (
        replace(page.source, file_id=uuid4()),
        replace(page.source, original_sha256="0" * 64),
        replace(page.source, original_blob_id=uuid4()),
    ):
        with pytest.raises(OcrSourceConflict):
            store.find(replace(page, source=source), snapshot)
    changed = store.save(page, replace(snapshot, configuration_revision="2"), output)
    assert changed.id != original.id
    assert store.find(page, snapshot).id == original.id


def test_duplicate_publication_is_immutable_and_ocr_transaction_rolls_back(ocr_setup):
    container, _, engine, page, snapshot = ocr_setup
    output = OcrText("OCR text", "text/plain", 1, uuid4())
    store = container.ocr_result_store()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(store.save, page, snapshot, output) for _ in range(2)]
        results = [future.result() for future in futures]
    assert results[0].id == results[1].id
    assert (
        store.save(page, snapshot, replace(output, text="later conflicting response")).output.text
        == "OCR text"
    )
    with pytest.raises(RuntimeError), container.unit_of_work() as uow:
        rolled_back = SqlOcrRepository(uow.session).save(
            replace(page, page=3), snapshot, OcrText("rolled back text", "text/plain", 1, uuid4())
        )
        raise RuntimeError("rollback")
    with Session(engine) as session:
        assert session.get(OcrResultRow, rolled_back.id) is None
    assert results[0].created_at <= datetime.now(UTC)


def test_qwen_reads_committed_ocr_after_failure_and_runtime_restart(ocr_setup):
    from test_qwen import envelope, profile

    from app.modules.inference.qwen import QwenProvider
    from app.modules.recognition.model import ModelFailure
    from app.runtime.qwen_cli import load_input

    container, settings, engine, page, snapshot = ocr_setup
    saved = container.ocr_result_store().save(
        page, snapshot, OcrText("61:01:1234567:8 123,45", "text/plain", 1, uuid4())
    )
    calls = []

    async def handler(request):
        calls.append(request)
        with engine.connect() as connection:
            count = connection.execute(
                text(
                    "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                    "AND pid<>pg_backend_pid() AND state IN ('active', 'idle in transaction') "
                    "AND xact_start IS NOT NULL"
                )
            ).scalar_one()
            assert count == 0
        if len(calls) == 1:
            return httpx.Response(503, text="PRIVATE-SERVICE-BODY")
        return httpx.Response(200, json=envelope())

    async def analyze(current):
        prepared = load_input(
            current, page.source.file_version_id, ocr_result_id=saved.id, page=None
        )
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with QwenProvider(
                profile(),
                key="separate-key",
                auth_header="Authorization",
                auth_scheme="Bearer",
                client=http,
            ) as model:
                return await model.analyze(prepared, model.profile, uuid4())

    with pytest.raises(ModelFailure) as caught:
        asyncio.run(analyze(container))
    assert caught.value.retryable and caught.value.provider == "qwen"
    container.close()
    restarted = AppContainer(settings)
    try:
        result = asyncio.run(analyze(restarted))
        evidence = next(v for v in result.fragments[0].fields if v.field_id == "area").evidence[0]
        assert evidence.ocr_result_id == saved.id
        assert evidence.location.file_version_id == page.source.file_version_id
        assert evidence.location.page == page.page
        assert restarted.ocr_result_store().find(page, snapshot).id == saved.id
        with Session(engine) as session:
            assert len(session.scalars(select(OcrResultRow)).all()) == 1
        assert len(calls) == 2
        assert all(call.url.path == "/v1/chat/completions" for call in calls)
        with pytest.raises(ValueError):
            load_input(restarted, uuid4(), ocr_result_id=saved.id, page=None)
    finally:
        restarted.close()
