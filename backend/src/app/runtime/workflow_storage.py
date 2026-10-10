"""Compact SQL adapters for M02/M04/M10/M11; immutable DTO snapshots in JSONB."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.runtime.database import Base


class ResourceRow(Base):
    __tablename__ = "workflow_resources"
    id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[UUID | None] = mapped_column(ForeignKey("identity_users.id"), index=True)
    parent_id: Mapped[UUID | None] = mapped_column(index=True)
    data: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class JobRow(Base):
    __tablename__ = "workflow_jobs"
    run_id: Mapped[UUID] = mapped_column(ForeignKey("workflow_resources.id"), primary_key=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    lease: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
