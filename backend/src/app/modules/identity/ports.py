from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.identity.domain import ActorContext, ResolvedSession


@dataclass(frozen=True)
class CredentialRecord:
    actor: ActorContext
    password_hash: str
    active: bool


class IdentityRepository(Protocol):
    def find_credentials(self, username: str) -> CredentialRecord | None: ...

    def add_session(self, session: ResolvedSession, created_at: datetime) -> None: ...

    def resolve_session(self, token_hash: str, now: datetime) -> ResolvedSession | None: ...

    def revoke_session(self, token_hash: str, now: datetime) -> None: ...


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, encoded: str) -> bool: ...
