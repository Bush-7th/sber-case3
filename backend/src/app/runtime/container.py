from pwdlib import PasswordHash
from sqlalchemy.orm import sessionmaker

from app.modules.identity.domain import AccessPolicy, ResolvedSession
from app.modules.identity.persistence import SqlIdentityRepository
from app.modules.identity.service import IdentityService, IssuedSession
from app.runtime.database import SqlAlchemyUnitOfWork, build_engine
from app.runtime.settings import Settings


class AppContainer:
    """Composition root; no request or domain object receives this as a service locator."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.engine = build_engine(settings.sqlalchemy_url())
        self.session_factory = sessionmaker(self.engine, expire_on_commit=False)
        self.identity = IdentityService(PasswordHash.recommended(), settings.session_hours)
        self.access = AccessPolicy()

    def unit_of_work(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self.session_factory)

    def authenticate(self, username: str, password: str) -> IssuedSession:
        with self.unit_of_work() as uow:
            issued = self.identity.authenticate(
                SqlIdentityRepository(uow.session), username, password
            )
            uow.commit()
            return issued

    def resolve_session(self, cookie: str | None) -> ResolvedSession:
        with self.unit_of_work() as uow:
            return self.identity.resolve_session(SqlIdentityRepository(uow.session), cookie)

    def revoke_session(self, session: ResolvedSession) -> None:
        with self.unit_of_work() as uow:
            self.identity.revoke_session(SqlIdentityRepository(uow.session), session)
            uow.commit()

    def close(self) -> None:
        self.engine.dispose()
