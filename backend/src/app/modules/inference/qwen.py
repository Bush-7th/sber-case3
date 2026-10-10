"""M06 Qwen adapter for the subset verified against llm.ilons.ru on 2026-10-10."""

import asyncio
import json
import re
from dataclasses import replace
from hashlib import sha256
from importlib.resources import files
from time import monotonic
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx
from pydantic import SecretStr

from app.modules.inference.olmocr import retry_after
from app.modules.recognition.model import (
    ModelAnalysis,
    ModelFailure,
    ModelInvocation,
    ModelRequest,
    PinnedModelProfile,
    extraction_schema,
    schema_hash,
)
from app.modules.recognition.validation import strict_json, validate_extraction

PROMPT_VERSION = "extract-v1"


class QwenFailure(ModelFailure):
    provider = "qwen"


def prompt_text() -> str:
    return files("app.modules.inference").joinpath("prompts/extract-v1.txt").read_text("utf-8")


def prompt_hash() -> str:
    return sha256(prompt_text().encode()).hexdigest()


class QwenProvider:
    """One asynchronous attempt; queue owns retry/backoff/heartbeat and publication fences."""

    def __init__(
        self,
        profile: PinnedModelProfile,
        *,
        key: str,
        auth_header: str,
        auth_scheme: str,
        client: httpx.AsyncClient | None = None,
    ):
        parsed = urlsplit(profile.base_url)
        path = urlsplit(profile.generation_path)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("Invalid Qwen base URL")
        if (
            not profile.generation_path.startswith("/")
            or path.netloc
            or path.query
            or path.fragment
            or "\r" in profile.generation_path
            or "\n" in profile.generation_path
        ):
            raise ValueError("Qwen generation path must stay on the configured service")
        if (
            not key
            or not re.fullmatch(r"[A-Za-z0-9-]+", auth_header)
            or any(c in key + auth_scheme for c in "\r\n")
            or auth_header.lower() in {"host", "content-length", "content-type", "x-correlation-id"}
        ):
            raise ValueError("Invalid Qwen authentication configuration")
        if (
            profile.provider != "external"
            or profile.api_format != "openai-chat"
            or profile.prompt_version != PROMPT_VERSION
            or profile.prompt_hash != prompt_hash()
            or profile.schema_hash != schema_hash()
        ):
            raise ValueError("Unsupported Qwen format/prompt/schema profile")
        if any(
            value <= 0
            for value in (
                profile.timeout_seconds,
                profile.max_output_tokens,
                profile.context_window_size,
                profile.max_input_bytes,
                profile.max_response_bytes,
            )
        ):
            raise ValueError("Qwen limits must be positive")
        self._profile = profile
        self._key = SecretStr(key)
        self._auth_header = auth_header
        self._auth_scheme = auth_scheme
        self._prompt = prompt_text()
        self._schema = extraction_schema()
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(follow_redirects=False, trust_env=False)

    @property
    def profile(self) -> PinnedModelProfile:
        return self._profile

    async def aclose(self):
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()

    async def _request(self, method: str, path: str, correlation_id: UUID, *, body=None):
        secret = self._key.get_secret_value()
        headers = {
            self._auth_header: f"{self._auth_scheme} {secret}".strip(),
            "X-Correlation-ID": str(correlation_id),
            "Accept": "application/json",
        }
        try:
            async with asyncio.timeout(self.profile.timeout_seconds):
                async with self._client.stream(
                    method,
                    self.profile.base_url.rstrip("/") + path,
                    headers=headers,
                    json=body,
                    timeout=httpx.Timeout(
                        self.profile.timeout_seconds, connect=min(10, self.profile.timeout_seconds)
                    ),
                    follow_redirects=False,
                ) as response:
                    status = response.status_code
                    if not 200 <= status < 300:
                        code = (
                            "qwen_auth_error"
                            if status in {401, 403}
                            else "qwen_rate_limited"
                            if status == 429
                            else "qwen_service_error"
                            if status >= 500
                            else "qwen_input_too_large"
                            if status == 413
                            else "qwen_unsupported_input"
                            if status in {400, 415, 422}
                            else "qwen_invalid_response"
                        )
                        retryable = status == 429 or status >= 500
                        raise QwenFailure(
                            code,
                            correlation_id,
                            status=status,
                            retryable=retryable,
                            retry_after_seconds=retry_after(response.headers.get("Retry-After"))
                            if retryable
                            else None,
                        )
                    media = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
                    if media.strip() != "application/json":
                        raise QwenFailure("qwen_invalid_response", correlation_id)
                    chunks, size = [], 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > self.profile.max_response_bytes:
                            raise QwenFailure("qwen_response_too_large", correlation_id)
                        chunks.append(chunk)
                    data = strict_json(b"".join(chunks).decode("utf-8"))
                    if not isinstance(data, dict):
                        raise ValueError("Invalid envelope")
                    return data
        except (httpx.TimeoutException, TimeoutError):
            raise QwenFailure("qwen_timeout", correlation_id, retryable=True) from None
        except httpx.RequestError:
            raise QwenFailure("qwen_network_error", correlation_id, retryable=True) from None
        except (ValueError, UnicodeError, RecursionError):
            raise QwenFailure("qwen_invalid_response", correlation_id) from None

    async def available_models(self, correlation_id: UUID) -> tuple[str, ...]:
        data = await self._request("GET", "/v1/models", correlation_id)
        items = data.get("data")
        if not isinstance(items, list) or any(
            not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in items
        ):
            raise QwenFailure("qwen_invalid_response", correlation_id)
        return tuple(item["id"] for item in items)

    async def analyze(
        self, request: ModelRequest, profile: PinnedModelProfile, correlation_id: UUID
    ) -> ModelAnalysis:
        if profile != self.profile:
            raise QwenFailure("qwen_profile_mismatch", correlation_id)
        if any(s.extraction_method == "vision" or s.image is not None for s in request.sources):
            raise QwenFailure("qwen_unsupported_capability", correlation_id)
        request = ModelRequest(
            tuple(replace(s, location=s.location.model_copy(deep=True)) for s in request.sources),
            request.forced_type,
        )
        user_input = json.dumps(
            {
                "forced_type": request.forced_type.value if request.forced_type else None,
                "sources": [{"source_id": s.id, "content": s.text} for s in request.sources],
            },
            ensure_ascii=False,
        )
        system = self._prompt + "\nJSON Schema:\n" + json.dumps(self._schema, ensure_ascii=False)
        if len((system + user_input).encode()) > profile.max_input_bytes:
            raise QwenFailure("qwen_input_too_large", correlation_id)
        body = {
            "model": profile.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_input},
            ],
            "temperature": 0,
            "max_tokens": profile.max_output_tokens,
            "stream": False,
            # Verified with this service. This requests JSON syntax; M05 validates the schema.
            "response_format": {"type": "json_object"},
        }
        started = monotonic()
        data = await self._request("POST", profile.generation_path, correlation_id, body=body)
        try:
            if data.get("model") != profile.model:
                raise ValueError("Unexpected model")
            choices = data["choices"]
            if not isinstance(choices, list) or len(choices) != 1:
                raise ValueError("Invalid choices")
            choice = choices[0]
            if not isinstance(choice, dict) or choice.get("finish_reason") != "stop":
                raise ValueError("Incomplete generation")
            message = choice["message"]
            if (
                not isinstance(message, dict)
                or message.get("role") != "assistant"
                or message.get("tool_calls")
                or message.get("refusal")
            ):
                raise ValueError("Unsupported model message")
            content = message["content"]
            if not isinstance(content, str) or not content.strip():
                raise ValueError("Empty generation")
        except (KeyError, TypeError, ValueError):
            raise QwenFailure(
                "qwen_invalid_model_output", correlation_id, stage="validating"
            ) from None
        try:
            payload, fragments = validate_extraction(content, request, correlation_id)
        except ModelFailure as exc:
            raise QwenFailure(
                "qwen_invalid_model_output", correlation_id, stage="validating", reason=exc.reason
            ) from None
        service_id = data.get("id")
        if not isinstance(service_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", service_id):
            service_id = None
        invocation = ModelInvocation(
            uuid4(),
            correlation_id,
            profile,
            round((monotonic() - started) * 1000),
            sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            sha256(content.encode()).hexdigest(),
            service_id,
            tuple(sorted({s.preparation_profile for s in request.sources})),
        )
        return ModelAnalysis(fragments, invocation, payload)
