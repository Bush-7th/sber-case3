"""Public DTOs. They contain no ORM objects, provider secrets, or business execution."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    SecretStr,
    StrictBool,
    StringConstraints,
    TypeAdapter,
    model_validator,
)

DecimalString = Annotated[
    str, StringConstraints(strict=True, pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Revision = Annotated[int, Field(strict=True, ge=0)]
Count = Annotated[int, Field(strict=True, ge=0)]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Role(StrEnum):
    specialist = "specialist"
    administrator = "administrator"


class DocumentType(StrEnum):
    application = "application"
    consent = "consent"
    certificate = "certificate"
    presentation = "presentation"
    cost_justification = "cost_justification"
    bank_statement = "bank_statement"
    property_document = "property_document"
    guarantee_letter = "guarantee_letter"
    gims_declaration = "gims_declaration"


class FileFormat(StrEnum):
    pdf = "pdf"
    doc = "doc"
    docx = "docx"
    xls = "xls"
    xlsx = "xlsx"
    jpg = "jpg"
    png = "png"


class ProcessingStatus(StrEnum):
    accepted = "accepted"
    determining = "determining"
    checked = "checked"
    processing_error = "processing_error"


class ProcessingStage(StrEnum):
    preparing = "preparing"
    ocr = "ocr"
    extracting = "extracting"
    validating = "validating"


class RunStatus(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Coverage(StrEnum):
    partial = "partial"
    complete = "complete"


class Freshness(StrEnum):
    current = "current"
    outdated = "outdated"


class Verdict(StrEnum):
    passed = "pass"
    review_required = "review_required"
    issues = "issues"


class DecisionAction(StrEnum):
    accepted = "accepted"
    needs_revision = "needs_revision"
    rejected = "rejected"


class Severity(StrEnum):
    info = "info"
    warning = "warning"
    error = "error"


class SubjectRole(StrEnum):
    applicant = "applicant"
    guarantor = "guarantor"
    person = "person"
    unknown = "unknown"


class ApiError(DTO):
    code: NonEmptyString
    message: NonEmptyString
    details: dict[str, JsonValue] = Field(default_factory=dict)
    correlation_id: UUID


class UserSummary(DTO):
    id: UUID
    display_name: NonEmptyString
    role: Role


class SessionCreate(DTO):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    password: SecretStr


class SessionResponse(DTO):
    user: UserSummary
    expires_at: AwareDatetime
    csrf_token: NonEmptyString


class BoundingBox(DTO):
    """Coordinates relative to the indicated source/preview page, within [0, 1]."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside_page(self) -> BoundingBox:
        if self.x + self.width > 1 or self.y + self.height > 1:
            raise ValueError("Bounding box must stay inside the page")
        return self


class SourceBase(DTO):
    file_id: UUID
    file_version_id: UUID


class PageLocation(SourceBase):
    kind: Literal["page"]
    page: int = Field(ge=1)
    preview_id: UUID | None = None
    bbox: BoundingBox | None = None


class SheetLocation(SourceBase):
    kind: Literal["sheet"]
    sheet: NonEmptyString
    cell_range: Annotated[
        str, StringConstraints(pattern=r"^[A-Z]+[1-9][0-9]*(?::[A-Z]+[1-9][0-9]*)?$")
    ]


class ParagraphLocation(SourceBase):
    kind: Literal["paragraph"]
    path: NonEmptyString


SourceLocation = Annotated[
    PageLocation | SheetLocation | ParagraphLocation, Field(discriminator="kind")
]


class EvidenceRef(DTO):
    location: SourceLocation
    excerpt: NonEmptyString
    extraction_method: Literal["native", "ocr", "vision"]
    ocr_result_id: UUID | None = None

    @model_validator(mode="after")
    def ocr_reference(self) -> EvidenceRef:
        if self.extraction_method == "ocr" and self.ocr_result_id is None:
            raise ValueError("OCR evidence must reference its saved result")
        if self.extraction_method != "ocr" and self.ocr_result_id is not None:
            raise ValueError("Only OCR evidence may reference an OCR result")
        return self


class ResourceRef(DTO):
    kind: Literal["package", "file", "document"]
    id: UUID


class IssueAction(DTO):
    action: Literal[
        "upload_document",
        "open_source",
        "correct_type",
        "retry_verification",
        "clarify_rule",
        "add_to_revision_request",
    ]
    target: ResourceRef | None = None


class Issue(DTO):
    id: UUID
    code: NonEmptyString
    severity: Severity
    category: Literal["document", "technical", "configuration"]
    message: NonEmptyString
    rule_id: str | None = None
    objects: list[ResourceRef] = Field(default_factory=list)
    sources: list[EvidenceRef] = Field(default_factory=list)
    next_action: IssueAction | None = None


class ExpenseItem(DTO):
    description: NonEmptyString
    amount: DecimalString | None
    unit: str | None = None
    evidence: list[EvidenceRef] = Field(default_factory=list)


class FieldDataType(StrEnum):
    text = "text"
    decimal = "decimal"
    money = "money"
    date = "date"
    boolean = "boolean"
    expense_items = "expense_items"


class FieldObservation(DTO):
    field_id: NonEmptyString
    data_type: FieldDataType
    raw: str | None
    normalized: str | StrictBool | list[ExpenseItem] | None
    known_state: Literal["known", "missing", "unreadable", "conflict"]
    subject_role: SubjectRole = SubjectRole.unknown
    unit: str | None = None
    source: Literal["machine"] = "machine"
    evidence: list[EvidenceRef] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalized_value(self) -> FieldObservation:
        if self.known_state != "known":
            if self.normalized is not None:
                raise ValueError("An unknown fact cannot carry a normalized value")
            return self
        if self.normalized is None:
            raise ValueError("A known fact must carry a value")
        if self.data_type in (FieldDataType.money, FieldDataType.decimal):
            TypeAdapter(DecimalString).validate_python(self.normalized)
        elif self.data_type == FieldDataType.date:
            if not isinstance(self.normalized, str):
                raise ValueError("A date fact must be an ISO date string")
            if len(self.normalized) != 10 or self.normalized[4] != "-" or self.normalized[7] != "-":
                raise ValueError("A date fact must use YYYY-MM-DD")
            date.fromisoformat(self.normalized)
        elif self.data_type == FieldDataType.boolean:
            if not isinstance(self.normalized, bool):
                raise ValueError("A boolean fact must be a boolean")
        elif self.data_type == FieldDataType.expense_items:
            if not isinstance(self.normalized, list):
                raise ValueError("Expense items must be a list")
        elif not isinstance(self.normalized, str):
            raise ValueError("A text fact must be a string")
        if not self.evidence:
            raise ValueError("A known machine fact must have evidence")
        return self


class FileSummary(DTO):
    id: UUID
    file_version_id: UUID
    original_name: NonEmptyString
    format: FileFormat
    size_bytes: Count
    sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    created_at: AwareDatetime
    page_count: Annotated[int, Field(ge=1)] | None = None
    sheet_names: list[str] = Field(default_factory=list)


class ProviderMetadata(DTO):
    provider: Literal["external", "local"]
    model: NonEmptyString
    prompt_version: NonEmptyString
    schema_hash: NonEmptyString
    invocation_id: UUID


class ModelProfile(DTO):
    provider: Literal["external", "local"]
    model: NonEmptyString
    prompt_version: NonEmptyString
    preparation_version: NonEmptyString
    ocr_profile: str | None = None


class FileCheck(DTO):
    file: FileSummary
    processing: ProcessingStatus
    processing_stage: ProcessingStage | None
    predicted_type: DocumentType | Literal["unknown"] | None
    verdict: Verdict | None
    issues: list[Issue] = Field(default_factory=list)
    document_unit_ids: list[UUID] = Field(default_factory=list)
    invocations: list[ProviderMetadata] = Field(default_factory=list)
    error: ApiError | None = None


class SourceFragmentRef(DTO):
    id: UUID
    location: SourceLocation


class DocumentUnit(DTO):
    id: UUID
    version_id: UUID
    predicted_type: DocumentType | Literal["unknown"]
    effective_type: DocumentType | Literal["unknown"]
    type_overridden: bool
    fragments: list[SourceFragmentRef] = Field(min_length=1)
    fields: list[FieldObservation] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)


class RequirementKind(StrEnum):
    required = "required"
    conditional = "conditional"
    optional = "optional"


class RequirementResult(DTO):
    requirement_id: NonEmptyString
    document_type: DocumentType
    kind: RequirementKind
    status: Literal["found", "missing", "pending", "unknown", "not_applicable"]
    severity: Severity
    message: NonEmptyString
    document_unit_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def missing_severity(self) -> RequirementResult:
        if self.status == "missing":
            expected = {
                RequirementKind.required: Severity.error,
                RequirementKind.conditional: Severity.warning,
            }.get(self.kind)
            if expected is not None and self.severity != expected:
                raise ValueError("Deficit severity must match the requirement kind")
        return self


class RuleResult(DTO):
    rule_id: NonEmptyString
    status: Literal["PASS", "FAIL", "UNKNOWN", "NOT_APPLICABLE"]
    severity: Severity
    message: NonEmptyString
    operands: dict[str, FieldObservation] = Field(default_factory=dict)
    formula: str | None = None
    sources: list[EvidenceRef] = Field(default_factory=list)


class MachineReport(DTO):
    id: UUID
    package_id: UUID
    run_id: UUID
    input_revision: Revision
    progress_version: Revision
    program_version_id: UUID
    basis: Literal["machine"] = "machine"
    created_at: AwareDatetime
    reference_date: date
    timezone: NonEmptyString
    coverage: Coverage
    provisional: bool
    freshness: Freshness
    verdict: Verdict
    requirements: list[RequirementResult] = Field(default_factory=list)
    rules: list[RuleResult] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)

    @model_validator(mode="after")
    def no_premature_pass(self) -> MachineReport:
        if self.verdict == Verdict.passed:
            if self.coverage != Coverage.complete or self.provisional:
                raise ValueError("PASS requires complete, final coverage")
            if any(issue.severity != Severity.info for issue in self.issues):
                raise ValueError("PASS cannot contain warnings or errors")
            if any(rule.status in ("FAIL", "UNKNOWN") for rule in self.rules):
                raise ValueError("PASS requires resolved rules")
            if any(item.status in ("missing", "pending", "unknown") for item in self.requirements):
                raise ValueError("PASS requires resolved completeness")
        return self


class RunProgress(DTO):
    total: Count
    accepted: Count
    determining: Count
    checked: Count
    processing_error: Count

    @model_validator(mode="after")
    def counts_match(self) -> RunProgress:
        if self.total != self.accepted + self.determining + self.checked + self.processing_error:
            raise ValueError("File state counts must add up to total")
        return self


class VerificationRun(DTO):
    id: UUID
    package_id: UUID
    input_revision: Revision
    progress_version: Revision
    status: RunStatus
    coverage: Coverage
    freshness: Freshness
    reference_date: date
    timezone: NonEmptyString
    model_profile: ModelProfile
    progress: RunProgress
    files: list[FileCheck] = Field(default_factory=list)
    documents: list[DocumentUnit] = Field(default_factory=list)
    report: MachineReport | None = None
    error: ApiError | None = None


class ProjectContext(DTO):
    project_type: str | None = None
    conditions: dict[str, StrictBool | None] = Field(default_factory=dict)


class ApplicationDecision(DTO):
    id: UUID
    package_id: UUID
    input_revision: Revision
    report_id: UUID | None
    action: DecisionAction
    reason: NonEmptyString
    author: UserSummary
    decided_at: AwareDatetime
    freshness: Freshness


class PackageSummary(DTO):
    id: UUID
    title: NonEmptyString
    program_id: UUID
    program_version_id: UUID
    input_revision: Revision
    created_at: AwareDatetime
    updated_at: AwareDatetime
    current_run_id: UUID | None
    verdict: Verdict | None
    report_freshness: Freshness | None
    report_provisional: bool | None
    decision_status: DecisionAction | Literal["not_decided"]
    decision_freshness: Freshness | None


class PackageDetail(PackageSummary):
    project_context: ProjectContext
    files: list[FileSummary] = Field(default_factory=list)
    report: MachineReport | None = None
    decision: ApplicationDecision | None = None


class PackageCreate(DTO):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    program_version_id: UUID
    project_context: ProjectContext = Field(default_factory=ProjectContext)


class RevisionCommand(DTO):
    expected_revision: Revision


class ConfigurationUpdate(RevisionCommand):
    program_version_id: UUID | None = None
    project_context: ProjectContext | None = None

    @model_validator(mode="after")
    def has_change(self) -> ConfigurationUpdate:
        if self.program_version_id is None and self.project_context is None:
            raise ValueError("Provide a program version or project context")
        return self


class VerificationCreate(RevisionCommand):
    pass


class TypeUpdate(RevisionCommand):
    document_type: DocumentType
    reason: NonEmptyString


class GroupingUpdate(RevisionCommand):
    fragment_ids: list[UUID] = Field(min_length=1)
    reason: NonEmptyString

    @model_validator(mode="after")
    def unique_fragments(self) -> GroupingUpdate:
        if len(set(self.fragment_ids)) != len(self.fragment_ids):
            raise ValueError("A source fragment can only occur once")
        return self


class DecisionCreate(RevisionCommand):
    action: DecisionAction
    reason: NonEmptyString
    report_id: UUID | None = None


class RunRequested(DTO):
    package_id: UUID
    input_revision: Revision
    run_id: UUID
    correlation_id: UUID


class UploadRejection(DTO):
    original_name: NonEmptyString
    error: ApiError


class UploadResult(DTO):
    package_id: UUID
    input_revision: Revision
    accepted: list[FileSummary]
    rejected: list[UploadRejection]
    run_id: UUID | None
    correlation_id: UUID


class SheetCell(DTO):
    address: NonEmptyString
    value: str | StrictBool | None
    formula: str | None = None
    known_state: Literal["known", "missing", "unreadable"]


class SheetData(DTO):
    file_id: UUID
    file_version_id: UUID
    sheet: NonEmptyString
    cells: list[SheetCell]
    offset: Count
    limit: int = Field(ge=1, le=1000)
    total: Count


class FieldDefinition(DTO):
    id: NonEmptyString
    label: NonEmptyString
    data_type: FieldDataType
    unit: str | None = None


class DocumentTypeDefinition(DTO):
    id: DocumentType
    label: NonEmptyString
    description: NonEmptyString
    fields: list[FieldDefinition]
    minimum_field_ids: list[str]
    extension: bool = False


class EqualsPredicate(DTO):
    kind: Literal["equals"]
    field: NonEmptyString
    value: str | StrictBool


class IsTruePredicate(DTO):
    kind: Literal["is_true"]
    field: NonEmptyString


class AllPredicate(DTO):
    kind: Literal["all"]
    operands: list[ConditionPredicate] = Field(min_length=1)


class AnyPredicate(DTO):
    kind: Literal["any"]
    operands: list[ConditionPredicate] = Field(min_length=1)


ConditionPredicate = Annotated[
    EqualsPredicate | IsTruePredicate | AllPredicate | AnyPredicate, Field(discriminator="kind")
]
AllPredicate.model_rebuild()
AnyPredicate.model_rebuild()


class RequirementDefinition(DTO):
    id: NonEmptyString
    document_type: DocumentType
    kind: RequirementKind
    quantity: int = Field(ge=1)
    predicate: ConditionPredicate | None = None
    missing_severity: Severity
    needs_clarification: bool = False

    @model_validator(mode="after")
    def deficit_severity(self) -> RequirementDefinition:
        if self.kind == RequirementKind.conditional and self.missing_severity != Severity.warning:
            raise ValueError("A conditional deficit must stay a warning")
        if self.kind == RequirementKind.required and self.missing_severity != Severity.error:
            raise ValueError("A required deficit must be an error")
        return self


class FieldBinding(DTO):
    operand: NonEmptyString
    document_type: DocumentType
    field_id: NonEmptyString
    subject_role: SubjectRole = SubjectRole.unknown


class RuleParameters(DTO):
    factor: DecimalString | None = None
    pattern: str | None = None
    date_mode: Literal["not_future", "not_expired"] | None = None
    field_ids: list[str] = Field(default_factory=list)


class RuleDefinition(DTO):
    id: NonEmptyString
    family: Literal[
        "required_fields",
        "non_empty",
        "matches_regex",
        "date_compare",
        "ratio_gte",
        "amount_equal",
        "same_subject_value",
    ]
    bindings: list[FieldBinding] = Field(default_factory=list)
    parameters: RuleParameters = Field(default_factory=RuleParameters)
    severity: Severity
    needs_clarification: bool = False


class ProgramDefinition(DTO):
    name: NonEmptyString
    description: str
    document_types: list[DocumentTypeDefinition]
    requirements: list[RequirementDefinition]
    rules: list[RuleDefinition]


class ProgramSummary(DTO):
    id: UUID
    name: NonEmptyString
    latest_version_id: UUID


class ProgramVersion(DTO):
    id: UUID
    program_id: UUID
    version: int = Field(ge=1)
    published_at: AwareDatetime
    definition: ProgramDefinition


class ProgramDraftSummary(DTO):
    id: UUID
    program_id: UUID | None
    name: NonEmptyString
    revision: Revision
    status: Literal["draft", "published"]
    updated_at: AwareDatetime


class ProgramDraft(ProgramDraftSummary):
    base_version_id: UUID | None
    definition: ProgramDefinition


class ProgramDraftCreate(DTO):
    name: NonEmptyString
    base_version_id: UUID | None = None


class ProgramDraftUpdate(RevisionCommand):
    definition: ProgramDefinition


class RuleUpdate(RevisionCommand):
    rule: RuleDefinition


class DraftValidation(DTO):
    draft_id: UUID
    revision: Revision
    valid: bool
    issues: list[Issue]
    correlation_id: UUID


class AuditEvent(DTO):
    id: UUID
    actor: UserSummary | None
    action: NonEmptyString
    resource: ResourceRef
    input_revision: Revision | None
    run_id: UUID | None
    created_at: AwareDatetime
    correlation_id: UUID
    details: dict[str, JsonValue] = Field(default_factory=dict)


class Page[T](DTO):
    items: list[T]
    total: Count
    offset: Count
    limit: int = Field(ge=1, le=100)
