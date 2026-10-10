"""Explicit provisioning commands, run before serving traffic."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from alembic import command
from alembic.config import Config
from pwdlib import PasswordHash
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.modules.identity.domain import Role
from app.modules.identity.persistence import UserRow
from app.runtime.catalog_seed import seed_catalog
from app.runtime.database import build_engine
from app.runtime.settings import ConfigurationError, Settings

BACKEND_ROOT = Path(__file__).resolve().parents[3]


def migration_config() -> Config:
    return Config(str(BACKEND_ROOT / "alembic.ini"))


def migrate(settings: Settings) -> None:
    engine = build_engine(settings.sqlalchemy_url())
    try:
        with engine.connect() as connection:
            # Serialize separate deploy attempts. Lock lifetime is this connection, not a HTTP call.
            connection.execute(text("SELECT pg_advisory_lock(314159265)"))
            connection.commit()
            try:
                config = migration_config()
                config.attributes["connection"] = connection
                command.upgrade(config, "head")
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(314159265)"))
                connection.commit()
    finally:
        engine.dispose()


def bootstrap(settings: Settings) -> None:
    users = [
        (
            settings.bootstrap_specialist_username,
            settings.bootstrap_specialist_password,
            "Специалист",
            Role.specialist,
        ),
        (
            settings.bootstrap_admin_username,
            settings.bootstrap_admin_password,
            "Администратор",
            Role.administrator,
        ),
    ]
    if users[0][0] == users[1][0] or any(
        not username.strip() or len(username) > 100 or len(password.get_secret_value()) < 12
        for username, password, _, _ in users
    ):
        raise ConfigurationError(
            "Bootstrap needs distinct usernames and passwords of 12+ characters"
        )
    engine = build_engine(settings.sqlalchemy_url())
    hasher = PasswordHash.recommended()
    # CPU work outside the database transaction; existing credentials are never silently reset.
    hashes = {
        username: hasher.hash(password.get_secret_value()) for username, password, _, _ in users
    }
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("SELECT pg_advisory_xact_lock(314159266)"))
            for username, _, display_name, role in users:
                existing = session.scalar(select(UserRow).where(UserRow.username == username))
                if existing:
                    if existing.role != role:
                        raise ConfigurationError(
                            "Bootstrap username already belongs to another role"
                        )
                    continue
                session.add(
                    UserRow(
                        id=uuid4(),
                        username=username,
                        display_name=display_name,
                        role=role,
                        password_hash=hashes[username],
                        active=True,
                        created_at=datetime.now(UTC),
                    )
                )
            session.flush()
            seed_catalog(session)
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["migrate", "bootstrap"])
    args = parser.parse_args()
    try:
        settings = Settings()
        {"migrate": migrate, "bootstrap": bootstrap}[args.command](settings)
    except (ConfigurationError, ValidationError, SQLAlchemyError):
        # Driver/validation exceptions can include URLs or input values. Never print them.
        print(json.dumps({"event": "provisioning_failed", "command": args.command}))
        raise SystemExit(1) from None
    print(json.dumps({"event": "provisioning_complete", "command": args.command}))


if __name__ == "__main__":
    main()
