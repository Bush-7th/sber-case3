from datetime import UTC, datetime
from hashlib import sha256
from io import BytesIO
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    delete,
    exists,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.modules.assets.ports import BlobConflict, BlobNotFound, BlobRef
from app.runtime.database import Base


class BlobRow(Base):
    __tablename__ = "assets_blobs"
    __table_args__ = (
        CheckConstraint("size_bytes >= 0", name="nonnegative_size"),
        CheckConstraint("octet_length(data) = size_bytes", name="actual_size"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True)
    data: Mapped[bytes] = mapped_column(LargeBinary)
    sha256: Mapped[str] = mapped_column(String(64))
    size_bytes: Mapped[int] = mapped_column(Integer)
    media_type: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class BlobReferenceRow(Base):
    """Assets-owned retention registry. Owning modules retain before linking their resources."""

    __tablename__ = "assets_blob_references"

    blob_id: Mapped[UUID] = mapped_column(ForeignKey("assets_blobs.id"), primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(primary_key=True)


class PostgresBlobStore:
    def __init__(self, session: Session):
        self.session = session

    def put_immutable(self, blob_id: UUID, data: bytes, media_type: str) -> BlobRef:
        digest = sha256(data).hexdigest()
        self.session.execute(
            insert(BlobRow)
            .values(
                id=blob_id,
                data=data,
                sha256=digest,
                size_bytes=len(data),
                media_type=media_type,
                created_at=datetime.now(UTC),
            )
            .on_conflict_do_nothing(index_elements=[BlobRow.id])
        )
        row = self.session.execute(
            select(BlobRow.sha256, BlobRow.size_bytes, BlobRow.media_type)
            .where(BlobRow.id == blob_id)
            .with_for_update()
        ).one()
        if tuple(row) != (digest, len(data), media_type):
            raise BlobConflict
        return BlobRef(blob_id, digest, len(data), media_type)

    def head(self, blob_id: UUID) -> BlobRef:
        row = self.session.execute(
            select(BlobRow.id, BlobRow.sha256, BlobRow.size_bytes, BlobRow.media_type).where(
                BlobRow.id == blob_id
            )
        ).first()
        if row is None:
            raise BlobNotFound
        return BlobRef(*row)

    def open(self, blob_id: UUID) -> BytesIO:
        data = self.session.scalar(select(BlobRow.data).where(BlobRow.id == blob_id))
        if data is None:
            raise BlobNotFound
        return BytesIO(data)

    def retain(self, blob_id: UUID, resource_id: UUID) -> None:
        # A parent-row lock serializes reference creation with garbage collection.
        row = self.session.scalar(select(BlobRow.id).where(BlobRow.id == blob_id).with_for_update())
        if row is None:
            raise BlobNotFound
        if self.session.get(BlobReferenceRow, (blob_id, resource_id)) is None:
            self.session.add(BlobReferenceRow(blob_id=blob_id, resource_id=resource_id))
            self.session.flush()

    def release(self, blob_id: UUID, resource_id: UUID) -> None:
        self.session.execute(
            delete(BlobReferenceRow).where(
                BlobReferenceRow.blob_id == blob_id, BlobReferenceRow.resource_id == resource_id
            )
        )

    def delete_unreferenced(self, blob_id: UUID) -> bool:
        row = self.session.scalar(select(BlobRow.id).where(BlobRow.id == blob_id).with_for_update())
        if row is None:
            return False
        referenced = self.session.scalar(
            select(exists().where(BlobReferenceRow.blob_id == blob_id))
        )
        if referenced:
            return False
        self.session.execute(delete(BlobRow).where(BlobRow.id == blob_id))
        self.session.flush()
        return True
