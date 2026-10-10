"""M05 public machine facts and provenance; independent of HTTP and persistence."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    TypeAdapter,
    model_validator,
)

DecimalString = Annotated[
    str, StringConstraints(strict=True, pattern=r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?$")
]
NonEmptyString = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid")


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


class SubjectRole(StrEnum):
    applicant = "applicant"
    guarantor = "guarantor"
    person = "person"
    unknown = "unknown"


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
