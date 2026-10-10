"""M06 local-only CPU inference; no remote OCR, credentials or fallback."""

import asyncio
import base64
import ipaddress
import json
import re
from dataclasses import dataclass, replace
from hashlib import sha256
from importlib.resources import files
from time import monotonic
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from pydantic import ValidationError

from app.modules.inference.olmocr import retry_after
from app.modules.recognition.model import (
    FIELD_MODELS,
    ClassificationPayload,
    LocalModelProfile,
    ModelAnalysis,
    ModelCall,
    ModelFailure,
    ModelInvocation,
    ModelRequest,
    PinnedModelProfile,
    VisualTranscript,
    local_schema_hash,
)
from app.modules.recognition.validation import strict_json, validate_extraction, verify_quote

PROMPT_VERSION = "ollama-stages-v1"
PROMPT_FILES = (
    "local-transcribe-v1.txt",
    "local-classify-v1.txt",
    "local-extract-v1.txt",
    "local-fields-v1.json",
)


def load_prompt(name: str) -> str:
    return files("app.modules.inference").joinpath("prompts", name).read_text("utf-8")


def local_prompt_hash() -> str:
    return sha256(
        json.dumps({name: load_prompt(name) for name in PROMPT_FILES}, sort_keys=True).encode()
    ).hexdigest()


class LocalModelFailure(ModelFailure):
    provider = "ollama"


@dataclass(frozen=True)
class LocalModelInfo:
    model: str
    digest: str
    server_version: str
    vision: bool


class OllamaClient:
    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float,
        max_response_bytes: int,
        client: httpx.AsyncClient | None = None,
    ):
        parsed = urlsplit(base_url)
        try:
            private_host = ipaddress.ip_address(parsed.hostname or "").is_private
        except ValueError:
            private_host = parsed.hostname in {"localhost", "ollama"}
        if (
            parsed.scheme not in {"http", "https"}
            or not private_host
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Ollama requires a local/private service URL without credentials")
        if timeout_seconds <= 0 or max_response_bytes <= 0:
            raise ValueError("Local limits must be positive")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_response_bytes = max_response_bytes
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(follow_redirects=False, trust_env=False)

    async def aclose(self):
        if self._owns_client:
            await self._client.aclose()

    async def request(self, method, path, correlation_id: UUID, *, body=None):
        try:
            async with asyncio.timeout(self.timeout_seconds):
                async with self._client.stream(
                    method,
                    self.base_url + path,
                    json=body,
                    headers={"X-Correlation-ID": str(correlation_id), "Accept": "application/json"},
                    timeout=httpx.Timeout(
                        self.timeout_seconds, connect=min(10, self.timeout_seconds)
                    ),
                    follow_redirects=False,
                ) as response:
                    status = response.status_code
                    if not 200 <= status < 300:
                        code = (
                            "local_auth_error"
                            if status in {401, 403}
                            else "local_model_missing"
                            if status == 404
                            else "local_rate_limited"
                            if status == 429
                            else "local_service_error"
                            if status >= 500
                            else "local_input_too_large"
                            if status == 413
                            else "local_unsupported_input"
                            if status in {400, 415, 422}
                            else "local_invalid_response"
                        )
                        retryable = status == 429 or status >= 500
                        raise LocalModelFailure(
                            code,
                            correlation_id,
                            status=status,
                            retryable=retryable,
                            retry_after_seconds=retry_after(response.headers.get("Retry-After"))
                            if retryable
                            else None,
                        )
                    media = (
                        response.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                    )
                    if media != "application/json":
                        raise LocalModelFailure("local_invalid_response", correlation_id)
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > self.max_response_bytes:
                            raise LocalModelFailure("local_response_too_large", correlation_id)
                        chunks.append(chunk)
                    data = strict_json(b"".join(chunks).decode("utf-8"))
                    if not isinstance(data, dict) or "error" in data:
                        raise LocalModelFailure("local_invalid_response", correlation_id)
                    return data
        except (httpx.TimeoutException, TimeoutError):
            raise LocalModelFailure("local_timeout", correlation_id, retryable=True) from None
        except httpx.RequestError:
            raise LocalModelFailure("local_network_error", correlation_id, retryable=True) from None
        except (ValueError, UnicodeError, RecursionError):
            raise LocalModelFailure("local_invalid_response", correlation_id) from None

    async def inspect_model(
        self, model: str, correlation_id: UUID, expected_digest: str | None = None
    ) -> LocalModelInfo:
        if not model or "cloud" in model.lower():
            raise LocalModelFailure("local_cloud_model_forbidden", correlation_id)
        version = await self.request("GET", "/api/version", correlation_id)
        tags = await self.request("GET", "/api/tags", correlation_id)
        items = tags.get("models")
        if not isinstance(items, list):
            raise LocalModelFailure("local_invalid_response", correlation_id)
        matching = [item for item in items if isinstance(item, dict) and item.get("name") == model]
        if len(matching) != 1:
            raise LocalModelFailure("local_model_missing", correlation_id)
        tag = matching[0]
        if tag.get("remote_model") or tag.get("remote_host"):
            raise LocalModelFailure("local_cloud_model_forbidden", correlation_id)
        digest = tag.get("digest")
        if isinstance(digest, str) and re.fullmatch(r"[a-f0-9]{64}", digest):
            digest = "sha256:" + digest
        if not isinstance(digest, str) or not re.fullmatch(r"sha256:[a-f0-9]{64}", digest):
            raise LocalModelFailure("local_invalid_response", correlation_id)
        if expected_digest is not None and digest != expected_digest:
            raise LocalModelFailure("local_profile_mismatch", correlation_id)
        shown = await self.request("POST", "/api/show", correlation_id, body={"model": model})
        if shown.get("remote_model") or shown.get("remote_host"):
            raise LocalModelFailure("local_cloud_model_forbidden", correlation_id)
        capabilities = shown.get("capabilities")
        if not isinstance(capabilities, list) or "completion" not in capabilities:
            raise LocalModelFailure("local_unsupported_capability", correlation_id)
        server = version.get("version")
        if not isinstance(server, str) or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", server):
            raise LocalModelFailure("local_invalid_response", correlation_id)
        if model.startswith("qwen3-vl:") and tuple(map(int, server.split("."))) < (0, 12, 7):
            raise LocalModelFailure("local_unsupported_capability", correlation_id,
                                    reason="unsupported_server_version")
        return LocalModelInfo(model, digest, server, "vision" in capabilities)


class OllamaProvider:
    def __init__(self, profile: LocalModelProfile, client: OllamaClient):
        if (
            profile.provider != "local"
            or profile.api_format != "ollama-chat"
            or profile.generation_path != "/api/chat"
            or profile.prompt_version != PROMPT_VERSION
            or profile.prompt_hash != local_prompt_hash()
            or profile.schema_hash != local_schema_hash()
            or profile.base_url.rstrip("/") != client.base_url
            or profile.timeout_seconds != client.timeout_seconds
            or profile.max_response_bytes != client.max_response_bytes
            or profile.num_threads < 1
            or profile.max_output_tokens < 1
            or profile.context_window_size <= profile.max_output_tokens
            or profile.keep_alive_seconds < 0
            or profile.max_input_bytes < 1
        ):
            raise ValueError("Invalid pinned local profile")
        self._profile = profile
        self._client = client
        self._prompts = {name: load_prompt(name) for name in PROMPT_FILES}
        self._field_meanings = strict_json(self._prompts[PROMPT_FILES[3]])

    @property
    def profile(self) -> LocalModelProfile:
        return self._profile

    async def aclose(self):
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()

    async def _check_model(self, correlation_id):
        info = await self._client.inspect_model(
            self.profile.model, correlation_id, self.profile.model_digest
        )
        if info.server_version != self.profile.server_version or info.vision != self.profile.vision:
            raise LocalModelFailure("local_profile_mismatch", correlation_id)

    async def _chat(self, stage, prompt, schema, sources, correlation_id, *, images=None):
        system = prompt + "\nJSON Schema:\n" + json.dumps(schema, ensure_ascii=False)
        text = json.dumps(sources, ensure_ascii=False)
        messages = [{"role": "system", "content": system}, {"role": "user", "content": text}]
        if images:
            messages[1]["images"] = [base64.b64encode(image).decode("ascii") for image in images]
        # UTF-8 bytes bound the token count conservatively; reserve extra context for image tokens.
        text_budget = self.profile.context_window_size - self.profile.max_output_tokens
        if images:
            text_budget -= 8192 * len(images)
        if len((system + text).encode()) > text_budget:
            raise LocalModelFailure("local_context_too_large", correlation_id)
        body = {
            "model": self.profile.model,
            "messages": messages,
            "stream": False,
            "format": schema,
            "think": False,
            "keep_alive": self.profile.keep_alive_seconds,
            "options": {
                "temperature": 0,
                "seed": 0,
                "num_gpu": 0,
                "num_thread": self.profile.num_threads,
                "num_ctx": self.profile.context_window_size,
                "num_predict": self.profile.max_output_tokens,
            },
        }
        encoded = json.dumps(body, sort_keys=True, ensure_ascii=False).encode()
        if len(encoded) > self.profile.max_input_bytes:
            raise LocalModelFailure("local_input_too_large", correlation_id)
        started = monotonic()
        data = await self._client.request("POST", "/api/chat", correlation_id, body=body)
        message = data.get("message")
        if (
            data.get("model") != self.profile.model
            or data.get("done") is not True
            or data.get("done_reason") != "stop"
            or not isinstance(message, dict)
            or message.get("role") != "assistant"
            or message.get("tool_calls")
            or not isinstance(message.get("content"), str)
            or not message["content"].strip()
        ):
            raise LocalModelFailure(
                "local_invalid_model_output", correlation_id, stage="validating"
            )
        content = message["content"]
        call = ModelCall(
            stage,
            round((monotonic() - started) * 1000),
            sha256(encoded).hexdigest(),
            sha256(content.encode()).hexdigest(),
            data.get("prompt_eval_count") if type(data.get("prompt_eval_count")) is int else None,
            data.get("eval_count") if type(data.get("eval_count")) is int else None,
        )
        return content, call

    async def analyze(
        self, request: ModelRequest, profile: PinnedModelProfile, correlation_id: UUID
    ) -> ModelAnalysis:
        if profile != self.profile:
            raise LocalModelFailure("local_profile_mismatch", correlation_id)
        if any(s.image for s in request.sources) and not self.profile.vision:
            raise LocalModelFailure("local_unsupported_capability", correlation_id)
        request = ModelRequest(
            tuple(replace(s, location=s.location.model_copy(deep=True)) for s in request.sources),
            request.forced_type,
        )
        await self._check_model(correlation_id)
        started, calls, prepared = monotonic(), [], []
        try:
            for source in request.sources:
                source = replace(source, location=source.location.model_copy(deep=True))
                if source.extraction_method == "vision":
                    content, call = await self._chat(
                        "transcribing",
                        self._prompts[PROMPT_FILES[0]],
                        VisualTranscript.model_json_schema(),
                        {"source_id": source.id},
                        correlation_id,
                        images=[source.image],
                    )
                    calls.append(call)
                    transcript = VisualTranscript.model_validate(strict_json(content))
                    if not transcript.text.strip():
                        raise LocalModelFailure(
                            "local_empty_transcript", correlation_id, stage="validating"
                        )
                    source = replace(
                        source,
                        text=transcript.text,
                        preparation_profile=source.preparation_profile + "/local-transcribe-v1",
                    )
                prepared.append(source)
            request = ModelRequest(tuple(prepared), request.forced_type)
            content, call = await self._chat(
                "classifying",
                self._prompts[PROMPT_FILES[1]],
                ClassificationPayload.model_json_schema(),
                {"sources": [{"source_id": s.id, "content": s.text} for s in prepared]},
                correlation_id,
            )
            calls.append(call)
            classified = ClassificationPayload.model_validate(strict_json(content))
            available, covered = {s.id for s in prepared}, set()
            for fragment in classified.fragments:
                if not set(fragment.source_ids) <= available or len(
                    set(fragment.source_ids)
                ) != len(fragment.source_ids):
                    raise ValueError("Invalid classification sources")
                covered.update(fragment.source_ids)
                for q in fragment.classification_evidence:
                    verify_quote(q, request, fragment.source_ids)
            if covered != available:
                raise ValueError("Incomplete source coverage")
            fragments = []
            for fragment in classified.fragments:
                effective_type = (
                    request.forced_type.value if request.forced_type else fragment.predicted_type
                )
                fields = {}
                if effective_type != "unknown":
                    content, call = await self._chat(
                        "extracting",
                        self._prompts[PROMPT_FILES[2]]
                        + "\nСмысл полей:\n"
                        + json.dumps(self._field_meanings[effective_type], ensure_ascii=False),
                        FIELD_MODELS[effective_type].model_json_schema(),
                        {
                            "document_type": effective_type,
                            "sources": [
                                {"source_id": s.id, "content": s.text}
                                for s in prepared
                                if s.id in fragment.source_ids
                            ],
                        },
                        correlation_id,
                    )
                    calls.append(call)
                    fields = strict_json(content)
                fragments.append(
                    {**fragment.model_dump(), "document_type": effective_type, "fields": fields}
                )
            raw = json.dumps({"fragments": fragments}, ensure_ascii=False)
            payload, recognized = validate_extraction(raw, request, correlation_id)
        except ModelFailure as exc:
            if isinstance(exc, LocalModelFailure):
                raise
            raise LocalModelFailure(
                "local_invalid_model_output", correlation_id, stage="validating", reason=exc.reason
            ) from None
        except (ValueError, ValidationError, RecursionError):
            raise LocalModelFailure(
                "local_invalid_model_output", correlation_id, stage="validating"
            ) from None
        await self._check_model(correlation_id)
        invocation = ModelInvocation(
            uuid4(),
            correlation_id,
            self.profile,
            round((monotonic() - started) * 1000),
            sha256(json.dumps([c.input_sha256 for c in calls]).encode()).hexdigest(),
            sha256(raw.encode()).hexdigest(),
            preparation_profiles=tuple(sorted({s.preparation_profile for s in prepared})),
            calls=tuple(calls),
        )
        return ModelAnalysis(recognized, invocation, payload, tuple(prepared))

    async def running_model(self, correlation_id: UUID) -> dict | None:
        data = await self._client.request("GET", "/api/ps", correlation_id)
        items = data.get("models")
        if not isinstance(items, list):
            raise LocalModelFailure("local_invalid_response", correlation_id)
        for item in items:
            if isinstance(item, dict) and item.get("name") == self.profile.model:
                if any(
                    type(item.get(key)) is not int or item[key] < 0
                    for key in ("size", "size_vram", "context_length")
                ):
                    raise LocalModelFailure("local_invalid_response", correlation_id)
                return {
                    key: item.get(key) for key in ("digest", "size", "size_vram", "context_length")
                }
        return None

    async def unload(self, correlation_id: UUID):
        await self._client.request(
            "POST",
            "/api/generate",
            correlation_id,
            body={"model": self.profile.model, "keep_alive": 0},
        )
