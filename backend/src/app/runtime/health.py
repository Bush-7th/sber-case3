from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app.modules.identity.persistence import UserRow
from app.runtime.cli import migration_config
from app.runtime.container import AppContainer


def readiness(container: AppContainer | None) -> dict:
    """Check local state only. Provider readiness requires a later real smoke test, never a poll."""
    checks = {
        "database": "not_ready",
        "schema": "not_ready",
        "identity": "not_ready",
        "catalog": "not_checked",
        "model": "not_checked",
        "office_converter": "not_checked",
    }
    if container is not None:
        try:
            with container.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
                checks["database"] = "ready"
                actual = set(MigrationContext.configure(connection).get_current_heads())
                expected = set(ScriptDirectory.from_config(migration_config()).get_heads())
                if actual == expected:
                    checks["schema"] = "ready"
                    active_roles = (
                        connection.execute(
                            select(UserRow.role)
                            .where(UserRow.active.is_(True))
                            .group_by(UserRow.role)
                            .having(func.count() > 0)
                        )
                        .scalars()
                        .all()
                    )
                    if set(active_roles) == {"specialist", "administrator"}:
                        checks["identity"] = "ready"
        except SQLAlchemyError:
            # An unavailable dependency must not disable liveness or expose connection details.
            pass
    api_ready = all(checks[key] == "ready" for key in ("database", "schema", "identity"))
    return {"api_ready": api_ready, "pipeline_ready": False, "checks": checks}
