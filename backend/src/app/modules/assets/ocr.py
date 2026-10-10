"""M03 OCR contracts: prepared page in, immutable derived text out."""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from hashlib import sha256
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class OcrSource:
    file_id: UUID
    file_version_id: UUID
    original_blob_id: UUID
    original_sha256: str


@dataclass(frozen=True)
class PreparedOcrPage:
    source: OcrSource
    page: int
    media_type: str
    preparation_profile: str
    data: bytes = field(repr=False)

    def __post_init__(self):
        if self.page < 1 or not self.preparation_profile or not self.data:
            raise ValueError("OCR requires a nonempty, addressed, prepared page")

    @property
    def sha256(self) -> str:
        return sha256(self.data).hexdigest()


@dataclass(frozen=True)
class OcrProfile:
    base_url: str
    configuration_revision: str
    model: str | None = None
    service_revision: str | None = None
    layout: bool | None = None
    provider: Literal["olmocr"] = "olmocr"
    protocol_version: str = "multipart-text-v1"

    @property
    def fingerprint(self) -> str:
        serialized = json.dumps(asdict(self), sort_keys=True, separators=(",", ":"))
        return sha256(serialized.encode()).hexdigest()


@dataclass(frozen=True)
class OcrCacheKey:
    file_version_id: UUID
    original_sha256: str
    page: int
    preparation_profile: str
    ocr_profile_fingerprint: str

    @classmethod
    def for_page(cls, page: PreparedOcrPage, profile: OcrProfile):
        return cls(
            page.source.file_version_id,
            page.source.original_sha256,
            page.page,
            page.preparation_profile,
            profile.fingerprint,
        )

    @property
    def fingerprint(self) -> str:
        values = {**asdict(self), "file_version_id": str(self.file_version_id)}
        return sha256(
            json.dumps(values, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()


@dataclass(frozen=True)
class OcrText:
    text: str = field(repr=False)
    content_type: str
    duration_ms: int
    correlation_id: UUID
    service_request_id: UUID | None = None


@dataclass(frozen=True)
class OcrResult:
    id: UUID
    source: OcrSource
    page: int
    preparation_profile: str
    prepared_sha256: str
    prepared_blob_id: UUID
    profile: OcrProfile
    output: OcrText
    created_at: datetime


class OcrFailure(Exception):
    """Safe, stage-specific failure. No response body, token or document is retained."""

    stage = "ocr"
    provider = "olmocr"

    def __init__(
        self,
        code: str,
        correlation_id: UUID,
        *,
        retryable: bool = False,
        status: int | None = None,
        retry_after_seconds: float | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.correlation_id = correlation_id
        self.retryable = retryable
        self.status = status
        self.retry_after_seconds = retry_after_seconds


class OcrSourceConflict(Exception):
    pass


class PreparationFailure(OcrFailure):
    stage = "preparing"
    provider = None


class OcrPort(Protocol):
    async def healthcheck(self, correlation_id: UUID) -> OcrProfile: ...

    async def recognize(
        self, page: PreparedOcrPage, profile: OcrProfile, correlation_id: UUID
    ) -> OcrText: ...


class OcrResultStore(Protocol):
    def find(self, page: PreparedOcrPage, profile: OcrProfile) -> OcrResult | None: ...

    def save(self, page: PreparedOcrPage, profile: OcrProfile, output: OcrText) -> OcrResult: ...
