import asyncio
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from time import monotonic
from urllib.parse import urlsplit
from uuid import UUID

import httpx

from app.modules.assets.ocr import OcrFailure, OcrProfile, OcrText, PreparedOcrPage

ALLOWED_MEDIA = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}


def retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        seconds = float(value)
        if 0 <= seconds < float("inf"):
            return seconds
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return max(0.0, (when - datetime.now(UTC)).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


class OlmOcrClient:
    """One HTTP attempt. Retry scheduling and heartbeat belong to M11, not this adapter."""

    def __init__(
        self,
        base_url: str,
        *,
        token: str = "",
        timeout_seconds: float = 300,
        configuration_revision: str = "1",
        max_input_bytes: int = 50_000_000,
        client: httpx.AsyncClient | None = None,
    ):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OCR base URL must not contain credentials or query parameters")
        if timeout_seconds <= 0 or max_input_bytes <= 0 or not configuration_revision:
            raise ValueError("OCR limits and profile revision must be positive/nonempty")
        self.base_url = base_url.rstrip("/")
        self._token = token
        self.timeout_seconds = timeout_seconds
        self.configuration_revision = configuration_revision
        self.max_input_bytes = max_input_bytes
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(follow_redirects=False, trust_env=False)

    async def aclose(self):
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.aclose()

    async def _request(self, method: str, path: str, correlation_id: UUID, **kwargs):
        headers = {"X-Correlation-ID": str(correlation_id)}
        if self._token:
            headers["x-api-token"] = self._token
        try:
            # HTTPX timeouts bound network inactivity; this also bounds total elapsed request time.
            async with asyncio.timeout(self.timeout_seconds):
                response = await self._client.request(
                    method,
                    self.base_url + path,
                    headers=headers,
                    timeout=httpx.Timeout(
                        self.timeout_seconds, connect=min(10, self.timeout_seconds)
                    ),
                    follow_redirects=False,
                    **kwargs,
                )
        except (httpx.TimeoutException, TimeoutError):
            raise OcrFailure("ocr_timeout", correlation_id, retryable=True) from None
        except httpx.RequestError:
            raise OcrFailure("ocr_network_error", correlation_id, retryable=True) from None
        if 200 <= response.status_code < 300:
            return response
        status = response.status_code
        if status in {401, 403}:
            code = "ocr_auth_error"
        elif status == 429:
            code = "ocr_rate_limited"
        elif status >= 500:
            code = "ocr_service_error"
        elif status == 413:
            code = "ocr_input_too_large"
        else:
            code = "ocr_unsupported_input" if status in {400, 415, 422} else "ocr_invalid_response"
        raise OcrFailure(
            code,
            correlation_id,
            retryable=status == 429 or status >= 500,
            status=status,
            retry_after_seconds=retry_after(response.headers.get("Retry-After"))
            if status == 429 or status >= 500
            else None,
        )

    async def healthcheck(self, correlation_id: UUID) -> OcrProfile:
        response = await self._request("GET", "/health", correlation_id)
        try:
            body = response.json()
        except ValueError:
            raise OcrFailure("ocr_invalid_response", correlation_id) from None
        if not isinstance(body, dict) or body.get("status") != "ok":
            raise OcrFailure("ocr_invalid_response", correlation_id)
        # Only allow declared metadata. Extra fields or secrets returned by a service are discarded.
        model = body.get("model")
        revision = body.get("version")
        return OcrProfile(
            base_url=self.base_url,
            configuration_revision=self.configuration_revision,
            model=model if isinstance(model, str) and 0 < len(model) <= 200 else None,
            service_revision=revision
            if isinstance(revision, str) and 0 < len(revision) <= 100
            else None,
            layout=body.get("layout") if type(body.get("layout")) is bool else None,
        )

    async def recognize(
        self, page: PreparedOcrPage, profile: OcrProfile, correlation_id: UUID
    ) -> OcrText:
        extension = ALLOWED_MEDIA.get(page.media_type)
        if not extension:
            raise OcrFailure("ocr_unsupported_input", correlation_id)
        if len(page.data) > self.max_input_bytes:
            raise OcrFailure("ocr_input_too_large", correlation_id)
        if (
            profile.base_url != self.base_url
            or profile.configuration_revision != self.configuration_revision
        ):
            raise OcrFailure("ocr_profile_mismatch", correlation_id)
        started = monotonic()
        response = await self._request(
            "POST",
            "/ocr",
            correlation_id,
            files={"file": (f"page-{page.page}.{extension}", page.data, page.media_type)},
        )
        content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower().strip()
        if content_type not in {"text/plain", "text/markdown"}:
            raise OcrFailure("ocr_invalid_response", correlation_id)
        text = response.text
        if not text.strip():
            raise OcrFailure("ocr_empty_result", correlation_id)
        service_id = response.headers.get("X-Request-ID") or response.headers.get(
            "X-Correlation-ID"
        )
        try:
            service_id = UUID(service_id) if service_id else None
        except ValueError:
            service_id = None
        return OcrText(
            text=text,
            content_type=content_type,
            duration_ms=round((monotonic() - started) * 1000),
            correlation_id=correlation_id,
            service_request_id=service_id,
        )
