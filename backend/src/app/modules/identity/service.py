from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import compare_digest, token_urlsafe

from app.modules.identity.domain import (
    AccessDenied,
    AuthenticationRequired,
    InvalidCredentials,
    ResolvedSession,
)
from app.modules.identity.ports import IdentityRepository, PasswordHasher


def secret_hash(secret: str) -> str:
    return sha256(secret.encode()).hexdigest()


@dataclass(frozen=True)
class IssuedSession:
    session: ResolvedSession
    cookie: str = field(repr=False)
    csrf_token: str = field(repr=False)


class IdentityService:
    def __init__(self, hasher: PasswordHasher, session_hours: int = 8):
        self.hasher = hasher
        self.session_hours = session_hours
        self.dummy_hash = hasher.hash(token_urlsafe(32))

    def authenticate(
        self, repository: IdentityRepository, username: str, password: str
    ) -> IssuedSession:
        record = repository.find_credentials(username)
        valid = self.hasher.verify(password, record.password_hash if record else self.dummy_hash)
        if not record or not valid or not record.active:
            raise InvalidCredentials
        now = datetime.now(UTC)
        cookie, csrf_token = token_urlsafe(32), token_urlsafe(32)
        session = ResolvedSession(
            actor=record.actor,
            token_hash=secret_hash(cookie),
            csrf_hash=secret_hash(csrf_token),
            expires_at=now + timedelta(hours=self.session_hours),
        )
        repository.add_session(session, now)
        return IssuedSession(session, cookie, csrf_token)

    def resolve_session(
        self, repository: IdentityRepository, cookie: str | None
    ) -> ResolvedSession:
        if not cookie or len(cookie) > 128:
            raise AuthenticationRequired
        session = repository.resolve_session(secret_hash(cookie), datetime.now(UTC))
        if session is None:
            raise AuthenticationRequired
        return session

    def check_csrf(self, session: ResolvedSession, token: str | None) -> None:
        if (
            not token
            or len(token) > 128
            or not compare_digest(session.csrf_hash, secret_hash(token))
        ):
            raise AccessDenied

    def revoke_session(self, repository: IdentityRepository, session: ResolvedSession) -> None:
        repository.revoke_session(session.token_hash, datetime.now(UTC))
