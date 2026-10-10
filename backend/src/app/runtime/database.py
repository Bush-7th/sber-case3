from sqlalchemy import MetaData, create_engine
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(column_0_label)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


def build_engine(url: URL) -> Engine:
    return create_engine(
        url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        pool_timeout=5,
        hide_parameters=True,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"},
    )


class SqlAlchemyUnitOfWork:
    """Short transaction shared by explicitly constructed repository adapters."""

    def __init__(self, factory: sessionmaker[Session]):
        self.factory = factory

    def __enter__(self):
        self.session = self.factory()
        return self

    def commit(self) -> None:
        self.session.commit()

    def __exit__(self, exc_type, exc_value, traceback):
        # Closing rolls back every uncommitted transaction, including exceptional exits.
        self.session.close()
