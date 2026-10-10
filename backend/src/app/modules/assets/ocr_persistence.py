from dataclasses import asdict
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func, select
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import Mapped, Session, mapped_column, sessionmaker

from app.modules.assets.ocr import (
    OcrCacheKey,
    OcrProfile,
    OcrResult,
    OcrSource,
    OcrSourceConflict,
    OcrText,
    PreparedOcrPage,
)
from app.modules.assets.persistence import BlobRow, PostgresBlobStore
from app.runtime.database import Base, SqlAlchemyUnitOfWork


class FileVersionRow(Base):
    __tablename__ = "assets_file_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    file_id: Mapped[UUID] = mapped_column(index=True)
    original_blob_id: Mapped[UUID] = mapped_column(ForeignKey("assets_blobs.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OcrResultRow(Base):
    __tablename__ = "assets_ocr_results"
    __table_args__ = (
        CheckConstraint("page >= 1", name="positive_page"),
        CheckConstraint("length(btrim(text)) > 0", name="nonempty_text"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    cache_key: Mapped[str] = mapped_column(String(64), unique=True)
    file_version_id: Mapped[UUID] = mapped_column(ForeignKey("assets_file_versions.id"), index=True)
    page: Mapped[int] = mapped_column(Integer)
    preparation_profile: Mapped[str] = mapped_column(String(200))
    prepared_sha256: Mapped[str] = mapped_column(String(64))
    prepared_blob_id: Mapped[UUID] = mapped_column(ForeignKey("assets_blobs.id"))
    ocr_profile: Mapped[dict] = mapped_column(JSONB)
    text: Mapped[str] = mapped_column(Text)
    invocation: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SqlOcrRepository:
    def __init__(self, session: Session):
        self.session = session

    def register_source(self, source: OcrSource) -> None:
        blob = PostgresBlobStore(self.session).head(source.original_blob_id)
        if blob.sha256 != source.original_sha256:
            raise OcrSourceConflict
        self.session.execute(
            insert(FileVersionRow)
            .values(
                id=source.file_version_id,
                file_id=source.file_id,
                original_blob_id=source.original_blob_id,
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=[FileVersionRow.id])
        )
        self.validate_source(source)
        PostgresBlobStore(self.session).retain(source.original_blob_id, source.file_version_id)

    def validate_source(self, source: OcrSource) -> None:
        row = self.session.execute(
            select(FileVersionRow.file_id, FileVersionRow.original_blob_id, BlobRow.sha256)
            .join(BlobRow, FileVersionRow.original_blob_id == BlobRow.id)
            .where(FileVersionRow.id == source.file_version_id)
        ).first()
        if row is None or tuple(row) != (
            source.file_id,
            source.original_blob_id,
            source.original_sha256,
        ):
            raise OcrSourceConflict

    def find(self, page: PreparedOcrPage, profile: OcrProfile) -> OcrResult | None:
        self.validate_source(page.source)
        row = self.session.scalar(
            select(OcrResultRow).where(
                OcrResultRow.cache_key == OcrCacheKey.for_page(page, profile).fingerprint
            )
        )
        return self._result(row, page.source) if row else None

    def save(self, page: PreparedOcrPage, profile: OcrProfile, output: OcrText) -> OcrResult:
        self.validate_source(page.source)
        if not output.text.strip():
            raise ValueError("Empty OCR text cannot be saved")
        key = OcrCacheKey.for_page(page, profile).fingerprint
        # Different cache keys run concurrently. The same key keeps the first completed result.
        lock_id = int(key[:16], 16)
        lock_id = lock_id if lock_id < 2**63 else lock_id - 2**64
        self.session.execute(select(func.pg_advisory_xact_lock(lock_id)))
        existing = self.find(page, profile)
        if existing:
            return existing
        result_id, prepared_blob_id = uuid4(), uuid4()
        blobs = PostgresBlobStore(self.session)
        blobs.put_immutable(prepared_blob_id, page.data, page.media_type)
        blobs.retain(prepared_blob_id, result_id)
        row = OcrResultRow(
            id=result_id,
            cache_key=key,
            file_version_id=page.source.file_version_id,
            page=page.page,
            preparation_profile=page.preparation_profile,
            prepared_sha256=page.sha256,
            prepared_blob_id=prepared_blob_id,
            ocr_profile=asdict(profile),
            text=output.text,
            invocation={
                "content_type": output.content_type,
                "duration_ms": output.duration_ms,
                "correlation_id": str(output.correlation_id),
                "service_request_id": str(output.service_request_id)
                if output.service_request_id
                else None,
            },
            created_at=datetime.now(UTC),
        )
        self.session.add(row)
        self.session.flush()
        return self._result(row, page.source)

    def _result(self, row: OcrResultRow, source: OcrSource) -> OcrResult:
        metadata = row.invocation
        return OcrResult(
            id=row.id,
            source=source,
            page=row.page,
            preparation_profile=row.preparation_profile,
            prepared_sha256=row.prepared_sha256,
            prepared_blob_id=row.prepared_blob_id,
            profile=OcrProfile(**row.ocr_profile),
            output=OcrText(
                text=row.text,
                content_type=metadata["content_type"],
                duration_ms=metadata["duration_ms"],
                correlation_id=UUID(metadata["correlation_id"]),
                service_request_id=UUID(metadata["service_request_id"])
                if metadata["service_request_id"]
                else None,
            ),
            created_at=row.created_at,
        )


class PostgresOcrResultStore:
    """Owns short transactions for standalone preparation; no HTTP call holds a session."""

    def __init__(self, factory: sessionmaker[Session]):
        self.factory = factory

    def find(self, page: PreparedOcrPage, profile: OcrProfile) -> OcrResult | None:
        with SqlAlchemyUnitOfWork(self.factory) as uow:
            return SqlOcrRepository(uow.session).find(page, profile)

    def save(self, page: PreparedOcrPage, profile: OcrProfile, output: OcrText) -> OcrResult:
        with SqlAlchemyUnitOfWork(self.factory) as uow:
            result = SqlOcrRepository(uow.session).save(page, profile, output)
            uow.commit()
            return result
