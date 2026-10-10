import os
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.runtime.cli import migrate
from app.runtime.settings import Settings


@pytest.fixture(scope="module")
def database_url():
    source = os.environ.get("TEST_DATABASE_URL")
    if not source:
        pytest.skip("Set TEST_DATABASE_URL to run real PostgreSQL integration checks")
    admin_url = make_url(source)
    assert admin_url.drivername == "postgresql+psycopg"
    # Never truncate the database specified by the developer; create our own throwaway database.
    name = "case3_inf01_" + uuid4().hex
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    target = admin_url.set(database=name)
    try:
        migrate(Settings(_env_file=None, database_url=target.render_as_string(hide_password=False)))
        yield target
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()
