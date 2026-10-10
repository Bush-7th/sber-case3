"""M05 model port and required, nullable extraction schemas. No HTTP/provider imports."""

import json
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Annotated, Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.modules.recognition.facts import DocumentType, FieldObservation, SourceLocation

DocumentKind = Literal[
    "application",
    "consent",
    "certificate",
    "presentation",
    "cost_justification",
    "bank_statement",
    "property_document",
    "guarantee_letter",
    "gims_declaration",
    "unknown",
]
Nonempty = Annotated[str, StringConstraints(min_length=1)]


class ModelDTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)


class Quote(ModelDTO):
    source_id: Nonempty
    excerpt: Nonempty = Field(repr=False)


class ExtractedValue(ModelDTO):
    # The model supplies the literal source string. Decimal/date normalization belongs to M05.
    raw: Nonempty = Field(repr=False)
    evidence: list[Quote] = Field(min_length=1, repr=False)


class CommonFields(ModelDTO):
    applicant_inn: ExtractedValue | None


class ApplicationFields(CommonFields):
    organization: ExtractedValue | None
    inn: ExtractedValue | None
    ogrn: ExtractedValue | None
    requested_amount: ExtractedValue | None
    date: ExtractedValue | None
    signatory: ExtractedValue | None


class ConsentFields(CommonFields):
    full_name: ExtractedValue | None
    passport_data: ExtractedValue | None
    date: ExtractedValue | None


class CertificateFields(CommonFields):
    number: ExtractedValue | None
    certifying_authority: ExtractedValue | None
    issue_date: ExtractedValue | None
    expiration_date: ExtractedValue | None


class PresentationFields(CommonFields):
    project_name: ExtractedValue | None
    short_description: ExtractedValue | None


class ExtractedExpense(ModelDTO):
    description: ExtractedValue
    amount: ExtractedValue | None


class CostFields(CommonFields):
    total_expenses: ExtractedValue | None
    own_funds: ExtractedValue | None
    requested_subsidy_amount: ExtractedValue | None
    expense_items: list[ExtractedExpense] | None


class BankFields(CommonFields):
    organization: ExtractedValue | None
    account_number: ExtractedValue | None
    balance: ExtractedValue | None
    date: ExtractedValue | None


class PropertyFields(CommonFields):
    cadastral_number: ExtractedValue | None
    area: ExtractedValue | None
    purpose: ExtractedValue | None
    address: ExtractedValue | None


class GuaranteeFields(CommonFields):
    organization: ExtractedValue | None
    guarantor_inn: ExtractedValue | None
    amount: ExtractedValue | None
    date: ExtractedValue | None
    signatory: ExtractedValue | None


class GimsFields(CommonFields):
    expiration_date: ExtractedValue | None


class FragmentBase(ModelDTO):
    predicted_type: DocumentKind
    source_ids: list[Nonempty] = Field(min_length=1)
    classification_evidence: list[Quote] = Field(min_length=1, repr=False)


class ApplicationFragment(FragmentBase):
    document_type: Literal["application"]
    fields: ApplicationFields = Field(repr=False)


class ConsentFragment(FragmentBase):
    document_type: Literal["consent"]
    fields: ConsentFields = Field(repr=False)


class CertificateFragment(FragmentBase):
    document_type: Literal["certificate"]
    fields: CertificateFields = Field(repr=False)


class PresentationFragment(FragmentBase):
    document_type: Literal["presentation"]
    fields: PresentationFields = Field(repr=False)


class CostFragment(FragmentBase):
    document_type: Literal["cost_justification"]
    fields: CostFields = Field(repr=False)


class BankFragment(FragmentBase):
    document_type: Literal["bank_statement"]
    fields: BankFields = Field(repr=False)


class PropertyFragment(FragmentBase):
    document_type: Literal["property_document"]
    fields: PropertyFields = Field(repr=False)


class GuaranteeFragment(FragmentBase):
    document_type: Literal["guarantee_letter"]
    fields: GuaranteeFields = Field(repr=False)


class GimsFragment(FragmentBase):
    document_type: Literal["gims_declaration"]
    fields: GimsFields = Field(repr=False)


class UnknownFragment(FragmentBase):
    document_type: Literal["unknown"]
    fields: dict[str, ExtractedValue] = Field(max_length=0, repr=False)


Fragment = Annotated[
    ApplicationFragment
    | ConsentFragment
    | CertificateFragment
    | PresentationFragment
    | CostFragment
    | BankFragment
    | PropertyFragment
    | GuaranteeFragment
    | GimsFragment
    | UnknownFragment,
    Field(discriminator="document_type"),
]


class ExtractionPayload(ModelDTO):
    fragments: list[Fragment] = Field(min_length=1, max_length=200)


def extraction_schema() -> dict:
    return ExtractionPayload.model_json_schema()


def schema_hash() -> str:
    return sha256(json.dumps(extraction_schema(), sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class PreparedSource:
    id: str
    location: SourceLocation
    text: str = field(repr=False)
    extraction_method: Literal["native", "ocr"] = "native"
    ocr_result_id: UUID | None = None
    preparation_profile: str = "native-text-v1"

    def __post_init__(self):
        if not self.id or not self.text.strip() or not self.preparation_profile:
            raise ValueError("Model source requires an ID and prepared text")
        if self.extraction_method not in {"native", "ocr"}:
            raise ValueError("Text model sources must be native or saved OCR")
        if (self.extraction_method == "ocr") != (self.ocr_result_id is not None):
            raise ValueError("OCR source must reference its saved result")


@dataclass(frozen=True)
class ModelRequest:
    sources: tuple[PreparedSource, ...] = field(repr=False)
    forced_type: DocumentType | None = None

    def __post_init__(self):
        if not self.sources or len({s.id for s in self.sources}) != len(self.sources):
            raise ValueError("Model request requires uniquely addressed sources")


@dataclass(frozen=True)
class PinnedModelProfile:
    provider: Literal["external", "local"]
    base_url: str
    model: str
    generation_path: str
    api_format: str
    prompt_version: str
    prompt_hash: str
    schema_hash: str
    timeout_seconds: float
    max_output_tokens: int
    context_window_size: int
    # Operational byte limits are distinct from the unverified model tokenizer/context capacity.
    max_input_bytes: int
    max_response_bytes: int


@dataclass(frozen=True)
class ModelInvocation:
    id: UUID
    correlation_id: UUID
    profile: PinnedModelProfile
    duration_ms: int
    input_sha256: str
    output_sha256: str
    service_request_id: str | None = None
    preparation_profiles: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecognizedFragment:
    predicted_type: str
    effective_type: str
    source_ids: tuple[str, ...]
    fields: tuple[FieldObservation, ...] = field(repr=False)


@dataclass(frozen=True)
class ModelAnalysis:
    fragments: tuple[RecognizedFragment, ...]
    invocation: ModelInvocation
    # Retain the validated machine response for immutable persistence by M05 in INT01.
    payload: ExtractionPayload = field(repr=False)


class ModelFailure(Exception):
    """Safe model-specific error; never retains request/response/credential contents."""

    provider = "model"

    def __init__(
        self,
        code: str,
        correlation_id: UUID,
        *,
        stage: str = "extracting",
        retryable: bool = False,
        status: int | None = None,
        retry_after_seconds: float | None = None,
        reason: str | None = None,
    ):
        super().__init__(code)
        self.code = code
        self.correlation_id = correlation_id
        self.stage = stage
        self.retryable = retryable
        self.status = status
        self.retry_after_seconds = retry_after_seconds
        self.reason = reason


class DocumentModelPort(Protocol):
    async def analyze(
        self, request: ModelRequest, profile: PinnedModelProfile, correlation_id: UUID
    ) -> ModelAnalysis: ...
