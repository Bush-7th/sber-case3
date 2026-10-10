from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, ForeignKey, String, select, update
from sqlalchemy.orm import Mapped, Session, mapped_column

from app.modules.identity.domain import ActorContext, ResolvedSession, Role
from app.modules.identity.ports import CredentialRecord
from app.runtime.database import Base


class RoleRow(Base):
    __tablename__ = "identity_roles"

    name: Mapped[str] = mapped_column(String(32), primary_key=True)


class UserRow(Base):
    __tablename__ = "identity_users"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(ForeignKey("identity_roles.name"))
    password_hash: Mapped[str] = mapped_column(String(512))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SessionRow(Base):
    __tablename__ = "identity_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("identity_users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


def actor_from(row: UserRow) -> ActorContext:
    return ActorContext(row.id, row.username, row.display_name, Role(row.role))


class SqlIdentityRepository:
    def __init__(self, session: Session):
        self.session = session

    def find_credentials(self, username: str) -> CredentialRecord | None:
        row = self.session.scalar(select(UserRow).where(UserRow.username == username))
        return CredentialRecord(actor_from(row), row.password_hash, row.active) if row else None

    def add_session(self, session: ResolvedSession, created_at: datetime) -> None:
        self.session.add(
            SessionRow(
                token_hash=session.token_hash,
                csrf_hash=session.csrf_hash,
                user_id=session.actor.id,
                created_at=created_at,
                expires_at=session.expires_at,
            )
        )

    def resolve_session(self, token_hash: str, now: datetime) -> ResolvedSession | None:
        result = self.session.execute(
            select(SessionRow, UserRow)
            .join(UserRow, UserRow.id == SessionRow.user_id)
            .where(
                SessionRow.token_hash == token_hash,
                SessionRow.expires_at > now,
                SessionRow.revoked_at.is_(None),
                UserRow.active.is_(True),
            )
        ).first()
        if result is None:
            return None
        row, user = result
        return ResolvedSession(actor_from(user), row.token_hash, row.csrf_hash, row.expires_at)

    def revoke_session(self, token_hash: str, now: datetime) -> None:
        self.session.execute(
            update(SessionRow)
            .where(SessionRow.token_hash == token_hash, SessionRow.revoked_at.is_(None))
            .values(revoked_at=now)
        )

    def update_csrf(self, token_hash: str, csrf_hash: str) -> None:
        self.session.execute(
            update(SessionRow)
            .where(SessionRow.token_hash == token_hash, SessionRow.revoked_at.is_(None))
            .values(csrf_hash=csrf_hash)
        )
