from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from app.modules.assets.persistence import BlobReferenceRow, BlobRow  # noqa: F401
from app.modules.identity.persistence import RoleRow, SessionRow, UserRow  # noqa: F401
from app.runtime.database import Base
from app.runtime.settings import Settings

target_metadata = Base.metadata

if context.is_offline_mode():
    context.configure(
        url="postgresql+psycopg://", target_metadata=target_metadata, literal_binds=True
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    supplied = context.config.attributes.get("connection")

    def run(connection):
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    if supplied is not None:
        run(supplied)
    else:
        engine = create_engine(
            Settings().sqlalchemy_url(), poolclass=NullPool, hide_parameters=True
        )
        try:
            with engine.connect() as connection:
                run(connection)
        finally:
            engine.dispose()
