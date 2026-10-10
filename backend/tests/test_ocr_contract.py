import asyncio
import sys
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from uuid import uuid4

import httpx
import pytest

from app.modules.assets.ocr import OcrCacheKey, OcrFailure, OcrProfile, OcrSource, PreparedOcrPage
from app.modules.assets.ocr_preparation import prepare_ocr_content
from app.modules.inference.olmocr import OlmOcrClient, retry_after


def prepared_page(media="image/png", data=b"\x01\x02"):
    # Opaque in-memory transport bytes, not a fabricated document or OCR quality sample.
    source = OcrSource(uuid4(), uuid4(), uuid4(), "a" * 64)
    return PreparedOcrPage(source, 3, media, "tested-preparation-v1", data)


def profile():
    return OcrProfile("https://ocr.example", "1", model="reported-model", layout=True)


def run(coroutine):
    return asyncio.run(coroutine)


def test_multipart_text_response_token_timeout_and_source_page():
    requests = []
    correlation = uuid4()
    service_id = uuid4()

    async def handler(request):
        requests.append(request)
        body = await request.aread()
        assert request.method == "POST" and request.url.path == "/ocr"
        assert request.headers["x-api-token"] == "ocr-token"
        assert request.headers["X-Correlation-ID"] == str(correlation)
        assert request.headers["Content-Type"].startswith("multipart/form-data; boundary=")
        assert b'name="file"; filename="page-3.png"' in body
        assert b"Content-Type: image/png" in body and b"\x01\x02" in body
        assert request.extensions["timeout"]["read"] == 300
        return httpx.Response(
            200,
            text="# OCR result\n\nline\n",
            headers={"Content-Type": "text/plain; charset=utf-8", "X-Request-ID": str(service_id)},
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient(
                "https://ocr.example", token="ocr-token", client=http
            ) as client:
                return await client.recognize(prepared_page(), profile(), correlation)

    output = run(scenario())
    assert output.text == "# OCR result\n\nline\n"  # Not parsed as JSON or trimmed.
    assert output.service_request_id == service_id and output.correlation_id == correlation
    assert output.duration_ms >= 0
    assert "OCR result" not in repr(output)
    assert len(requests) == 1


def test_health_reads_only_declared_metadata_and_empty_token_is_not_sent():
    async def handler(request):
        assert request.url.path == "/health" and request.method == "GET"
        assert "x-api-token" not in request.headers
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "model": "reported-model",
                "layout": True,
                "version": "actual-version",
                "secret": "discard-me",
            },
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient("https://ocr.example/", client=http) as client:
                return await client.healthcheck(uuid4())

    result = run(scenario())
    assert result.model == "reported-model" and result.service_revision == "actual-version"
    assert result.layout is True and "discard-me" not in repr(result)


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "ocr_auth_error", False),
        (403, "ocr_auth_error", False),
        (429, "ocr_rate_limited", True),
        (500, "ocr_service_error", True),
        (502, "ocr_service_error", True),
        (400, "ocr_unsupported_input", False),
        (415, "ocr_unsupported_input", False),
        (422, "ocr_unsupported_input", False),
        (413, "ocr_input_too_large", False),
        (302, "ocr_invalid_response", False),
    ],
)
def test_http_errors_are_ocr_specific_safe_and_have_no_internal_retry(status, code, retryable):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="SECRET-DOCUMENT-BODY",
            headers={"Retry-After": "7", "Location": "https://untrusted.example"},
        )

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient(
                "https://ocr.example", token="SECRET-TOKEN", client=http
            ) as client:
                await client.recognize(prepared_page(), profile(), uuid4())

    with pytest.raises(OcrFailure) as caught:
        run(scenario())
    failure = caught.value
    assert failure.stage == "ocr" and failure.provider == "olmocr"
    assert failure.code == code and failure.retryable is retryable and failure.status == status
    assert failure.retry_after_seconds == (7 if retryable else None)
    assert "SECRET" not in str(failure) + repr(failure)
    assert len(calls) == 1  # M11 schedules bounded retries; no compounded retry loops.


@pytest.mark.parametrize(
    "mode,code", [("timeout", "ocr_timeout"), ("network", "ocr_network_error")]
)
def test_network_errors_preserve_no_driver_exception_text(mode, code):
    async def handler(request):
        error = httpx.ReadTimeout if mode == "timeout" else httpx.ConnectError
        raise error("SECRET-DRIVER-CONTENT", request=request)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient("https://ocr.example", client=http) as client:
                await client.recognize(prepared_page(), profile(), uuid4())

    with pytest.raises(OcrFailure) as caught:
        run(scenario())
    assert caught.value.code == code and caught.value.retryable
    assert "SECRET" not in str(caught.value)


def test_total_timeout_also_bounds_a_slow_response():
    async def handler(request):
        await asyncio.sleep(0.1)
        return httpx.Response(200, text="too late", headers={"Content-Type": "text/plain"})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient(
                "https://ocr.example", timeout_seconds=0.01, client=http
            ) as client:
                await client.recognize(prepared_page(), profile(), uuid4())

    with pytest.raises(OcrFailure) as caught:
        run(scenario())
    assert caught.value.code == "ocr_timeout" and caught.value.retryable


@pytest.mark.parametrize(
    "body,content_type,code",
    [
        (" \n\t", "text/plain", "ocr_empty_result"),
        ('{"text":"unexpected JSON"}', "application/json", "ocr_invalid_response"),
        ("<html>error page</html>", "text/html", "ocr_invalid_response"),
    ],
)
def test_empty_or_unexpected_success_is_not_a_machine_result(body, content_type, code):
    async def handler(request):
        return httpx.Response(200, text=body, headers={"Content-Type": content_type})

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient("https://ocr.example", client=http) as client:
                await client.recognize(prepared_page(), profile(), uuid4())

    with pytest.raises(OcrFailure) as caught:
        run(scenario())
    assert caught.value.code == code and not caught.value.retryable


def test_office_large_inputs_and_wrong_profile_do_not_make_a_request():
    async def handler(request):
        pytest.fail("Invalid OCR input must be rejected locally")

    async def scenario(page, snapshot):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with OlmOcrClient(
                "https://ocr.example", max_input_bytes=2, client=http
            ) as client:
                await client.recognize(page, snapshot, uuid4())

    for page, snapshot, code in [
        (prepared_page("application/msword"), profile(), "ocr_unsupported_input"),
        (prepared_page(data=b"\x01\x02\x03"), profile(), "ocr_input_too_large"),
        (prepared_page(), replace(profile(), configuration_revision="2"), "ocr_profile_mismatch"),
    ]:
        with pytest.raises(OcrFailure) as caught:
            run(scenario(page, snapshot))
        assert caught.value.code == code and not caught.value.retryable
    with pytest.raises(OcrFailure) as caught:
        prepare_ocr_content(prepared_page().source, b"opaque", "application/msword")
    assert caught.value.stage == "preparing" and caught.value.provider is None


@pytest.mark.parametrize("page", ["0", "-1"])
def test_cli_rejects_nonpositive_pages_before_network_or_database(monkeypatch, page):
    from app.runtime.ocr_cli import main

    monkeypatch.setattr(sys, "argv", ["ocr_cli", "sample", "/unread/sample.pdf", "--page", page])
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2


def test_retry_after_and_profile_cache_compatibility():
    assert retry_after("0") == 0 and retry_after("1.5") == 1.5
    for invalid in (None, "", "bad", "-2", "nan", "inf"):
        assert retry_after(invalid) is None
    future = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
    assert 0 <= retry_after(future) <= 30
    page, snapshot = prepared_page(), profile()
    key = OcrCacheKey.for_page(page, snapshot)
    # Re-generated PDF serialization may change timestamps/IDs; semantic preparation stays pinned.
    assert key == OcrCacheKey.for_page(replace(page, data=b"other-serialization"), snapshot)
    for changed in (
        replace(page, page=2),
        replace(page, preparation_profile="v2"),
        replace(page, source=replace(page.source, file_version_id=uuid4())),
    ):
        assert key != OcrCacheKey.for_page(changed, snapshot)
    assert key != OcrCacheKey.for_page(page, replace(snapshot, configuration_revision="2"))
    assert key != OcrCacheKey.for_page(page, replace(snapshot, model="different-real-model"))
