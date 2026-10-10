"""HTTP/schema facts only, no synthetic documents or model-quality assertions from mocks."""

import asyncio
import json
from dataclasses import FrozenInstanceError, replace
from uuid import uuid4

import httpx
import pytest

from app.modules.inference.qwen import PROMPT_VERSION, QwenProvider, prompt_hash
from app.modules.recognition.facts import DocumentType, PageLocation, SheetLocation
from app.modules.recognition.model import (
    ExtractionPayload,
    ModelFailure,
    ModelRequest,
    PinnedModelProfile,
    PreparedSource,
    schema_hash,
)
from app.modules.recognition.validation import decimal_string, validate_extraction
from app.runtime.container import build_qwen_provider
from app.runtime.settings import ConfigurationError, Settings


def profile(**changes):
    return PinnedModelProfile(
        provider="external",
        base_url="https://llm.example",
        model="verified-model",
        generation_path="/v1/chat/completions",
        api_format="openai-chat",
        prompt_version=PROMPT_VERSION,
        prompt_hash=prompt_hash(),
        schema_hash=schema_hash(),
        timeout_seconds=300,
        max_output_tokens=8192,
        context_window_size=262000,
        max_input_bytes=750000,
        max_response_bytes=4000000,
        **changes,
    )


def source(text="61:01:1234567:8 123,45", *, method="ocr", id="source-1", location=None):
    return PreparedSource(
        id,
        location or PageLocation(kind="page", file_id=uuid4(), file_version_id=uuid4(), page=3),
        text,
        method,
        uuid4() if method == "ocr" else None,
    )


def quote(excerpt, id="source-1"):
    return {"source_id": id, "excerpt": excerpt}


def raw(value, id="source-1"):
    return {"raw": value, "evidence": [quote(value, id)]}


def payload(**fields):
    return {
        "fragments": [
            {
                "document_type": "property_document",
                "predicted_type": "property_document",
                "source_ids": ["source-1"],
                "classification_evidence": [quote("61:01:1234567:8")],
                "fields": {
                    "applicant_inn": None,
                    "cadastral_number": raw("61:01:1234567:8"),
                    "area": raw("123,45"),
                    "purpose": None,
                    "address": None,
                    **fields,
                },
            }
        ]
    }


def envelope(value=None, **changes):
    return {
        "id": "chatcmpl-test",
        "model": "verified-model",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(value or payload()),
                    "reasoning_content": "PRIVATE-REASONING",
                },
            }
        ],
        "secret": "DISCARD-ME",
        **changes,
    }


def analyze(handler, request=None, snapshot=None, supplied=None):
    snapshot = snapshot or profile()

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
            async with QwenProvider(
                snapshot,
                key="PRIVATE-KEY",
                auth_header="Authorization",
                auth_scheme="Bearer",
                client=http,
            ) as provider:
                return await provider.analyze(
                    request or ModelRequest((source(),)), supplied or snapshot, uuid4()
                )

    return asyncio.run(scenario())


def test_transport_schema_source_mapping_precision_and_secret_redaction(caplog):
    original = source()
    calls = []

    async def handler(request):
        calls.append(request)
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer PRIVATE-KEY"
        assert "x-api-token" not in request.headers
        assert request.extensions["timeout"]["read"] == 300
        body = json.loads(await request.aread())
        assert body["model"] == "verified-model" and body["stream"] is False
        assert body["max_tokens"] == 8192 and body["temperature"] == 0
        assert body["response_format"] == {"type": "json_object"}
        user = json.loads(body["messages"][1]["content"])
        assert user == {
            "forced_type": None,
            "sources": [{"source_id": original.id, "content": original.text}],
        }
        assert str(original.location.file_id) not in json.dumps(body)
        assert "PRIVATE-KEY" not in json.dumps(body)
        assert "JSON Schema" in body["messages"][0]["content"]
        return httpx.Response(200, json=envelope())

    result = analyze(handler, ModelRequest((original,)))
    fields = {f.field_id: f for f in result.fragments[0].fields}
    assert fields["area"].normalized == "123.45"
    assert fields["address"].normalized is None and fields["address"].known_state == "missing"
    ref = fields["area"].evidence[0]
    assert ref.location == original.location and ref.location.page == 3
    assert ref.location.bbox is None
    assert ref.ocr_result_id == original.ocr_result_id and ref.extraction_method == "ocr"
    assert result.invocation.profile == profile() and result.invocation.duration_ms >= 0
    assert len(result.invocation.input_sha256) == 64 and len(result.invocation.output_sha256) == 64
    assert result.invocation.service_request_id == "chatcmpl-test"
    assert len(calls) == 1
    output = repr(result) + caplog.text
    for secret in ("PRIVATE-KEY", "PRIVATE-REASONING", "DISCARD-ME", original.text):
        assert secret not in output


@pytest.mark.parametrize(
    "status,code,retryable",
    [
        (401, "qwen_auth_error", False),
        (403, "qwen_auth_error", False),
        (429, "qwen_rate_limited", True),
        (503, "qwen_service_error", True),
        (400, "qwen_unsupported_input", False),
        (413, "qwen_input_too_large", False),
        (422, "qwen_unsupported_input", False),
        (302, "qwen_invalid_response", False),
    ],
)
def test_errors_are_separate_from_ocr_safe_and_make_one_attempt(status, code, retryable):
    calls = []

    async def handler(request):
        calls.append(request)
        return httpx.Response(
            status,
            text="PRIVATE-BODY",
            headers={"Retry-After": "7", "Location": "https://untrusted.example"},
        )

    with pytest.raises(ModelFailure) as caught:
        analyze(handler)
    failure = caught.value
    assert failure.code == code and failure.provider == "qwen" and failure.stage == "extracting"
    assert failure.retryable is retryable and failure.status == status
    assert failure.retry_after_seconds == (7 if retryable else None)
    assert "PRIVATE" not in str(failure) + repr(failure)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "exception,code",
    [(httpx.ReadTimeout, "qwen_timeout"), (httpx.ConnectError, "qwen_network_error")],
)
def test_network_errors_are_safe_retryable(exception, code):
    async def handler(request):
        raise exception("PRIVATE-DRIVER-MESSAGE", request=request)

    with pytest.raises(ModelFailure) as caught:
        analyze(handler)
    assert caught.value.code == code and caught.value.retryable
    assert "PRIVATE" not in str(caught.value)


def test_total_deadline_and_response_size_limit():
    async def slow(request):
        await asyncio.sleep(0.05)
        return httpx.Response(200, json=envelope())

    with pytest.raises(ModelFailure) as caught:
        analyze(slow, snapshot=replace(profile(), timeout_seconds=0.01))
    assert caught.value.code == "qwen_timeout" and caught.value.retryable

    async def oversized(request):
        return httpx.Response(200, json=envelope())

    with pytest.raises(ModelFailure) as caught:
        analyze(oversized, snapshot=replace(profile(), max_response_bytes=10))
    assert caught.value.code == "qwen_response_too_large" and not caught.value.retryable


def test_profile_snapshot_and_input_limit_fail_before_http():
    async def handler(request):
        pytest.fail("Rejected locally")

    pinned = profile()
    with pytest.raises(FrozenInstanceError):
        pinned.model = "changed"
    for snapshot, supplied, code in (
        (pinned, replace(pinned, model="changed"), "qwen_profile_mismatch"),
        (replace(pinned, max_input_bytes=1), None, "qwen_input_too_large"),
    ):
        with pytest.raises(ModelFailure) as caught:
            analyze(handler, snapshot=snapshot, supplied=supplied)
        assert caught.value.code == code and not caught.value.retryable


@pytest.mark.parametrize(
    "mode",
    [
        "html",
        "empty",
        "truncated",
        "wrong_model",
        "tool",
        "fence",
        "prose",
        "duplicate",
        "nan",
        "null_response",
    ],
)
def test_invalid_success_is_never_a_valid_machine_result(mode):
    response = envelope()
    msg = response["choices"][0]["message"]
    if mode == "empty":
        msg["content"] = " "
    elif mode == "truncated":
        response["choices"][0]["finish_reason"] = "length"
    elif mode == "wrong_model":
        response["model"] = "silent-fallback"
    elif mode == "tool":
        msg["tool_calls"] = [{"name": "untrusted"}]
    elif mode == "fence":
        msg["content"] = "```json\n" + msg["content"] + "\n```"
    elif mode == "prose":
        msg["content"] = "Result: " + msg["content"]
    elif mode == "duplicate":
        msg["content"] = '{"fragments": [], "fragments": []}'
    elif mode == "nan":
        msg["content"] = '{"fragments": NaN}'
    elif mode == "null_response":
        msg["content"] = "null"

    async def handler(request):
        return (
            httpx.Response(200, text="<html>PRIVATE</html>", headers={"Content-Type": "text/html"})
            if mode == "html"
            else httpx.Response(200, json=response)
        )

    with pytest.raises(ModelFailure) as caught:
        analyze(handler)
    assert caught.value.code in {"qwen_invalid_model_output", "qwen_invalid_response"}
    assert not caught.value.retryable


@pytest.mark.parametrize(
    "mode",
    [
        "unknown_source",
        "invented_quote",
        "invented_raw",
        "invented_coordinates",
        "missing_key",
        "number_raw",
        "extra_field",
        "lost_source",
        "unrequested_override",
    ],
)
def test_schema_and_provenance_rejections(mode):
    content, request = payload(), ModelRequest((source(),))
    fragment = content["fragments"][0]
    if mode == "unknown_source":
        fragment["source_ids"] = ["unprovided"]
    elif mode == "invented_quote":
        fragment["fields"]["area"]["evidence"][0]["excerpt"] = "not in prepared content"
    elif mode == "invented_raw":
        fragment["fields"]["area"]["raw"] = "999"
    elif mode == "invented_coordinates":
        fragment["fields"]["area"]["evidence"][0]["bbox"] = [0, 0, 1, 1]
    elif mode == "missing_key":
        del fragment["fields"]["address"]
    elif mode == "number_raw":
        fragment["fields"]["area"]["raw"] = 123.45
    elif mode == "extra_field":
        fragment["fields"]["total_expenses"] = None
    elif mode == "lost_source":
        request = ModelRequest((source(), source(id="source-2")))
    elif mode == "unrequested_override":
        fragment["predicted_type"] = "bank_statement"
    with pytest.raises(ModelFailure) as caught:
        validate_extraction(json.dumps(content), request, uuid4())
    assert caught.value.stage == "validating" and not caught.value.retryable


def test_nullable_schemas_cover_eight_types_and_explicit_gims_extension():
    schema = ExtractionPayload.model_json_schema()
    mapping = schema["$defs"]["ApplicationFragment"]["properties"]["fields"]
    assert mapping["$ref"].endswith("ApplicationFields")
    types = {
        "application": "ApplicationFields",
        "consent": "ConsentFields",
        "certificate": "CertificateFields",
        "presentation": "PresentationFields",
        "cost_justification": "CostFields",
        "bank_statement": "BankFields",
        "property_document": "PropertyFields",
        "guarantee_letter": "GuaranteeFields",
        "gims_declaration": "GimsFields",
    }
    for kind, name in types.items():
        definition = schema["$defs"][name]
        assert set(definition["required"]) == set(definition["properties"])
        fragment = {
            "document_type": kind,
            "predicted_type": kind,
            "source_ids": ["source-1"],
            "classification_evidence": [quote("fact")],
            "fields": {key: None for key in definition["required"]},
        }
        _, results = validate_extraction(
            json.dumps({"fragments": [fragment]}), ModelRequest((source("fact"),)), uuid4()
        )
        assert all(f.known_state == "missing" and f.normalized is None for f in results[0].fields)
    assert "requested_subsidy_amount" in schema["$defs"]["CostFields"]["required"]


@pytest.mark.parametrize(
    "value,expected",
    [
        ("9 007 199 254 740 993,000000000000001", "9007199254740993.000000000000001"),
        ("00012.50", "12.50"),
        ("0", "0"),
        ("1\u00a0000,00", "1000.00"),
    ],
)
def test_decimal_normalization_preserves_precision(value, expected):
    assert decimal_string(value) == expected


def test_ambiguous_number_is_unreadable_not_zero_and_native_cells_remain_addressed():
    location = SheetLocation(
        kind="sheet", file_id=uuid4(), file_version_id=uuid4(), sheet="Actual", cell_range="B5"
    )
    prepared = source("61:01:1234567:8 1,234.56", method="native", location=location)
    _, fragments = validate_extraction(
        json.dumps(payload(area=raw("1,234.56"))), ModelRequest((prepared,)), uuid4()
    )
    field = next(v for v in fragments[0].fields if v.field_id == "area")
    assert field.known_state == "unreadable" and field.normalized is None
    assert field.raw == "1,234.56" and field.evidence[0].location.cell_range == "B5"
    assert (
        field.evidence[0].extraction_method == "native" and field.evidence[0].ocr_result_id is None
    )


def test_override_preserves_independent_prediction_and_reextracts_selected_schema():
    content = payload()
    content["fragments"][0]["predicted_type"] = "unknown"
    _, fragments = validate_extraction(
        json.dumps(content), ModelRequest((source(),), DocumentType.property_document), uuid4()
    )
    assert fragments[0].predicted_type == "unknown"
    assert fragments[0].effective_type == "property_document"


def test_unknown_content_is_explicit_and_has_no_facts():
    content = {
        "fragments": [
            {
                "document_type": "unknown",
                "predicted_type": "unknown",
                "source_ids": ["source-1"],
                "classification_evidence": [quote("fact")],
                "fields": {},
            }
        ]
    }
    _, fragments = validate_extraction(
        json.dumps(content), ModelRequest((source("fact"),)), uuid4()
    )
    assert fragments[0].effective_type == "unknown" and not fragments[0].fields


@pytest.mark.parametrize(
    "value,expected,state",
    [
        ("29.02.2024", "2024-02-29", "known"),
        ("2026-10-10", "2026-10-10", "known"),
        ("29.02.2025", None, "unreadable"),
        ("10/11/2026", None, "unreadable"),
        ("2026-W01-1", None, "unreadable"),
    ],
)
def test_dates_are_iso_and_ambiguous_or_invalid_values_are_unknown(value, expected, state):
    schema = ExtractionPayload.model_json_schema()["$defs"]["ConsentFields"]
    fields = {name: None for name in schema["required"]}
    fields["date"] = raw(value)
    fragment = {
        "document_type": "consent",
        "predicted_type": "consent",
        "source_ids": ["source-1"],
        "classification_evidence": [quote(value)],
        "fields": fields,
    }
    _, fragments = validate_extraction(
        json.dumps({"fragments": [fragment]}), ModelRequest((source(value),)), uuid4()
    )
    fact = next(f for f in fragments[0].fields if f.field_id == "date")
    assert fact.normalized == expected and fact.known_state == state


def test_cost_values_are_not_derived_and_expense_items_have_verified_sources():
    schema = ExtractionPayload.model_json_schema()["$defs"]["CostFields"]
    fields = {name: None for name in schema["required"]}
    fields.update(
        total_expenses=raw("1000,00"),
        own_funds=raw("500,00"),
        expense_items=[{"description": raw("item"), "amount": raw("1000,00")}],
    )
    fragment = {
        "document_type": "cost_justification",
        "predicted_type": "cost_justification",
        "source_ids": ["source-1"],
        "classification_evidence": [quote("item")],
        "fields": fields,
    }
    _, results = validate_extraction(
        json.dumps({"fragments": [fragment]}),
        ModelRequest((source("item 1000,00 500,00"),)),
        uuid4(),
    )
    facts = {f.field_id: f for f in results[0].fields}
    assert facts["total_expenses"].normalized == "1000.00"
    assert facts["own_funds"].normalized == "500.00"
    assert facts["requested_subsidy_amount"].normalized is None
    assert facts["requested_subsidy_amount"].known_state == "missing"
    assert facts["expense_items"].normalized[0].amount == "1000.00"
    assert facts["expense_items"].normalized[0].evidence


def test_multiple_sources_cannot_claim_unsupported_value_and_guarantor_is_separate():
    schema = ExtractionPayload.model_json_schema()["$defs"]["GuaranteeFields"]
    fields = {name: None for name in schema["required"]}
    fields["guarantor_inn"] = raw("1234567890")
    fields["applicant_inn"] = raw("0987654321", "source-2")
    fragment = {
        "document_type": "guarantee_letter",
        "predicted_type": "guarantee_letter",
        "source_ids": ["source-1", "source-2"],
        "classification_evidence": [quote("1234567890")],
        "fields": fields,
    }
    fields["applicant_inn"]["evidence"] = [quote("ИНН заявителя 0987654321", "source-2")]
    request = ModelRequest(
        (source("1234567890"), source("ИНН заявителя 0987654321", id="source-2"))
    )
    _, results = validate_extraction(json.dumps({"fragments": [fragment]}), request, uuid4())
    facts = {f.field_id: f for f in results[0].fields}
    assert facts["guarantor_inn"].subject_role == "guarantor"
    assert facts["applicant_inn"].subject_role == "applicant"
    assert facts["applicant_inn"].evidence[0].location == request.sources[1].location
    fields["guarantor_inn"]["evidence"].append(quote("0987654321", "source-2"))
    with pytest.raises(ModelFailure):
        validate_extraction(json.dumps({"fragments": [fragment]}), request, uuid4())


def test_html_table_projection_keeps_raw_ocr_and_quotes_visible_input():
    from app.modules.assets.text_projection import project_ocr_text

    # Bare cell/transport facts, not a synthetic document or OCR quality sample.
    html = "<table><tr><td>area</td><td>123,45</td></tr></table><script>hidden</script>"
    projection = project_ocr_text(html)
    assert " ".join(projection.text.split()) == "area 123,45"
    assert "hidden" not in projection.text
    assert projection.profile == "ocr-html-visible-text-v1"
    assert "<table>" in html  # Raw OCR is never modified by the projection.
    text = "plain &amp; literal"
    assert project_ocr_text(text).text == text
    assert project_ocr_text(text).profile == "ocr-text-identity-v1"
    assert projection.text not in repr(projection)


def test_source_metadata_snapshot_cannot_change_during_http():
    prepared = source()
    original_page = prepared.location.page

    async def handler(request):
        prepared.location.page = 99
        return httpx.Response(200, json=envelope())

    result = analyze(handler, ModelRequest((prepared,)))
    evidence = next(f for f in result.fragments[0].fields if f.field_id == "area").evidence[0]
    assert evidence.location.page == original_page


def test_qwen_cli_rejects_invalid_page_before_loading_source(monkeypatch):
    import sys

    from app.runtime.qwen_cli import main

    monkeypatch.setattr(sys, "argv", ["qwen_cli", "sample", str(uuid4()), "--page", "0"])
    with pytest.raises(SystemExit) as caught:
        main()
    assert caught.value.code == 2


def test_local_configuration_does_not_construct_or_require_qwen():
    settings = Settings(_env_file=None)
    assert settings.model_provider == "local"
    with pytest.raises(ConfigurationError):
        build_qwen_provider(settings)


@pytest.mark.parametrize(
    "changes",
    [
        {"generation_path": "//untrusted.example/path"},
        {"generation_path": "/path?key=leak"},
        {"api_format": "unverified-format"},
        {"schema_hash": "stale"},
        {"prompt_hash": "stale"},
    ],
)
def test_unverified_or_unsafe_configuration_is_rejected(changes):
    with pytest.raises(ValueError):
        QwenProvider(
            replace(profile(), **changes),
            key="secret",
            auth_header="Authorization",
            auth_scheme="Bearer",
        )
