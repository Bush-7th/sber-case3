from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID


class Role(StrEnum):
    specialist = "specialist"
    administrator = "administrator"


class AccessDenied(Exception):
    pass


class AuthenticationRequired(Exception):
    pass


class InvalidCredentials(Exception):
    pass


@dataclass(frozen=True)
class ActorContext:
    id: UUID
    username: str
    display_name: str
    role: Role


@dataclass(frozen=True)
class ResolvedSession:
    actor: ActorContext
    token_hash: str
    csrf_hash: str
    expires_at: datetime


@dataclass(frozen=True)
class ResourceAccess:
    """Supplied by the resource's owning module; UUID alone grants no access."""

    owner_id: UUID


class AccessPolicy:
    def require_administrator(self, actor: ActorContext) -> None:
        if actor.role != Role.administrator:
            raise AccessDenied

    def require_specialist(self, actor: ActorContext) -> None:
        if actor.role != Role.specialist:
            raise AccessDenied

    def authorize_resource(self, actor: ActorContext, facts: ResourceAccess) -> None:
        # Administrators configure catalogues; they do not inherit access to applicants' files.
        self.require_specialist(actor)
        if facts.owner_id != actor.id:
            raise AccessDenied
