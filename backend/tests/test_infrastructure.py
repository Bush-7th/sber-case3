import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import uuid4

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, select, text, update
from sqlalchemy.orm import Session

from app.main import create_app
from app.modules.assets.persistence import BlobRow, PostgresBlobStore
from app.modules.assets.ports import BlobConflict, BlobNotFound
from app.modules.identity.domain import (
    AccessDenied,
    AccessPolicy,
    ActorContext,
    ResourceAccess,
    Role,
)
from app.modules.identity.persistence import SessionRow, UserRow
from app.modules.identity.service import secret_hash
from app.runtime.cli import bootstrap, migration_config
from app.runtime.database import Base
from app.runtime.settings import Settings

PASSWORD = "test-only-specialist-password"
ADMIN_PASSWORD = "test-only-administrator-password"


def test_local_settings_do_not_require_remote_credentials_and_secrets_are_redacted():
    settings = Settings(_env_file=None, ilons_api_key="qwen-secret", olmocr_api_token="ocr-secret")
    assert settings.model_provider == "local"
    assert settings.qwen_timeout_seconds is None
    assert "qwen-secret" not in repr(settings)
    assert "ocr-secret" not in repr(settings)
    for invalid in (
        {"model_provider": "unknown"},
        {"model_provider": "external"},
        {"app_env": "production", "session_cookie_secure": False},
    ):
        with pytest.raises(ValidationError):
            Settings(_env_file=None, **invalid)
    external = Settings(
        _env_file=None,
        model_provider="external",
        ilons_api_key="separate-secret",
        qwen_generation_path="/confirmed-path",
        qwen_api_format="openai-chat",
        qwen_auth_header="Authorization",
        qwen_auth_scheme="Bearer",
        qwen_timeout_seconds=90,
    )
    assert external.olmocr_api_token.get_secret_value() == ""


def test_database_password_is_encoded_once_and_not_printed():
    settings = Settings(_env_file=None, postgres_password="a@b:c/percent%word")
    url = settings.sqlalchemy_url()
    assert url.password == "a@b:c/percent%word"
    assert "a@b" not in str(url)


def test_unexpected_errors_are_structured_and_do_not_log_exception_content(caplog, monkeypatch):
    monkeypatch.setattr(logging.getLogger("case3.http"), "handlers", [caplog.handler])
    application = create_app(Settings(_env_file=None))

    @application.get("/test-failure")
    def failure():
        raise RuntimeError("secret-document-fragment")

    with TestClient(application) as client:
        response = client.get("/test-failure")
    assert response.status_code == 500 and response.json()["code"] == "internal_error"
    assert "secret-document-fragment" not in response.text + caplog.text
    assert '"error_type": "RuntimeError"' in caplog.text
    assert response.headers["X-Correlation-ID"] == response.json()["correlation_id"]


def test_access_policy_requires_the_resource_owner_and_correct_role():
    owner = ActorContext(uuid4(), "owner", "Owner", Role.specialist)
    other = ActorContext(uuid4(), "other", "Other", Role.specialist)
    admin = ActorContext(uuid4(), "admin", "Admin", Role.administrator)
    policy = AccessPolicy()
    policy.authorize_resource(owner, ResourceAccess(owner.id))
    for denied in (other, admin):
        with pytest.raises(AccessDenied):
            policy.authorize_resource(denied, ResourceAccess(owner.id))
    policy.require_administrator(admin)
    with pytest.raises(AccessDenied):
        policy.require_administrator(owner)


@pytest.fixture()
def configured(database_url):
    engine = create_engine(database_url, hide_parameters=True)
    with engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE identity_sessions, identity_users, "
                "assets_blob_references, assets_blobs CASCADE"
            )
        )
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=database_url.render_as_string(hide_password=False),
        bootstrap_specialist_password=PASSWORD,
        bootstrap_admin_password=ADMIN_PASSWORD,
    )
    bootstrap(settings)
    try:
        yield settings, engine
    finally:
        engine.dispose()


def login(client, username="specialist", password=PASSWORD):
    response = client.post("/api/v1/sessions", json={"username": username, "password": password})
    assert response.status_code == 200
    return response


@pytest.mark.integration
def test_migration_roundtrip_and_metadata_match(database_url):
    engine = create_engine(database_url)
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes["connection"] = connection
            context = MigrationContext.configure(connection)
            assert context.get_current_revision() == "0002_ocr_results"
            assert compare_metadata(context, Base.metadata) == []
            assert (
                connection.execute(
                    text(
                        "SELECT data_type FROM information_schema.columns "
                        "WHERE table_name = 'assets_blobs' AND column_name = 'data'"
                    )
                ).scalar_one()
                == "bytea"
            )
            command.downgrade(config, "base")
            assert not connection.execute(text("SELECT to_regclass('identity_users')")).scalar()
            command.upgrade(config, "head")
            assert set(connection.execute(text("SELECT name FROM identity_roles")).scalars()) == {
                "specialist",
                "administrator",
            }
    finally:
        engine.dispose()


@pytest.mark.integration
def test_login_hashes_secrets_and_logout_revokes_the_server_session(configured):
    settings, engine = configured
    with TestClient(create_app(settings)) as client:
        response = login(client)
        csrf = response.json()["csrf_token"]
        cookie = client.cookies["session"]
        assert response.json()["user"]["role"] == "specialist"
        assert "password" not in response.json()["user"]
        flags = response.headers["set-cookie"]
        assert "HttpOnly" in flags and "SameSite=strict" in flags and "Path=/api/v1" in flags
        with Session(engine) as session:
            row = session.scalar(select(SessionRow))
            assert row.token_hash == sha256(cookie.encode()).hexdigest()
            assert row.csrf_hash == secret_hash(csrf)
            assert cookie not in row.token_hash and csrf not in row.csrf_hash
            assert session.scalar(
                select(UserRow.password_hash).where(UserRow.username == "specialist")
            ).startswith("$argon2id$")
        assert client.delete("/api/v1/sessions").status_code == 403
        assert client.delete("/api/v1/sessions", headers={"X-CSRF-Token": csrf}).status_code == 204
        assert "session" not in client.cookies
        response = client.get("/api/v1/packages", headers={"Cookie": "session=" + cookie})
        assert response.status_code == 401


@pytest.mark.integration
def test_secure_session_cookie_is_set_and_removed_on_https(configured):
    settings, _ = configured
    settings = settings.model_copy(update={"session_cookie_secure": True})
    with TestClient(create_app(settings), base_url="https://testserver") as client:
        response = login(client)
        assert "Secure" in response.headers["set-cookie"]
        assert client.get("/api/v1/packages").status_code == 501
        deleted = client.delete(
            "/api/v1/sessions", headers={"X-CSRF-Token": response.json()["csrf_token"]}
        )
        assert deleted.status_code == 204 and "Secure" in deleted.headers["set-cookie"]
        assert "session" not in client.cookies


@pytest.mark.integration
def test_direct_urls_roles_csrf_and_unimplemented_business(configured):
    settings, _ = configured
    paths = [
        "/api/v1/packages",
        f"/api/v1/files/{uuid4()}/content",
        f"/api/v1/files/{uuid4()}/preview",
        f"/api/v1/files/{uuid4()}/sheets/Sheet1",
        "/api/v1/admin/program-drafts",
    ]
    with TestClient(create_app(settings)) as client:
        for path in paths:
            assert client.get(path).status_code == 401
        # Authentication precedes JSON/multipart validation, even when content is malformed.
        assert (
            client.post("/api/v1/packages/not-a-uuid/files", content=b"invalid").status_code == 401
        )
        specialist = login(client)
        assert client.get(paths[0]).status_code == 501
        assert client.get(paths[1]).status_code == 501
        assert client.get(paths[-1]).status_code == 403
        assert client.post("/api/v1/packages", json={}).status_code == 403
        assert (
            client.post(
                "/api/v1/packages",
                json={},
                headers={"X-CSRF-Token": specialist.json()["csrf_token"]},
            ).status_code
            == 422
        )
        admin = login(client, "administrator", ADMIN_PASSWORD)
        assert client.get(paths[-1]).status_code == 501
        for path in paths[:-1]:
            assert client.get(path).status_code == 403
        assert (
            client.delete(
                "/api/v1/sessions", headers={"X-CSRF-Token": specialist.json()["csrf_token"]}
            ).status_code
            == 403
        )
        assert (
            client.delete(
                "/api/v1/sessions", headers={"X-CSRF-Token": admin.json()["csrf_token"]}
            ).status_code
            == 204
        )


@pytest.mark.integration
def test_wrong_expired_disabled_and_cross_origin_sessions(configured, caplog, monkeypatch):
    monkeypatch.setattr(logging.getLogger("case3.http"), "handlers", [caplog.handler])
    settings, engine = configured
    caplog.set_level(logging.INFO, logger="case3.http")
    with TestClient(create_app(settings)) as client:
        wrong = client.post(
            "/api/v1/sessions", json={"username": "specialist", "password": "wrong"}
        )
        absent = client.post("/api/v1/sessions", json={"username": "absent", "password": "wrong"})
        assert wrong.status_code == absent.status_code == 401
        assert wrong.json()["code"] == absent.json()["code"] == "invalid_credentials"
        assert not client.cookies
        assert (
            client.post(
                "/api/v1/sessions",
                json={"username": "specialist", "password": PASSWORD},
                headers={"Origin": "https://untrusted.example"},
            ).status_code
            == 403
        )
        response = login(client)
        assert (
            client.delete(
                "/api/v1/sessions",
                headers={
                    "X-CSRF-Token": response.json()["csrf_token"],
                    "Origin": "https://untrusted.example",
                },
            ).status_code
            == 403
        )
        assert (
            client.delete(
                "/api/v1/sessions",
                headers={
                    "X-CSRF-Token": response.json()["csrf_token"],
                    "Sec-Fetch-Site": "cross-site",
                },
            ).status_code
            == 403
        )
        with engine.begin() as connection:
            connection.execute(
                update(SessionRow).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        assert client.get("/api/v1/packages").status_code == 401
        login(client)
        with engine.begin() as connection:
            connection.execute(
                update(UserRow).where(UserRow.username == "specialist").values(active=False)
            )
        assert client.get("/api/v1/packages").status_code == 401
        assert (
            client.post(
                "/api/v1/sessions", json={"username": "specialist", "password": PASSWORD}
            ).status_code
            == 401
        )
    assert "http_request" in caplog.text
    assert PASSWORD not in caplog.text and response.json()["csrf_token"] not in caplog.text


@pytest.mark.integration
def test_bootstrap_is_idempotent_and_does_not_reset_password(configured):
    settings, engine = configured
    with Session(engine) as session:
        original = session.execute(select(UserRow.id, UserRow.password_hash)).all()
    second = settings.model_copy(
        update={"bootstrap_specialist_password": SecretStr("different-test-password")}
    )
    bootstrap(second)
    with Session(engine) as session:
        assert session.execute(select(UserRow.id, UserRow.password_hash)).all() == original
    with TestClient(create_app(settings)) as client:
        login(client)
        assert (
            client.post(
                "/api/v1/sessions",
                json={"username": "specialist", "password": "different-test-password"},
            ).status_code
            == 401
        )


@pytest.mark.integration
def test_restart_preserves_sessions_and_missing_dependencies_preserve_liveness(configured):
    settings, _ = configured
    with TestClient(create_app(settings)) as first:
        login(first)
        cookie = first.cookies["session"]
        health = first.get("/health/ready")
        assert health.status_code == 503
        assert health.json()["details"]["api_ready"] is True
        assert health.json()["details"]["pipeline_ready"] is False
        assert health.json()["details"]["checks"]["model"] == "not_checked"
    with TestClient(create_app(settings)) as second:
        assert (
            second.get("/api/v1/packages", headers={"Cookie": "session=" + cookie}).status_code
            == 501
        )
    broken = settings.model_copy(
        update={
            "database_url": SecretStr(
                "postgresql+psycopg://unavailable:private-db-password@127.0.0.1:1/absent"
            )
        }
    )
    with TestClient(create_app(broken)) as client:
        assert client.get("/health/live").status_code == 200
        health = client.get("/health/ready")
        assert health.status_code == 503 and health.json()["details"]["api_ready"] is False
        response = client.post(
            "/api/v1/sessions", json={"username": "specialist", "password": PASSWORD}
        )
        assert response.status_code == 503 and "private-db-password" not in response.text


@pytest.mark.integration
def test_blobs_are_immutable_transactional_persistent_and_retained(configured):
    settings, engine = configured
    from app.runtime.container import AppContainer

    container = AppContainer(settings)
    blob_id, resource_id = uuid4(), uuid4()
    data = b"\x00\x01\x02\xff"  # Storage payload, not a fabricated document.
    try:
        with container.unit_of_work() as uow:
            store = PostgresBlobStore(uow.session)
            ref = store.put_immutable(blob_id, data, "application/octet-stream")
            assert ref.size_bytes == len(data)
            assert store.put_immutable(blob_id, data, ref.media_type) == ref
            with pytest.raises(BlobConflict):
                store.put_immutable(blob_id, b"different", ref.media_type)
            store.retain(blob_id, resource_id)
            uow.commit()
        container.close()
        container = AppContainer(settings)
        with container.unit_of_work() as uow:
            store = PostgresBlobStore(uow.session)
            assert store.head(blob_id) == ref
            assert store.open(blob_id).read() == data
            assert not store.delete_unreferenced(blob_id)
            store.release(blob_id, resource_id)
            assert store.delete_unreferenced(blob_id)
            # Deliberately omit commit: deletion and release must both roll back.
        with container.unit_of_work() as uow:
            store = PostgresBlobStore(uow.session)
            assert store.open(blob_id).read() == data
            store.release(blob_id, resource_id)
            assert store.delete_unreferenced(blob_id)
            uow.commit()
        with container.unit_of_work() as uow:
            with pytest.raises(BlobNotFound):
                PostgresBlobStore(uow.session).open(blob_id)
        rollback_id = uuid4()
        with pytest.raises(RuntimeError), container.unit_of_work() as uow:
            PostgresBlobStore(uow.session).put_immutable(
                rollback_id, data, "application/octet-stream"
            )
            raise RuntimeError("rollback")
        with Session(engine) as session:
            assert session.get(BlobRow, rollback_id) is None
    finally:
        container.close()


@pytest.mark.integration
def test_concurrent_blob_replay_does_not_overwrite_or_abort_transactions(configured):
    settings, _ = configured
    from app.runtime.container import AppContainer

    container = AppContainer(settings)
    blob_id = uuid4()

    def put(data):
        with container.unit_of_work() as uow:
            ref = PostgresBlobStore(uow.session).put_immutable(
                blob_id, data, "application/octet-stream"
            )
            uow.commit()
            return ref

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(put, [b"\x01\x02", b"\x01\x02"]))
        assert results[0] == results[1]
        with pytest.raises(BlobConflict):
            put(b"\x03")
        with container.unit_of_work() as uow:
            assert PostgresBlobStore(uow.session).open(blob_id).read() == b"\x01\x02"
    finally:
        container.close()
