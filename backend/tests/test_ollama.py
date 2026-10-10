"""Local HTTP contracts and bare facts. Real CPU/document acceptance is recorded separately."""

import asyncio
import base64
import json
from dataclasses import replace
from uuid import uuid4

import httpx
import pytest
from test_qwen import payload, quote, source

from app.modules.inference.ollama import (
    PROMPT_VERSION,
    LocalModelFailure,
    OllamaClient,
    OllamaProvider,
    local_prompt_hash,
)
from app.modules.recognition.facts import DocumentType
from app.modules.recognition.model import LocalModelProfile, ModelRequest, local_schema_hash
from app.runtime.settings import Settings

MODEL = "qwen3-vl:4b-instruct"
DIGEST = "sha256:" + "a" * 64


def profile():
    return LocalModelProfile(
        provider="local",
        base_url="http://127.0.0.1:11439",
        model=MODEL,
        generation_path="/api/chat",
        api_format="ollama-chat",
        prompt_version=PROMPT_VERSION,
        prompt_hash=local_prompt_hash(),
        schema_hash=local_schema_hash(),
        timeout_seconds=300,
        max_output_tokens=2048,
        context_window_size=16384,
        max_input_bytes=12_000_000,
        max_response_bytes=4_000_000,
        model_digest=DIGEST,
        server_version="0.12.10",
        num_threads=6,
        keep_alive_seconds=30,
        vision=True,
    )


def classification(kind="property_document"):
    return {
        "fragments": [
            {
                "predicted_type": kind,
                "source_ids": ["source-1"],
                "classification_evidence": [quote("61:01:1234567:8")],
            }
        ]
    }


def response(content):
    return {
        "model": MODEL,
        "done": True,
        "done_reason": "stop",
        "message": {
            "role": "assistant",
            "content": json.dumps(content),
            "thinking": "PRIVATE-REASONING",
        },
        "prompt_eval_count": 100,
        "eval_count": 10,
        "private": "DISCARD-ME",
    }


def metadata(request, *, digest=DIGEST, remote=False):
    if request.url.path == "/api/version":
        return httpx.Response(200, json={"version": "0.12.10"})
    if request.url.path == "/api/tags":
        return httpx.Response(
            200, json={"models": [{"name": MODEL, "digest": digest.removeprefix("sha256:")}]}
        )
    if request.url.path == "/api/show":
        data = {"capabilities": ["completion", "vision"]}
        if remote:
            data["remote_host"] = "https://untrusted.example"
        return httpx.Response(200, json=data)
    return None


def analyze(handler, *, request=None, snapshot=None, supplied=None):
    snapshot = snapshot or profile()

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            client = OllamaClient(
                snapshot.base_url,
                timeout_seconds=snapshot.timeout_seconds,
                max_response_bytes=snapshot.max_response_bytes,
                client=http,
            )
            async with OllamaProvider(snapshot, client) as provider:
                return await provider.analyze(
                    request or ModelRequest((source(method="native"),)),
                    supplied or snapshot,
                    uuid4(),
                )

    return asyncio.run(run())


def test_cpu_stages_nullable_fields_sources_and_no_remote_headers(caplog):
    chats = []

    async def handler(request):
        assert request.url.host == "127.0.0.1"
        assert "Authorization" not in request.headers and "x-api-token" not in request.headers
        known = metadata(request)
        if known:
            return known
        assert request.url.path == "/api/chat"
        body = json.loads(await request.aread())
        chats.append(body)
        assert body["stream"] is False and body["think"] is False
        assert body["options"] == {
            "temperature": 0,
            "seed": 0,
            "num_gpu": 0,
            "num_thread": 6,
            "num_ctx": 16384,
            "num_predict": 2048,
        }
        assert body["keep_alive"] == 30 and isinstance(body["format"], dict)
        assert "tools" not in body
        return httpx.Response(
            200,
            json=response(
                classification() if len(chats) == 1 else payload()["fragments"][0]["fields"]
            ),
        )

    result = analyze(handler)
    fields = {f.field_id: f for f in result.fragments[0].fields}
    assert fields["area"].normalized == "123.45"
    assert fields["address"].normalized is None and fields["address"].known_state == "missing"
    assert fields["area"].evidence[0].extraction_method == "native"
    assert result.invocation.profile.model_digest == DIGEST
    assert [call.stage for call in result.invocation.calls] == ["classifying", "extracting"]
    assert all(
        call.prompt_tokens == 100 and call.output_tokens == 10 for call in result.invocation.calls
    )
    assert len(chats) == 2
    assert chats[0]["format"]["$defs"]["FragmentBase"]["required"] == [
        "predicted_type",
        "source_ids",
        "classification_evidence",
    ]
    assert "cadastral_number" in chats[1]["format"]["required"]
    assert "requested_amount" not in chats[1]["format"]["required"]
    assert "PRIVATE" not in repr(result) + caplog.text and "DISCARD-ME" not in repr(result)


def test_images_use_local_transcription_and_preserve_vision_provenance():
    chats = []
    prepared = replace(
        source(method="native"),
        text="",
        extraction_method="vision",
        image=b"\x01\x02",
        media_type="image/png",
    )

    async def handler(request):
        known = metadata(request)
        if known:
            return known
        body = json.loads(await request.aread())
        chats.append(body)
        if len(chats) == 1:
            assert body["messages"][1]["images"] == [base64.b64encode(b"\x01\x02").decode()]
            value = {"text": "61:01:1234567:8 123,45"}
        elif len(chats) == 2:
            assert "images" not in body["messages"][1]
            value = classification()
        else:
            value = payload()["fragments"][0]["fields"]
        return httpx.Response(200, json=response(value))

    result = analyze(handler, request=ModelRequest((prepared,)))
    fact = next(v for v in result.fragments[0].fields if v.field_id == "area")
    assert fact.evidence[0].extraction_method == "vision"
    assert fact.evidence[0].ocr_result_id is None and fact.evidence[0].location == prepared.location
    assert fact.evidence[0].location.bbox is None
    assert result.prepared_sources[0].text == "61:01:1234567:8 123,45"
    assert "local-transcribe-v1" in result.invocation.preparation_profiles[0]
    assert [call.stage for call in result.invocation.calls] == [
        "transcribing",
        "classifying",
        "extracting",
    ]
    assert len(chats) == 3


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "local_auth_error", False),
        (403, "local_auth_error", False),
        (404, "local_model_missing", False),
        (429, "local_rate_limited", True),
        (503, "local_service_error", True),
        (400, "local_unsupported_input", False),
        (413, "local_input_too_large", False),
        (302, "local_invalid_response", False),
    ],
)
def test_one_attempt_and_no_remote_fallback_on_errors(status, code, retryable):
    chats = []

    async def handler(request):
        known = metadata(request)
        if known:
            return known
        chats.append(request)
        return httpx.Response(
            status,
            text="PRIVATE-ERROR-BODY",
            headers={"Retry-After": "7", "Location": "https://untrusted.example"},
        )

    with pytest.raises(LocalModelFailure) as caught:
        analyze(handler)
    assert caught.value.code == code and caught.value.provider == "ollama"
    assert caught.value.retryable is retryable
    assert caught.value.retry_after_seconds == (7 if retryable else None)
    assert "PRIVATE" not in str(caught.value) + repr(caught.value)
    assert len(chats) == 1


@pytest.mark.parametrize(
    "error,code",
    [(httpx.ConnectError, "local_network_error"), (httpx.ReadTimeout, "local_timeout")],
)
def test_network_error_is_safe(error, code):
    async def handler(request):
        known = metadata(request)
        if known:
            return known
        raise error("PRIVATE-DRIVER", request=request)

    with pytest.raises(LocalModelFailure) as caught:
        analyze(handler)
    assert caught.value.code == code and caught.value.retryable
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize(
    "mode", ["truncated", "other_model", "tool", "invalid_json", "invented_quote", "invalid_fields"]
)
def test_invalid_outputs_do_not_become_machine_facts(mode):
    count = 0

    async def handler(request):
        nonlocal count
        known = metadata(request)
        if known:
            return known
        count += 1
        value = response(classification() if count == 1 else payload()["fragments"][0]["fields"])
        if mode == "invalid_fields" and count == 2:
            value["message"]["content"] = '{"address": null}'
        elif count == 1:
            if mode == "truncated":
                value["done_reason"] = "length"
            elif mode == "other_model":
                value["model"] = "silent-fallback"
            elif mode == "tool":
                value["message"]["tool_calls"] = [{"name": "untrusted"}]
            elif mode == "invalid_json":
                value["message"]["content"] = '{"fragments": NaN}'
            elif mode == "invented_quote":
                bad = classification()
                bad["fragments"][0]["classification_evidence"] = [quote("unprovided")]
                value = response(bad)
        return httpx.Response(200, json=value)

    with pytest.raises(LocalModelFailure) as caught:
        analyze(handler)
    assert caught.value.code == "local_invalid_model_output"
    assert caught.value.stage == "validating" and not caught.value.retryable
    assert count == (2 if mode == "invalid_fields" else 1)


def test_digest_changes_and_cloud_aliases_fail_before_generation():
    for remote, digest, code in (
        (True, DIGEST, "local_cloud_model_forbidden"),
        (False, "sha256:" + "b" * 64, "local_profile_mismatch"),
    ):

        async def handler(request, remote=remote, digest=digest):
            known = metadata(request, remote=remote, digest=digest)
            if known:
                return known
            pytest.fail("Must reject before generation")

        with pytest.raises(LocalModelFailure) as caught:
            analyze(handler)
        assert caught.value.code == code and not caught.value.retryable


def test_profile_context_and_vision_capability_fail_without_http():
    async def handler(request):
        pytest.fail("Rejected locally")

    with pytest.raises(LocalModelFailure) as caught:
        analyze(handler, supplied=replace(profile(), model_digest="sha256:" + "b" * 64))
    assert caught.value.code == "local_profile_mismatch"
    image = replace(
        source(method="native"),
        text="",
        extraction_method="vision",
        image=b"\x01",
        media_type="image/png",
    )
    with pytest.raises(LocalModelFailure) as caught:
        analyze(handler, request=ModelRequest((image,)), snapshot=replace(profile(), vision=False))
    assert caught.value.code == "local_unsupported_capability"


def test_unknown_does_not_trigger_extraction_but_pinned_type_keeps_prediction():
    chats = []

    async def handler(request):
        known = metadata(request)
        if known:
            return known
        chats.append(request)
        return httpx.Response(
            200,
            json=response(
                classification("unknown")
                if len(chats) == 1
                else payload()["fragments"][0]["fields"]
            ),
        )

    result = analyze(handler)
    assert not result.fragments[0].fields and len(chats) == 1
    chats.clear()
    result = analyze(
        handler, request=ModelRequest((source(method="native"),), DocumentType.property_document)
    )
    assert result.fragments[0].predicted_type == "unknown"
    assert result.fragments[0].effective_type == "property_document" and len(chats) == 2


def test_selected_local_factory_ignores_remote_settings(monkeypatch):
    from app.runtime import container

    calls = []

    async def handler(request):
        calls.append(request.url.path)
        known = metadata(request)
        assert known is not None
        return known

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            original = OllamaClient
            monkeypatch.setattr(
                container,
                "OllamaClient",
                lambda base_url, **kwargs: original(base_url, client=http, **kwargs),
            )
            monkeypatch.setattr(
                container,
                "build_qwen_provider",
                lambda settings: pytest.fail("No remote client in local mode"),
            )
            settings = Settings(
                _env_file=None,
                local_base_url="http://127.0.0.1:11439",
                local_model=MODEL,
                qwen_base_url="unusable",
                olmocr_base_url="unusable",
                ilons_api_key="",
                olmocr_api_token="",
            )
            async with await container.build_document_model(settings) as provider:
                assert (
                    provider.profile.provider == "local" and provider.profile.model_digest == DIGEST
                )

    asyncio.run(run())
    assert calls == ["/api/version", "/api/tags", "/api/show"]


@pytest.mark.parametrize(
    "url",
    [
        "https://llm.ilons.ru",
        "http://user:password@localhost:11434",
        "http://localhost:11434?key=secret",
    ],
)
def test_local_service_never_targets_public_provider_or_embedded_credentials(url):
    with pytest.raises(ValueError):
        OllamaClient(url, timeout_seconds=300, max_response_bytes=1000)


def test_total_timeout_response_limit_and_context_limit_do_not_retry():
    chats = []

    async def handler(request):
        known = metadata(request)
        if known:
            return known
        chats.append(request)
        await asyncio.sleep(0.05)
        return httpx.Response(200, json=response(classification()))

    with pytest.raises(LocalModelFailure) as caught:
        analyze(handler, snapshot=replace(profile(), timeout_seconds=0.01))
    assert caught.value.code == "local_timeout" and caught.value.retryable
    assert len(chats) == 1
    chats.clear()
    with pytest.raises(LocalModelFailure) as caught:
        analyze(handler, snapshot=replace(profile(), context_window_size=2049))
    assert caught.value.code == "local_context_too_large" and not chats

    async def oversized(request):
        return httpx.Response(200, json={"value": "x" * 100})

    with pytest.raises(LocalModelFailure) as caught:
        analyze(oversized, snapshot=replace(profile(), max_response_bytes=10))
    assert caught.value.code == "local_response_too_large" and not caught.value.retryable


def test_empty_visual_transcript_is_unknown_and_never_triggers_remote_ocr():
    chats = []
    image = replace(
        source(method="native"),
        text="",
        extraction_method="vision",
        image=b"\x01",
        media_type="image/jpeg",
    )

    async def handler(request):
        known = metadata(request)
        if known:
            return known
        chats.append(request)
        return httpx.Response(200, json=response({"text": " "}))

    with pytest.raises(LocalModelFailure) as caught:
        analyze(handler, request=ModelRequest((image,)))
    assert caught.value.code == "local_empty_transcript" and not caught.value.retryable
    assert len(chats) == 1 and chats[0].url.path == "/api/chat"


def test_qwen_rejects_image_without_any_http_call():
    from test_qwen import analyze as qwen_analyze

    from app.modules.recognition.model import ModelFailure

    image = replace(
        source(method="native"),
        text="",
        extraction_method="vision",
        image=b"\x01",
        media_type="image/png",
    )

    async def handler(request):
        pytest.fail("Qwen text adapter must reject vision input locally")

    with pytest.raises(ModelFailure) as caught:
        qwen_analyze(handler, request=ModelRequest((image,)))
    assert caught.value.code == "qwen_unsupported_capability" and caught.value.provider == "qwen"


def test_unlabelled_number_from_certificate_is_not_an_applicant_inn():
    from test_qwen import raw

    from app.modules.recognition.validation import validate_extraction

    value = payload(applicant_inn=raw("1234567890"))
    prepared = source("61:01:1234567:8 123,45 сертификат 1234567890", method="native")
    _, fragments = validate_extraction(json.dumps(value), ModelRequest((prepared,)), uuid4())
    observation = next(f for f in fragments[0].fields if f.field_id == "applicant_inn")
    assert observation.normalized is None and observation.known_state == "unreadable"
    assert observation.subject_role == "unknown" and observation.raw == "1234567890"
    assert observation.evidence


def test_cpu_image_preparation_bounds_size_and_preserves_original_provenance():
    from io import BytesIO

    from PIL import Image
    from test_ocr_contract import prepared_page

    from app.modules.assets.local_preparation import prepare_local_image

    # Bare pixels for the format adapter; no synthetic document or model quality sample.
    stream = BytesIO()
    with Image.new("RGBA", (1024, 512), (0, 0, 0, 0)) as pixels:
        pixels.save(stream, format="PNG")
    original = prepared_page(data=stream.getvalue())
    transformed = prepare_local_image(original, max_side=256)
    assert transformed.source == original.source and transformed.page == original.page
    assert original.data == stream.getvalue() and transformed.media_type == "image/png"
    assert "max-side-256" in transformed.preparation_profile
    with Image.open(BytesIO(transformed.data)) as result:
        assert result.size == (256, 128) and result.getpixel((0, 0)) == (255, 255, 255)


def test_corrupt_cpu_image_is_rejected_before_any_model_call():
    from test_ocr_contract import prepared_page

    from app.modules.assets.local_preparation import prepare_local_image
    from app.modules.assets.ocr import PreparationFailure

    with pytest.raises(PreparationFailure) as caught:
        prepare_local_image(prepared_page(), max_side=1280)
    assert caught.value.code == "preparation_unsupported_input" and not caught.value.retryable
