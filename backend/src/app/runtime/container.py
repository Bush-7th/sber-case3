from pwdlib import PasswordHash
from sqlalchemy.orm import sessionmaker

from app.modules.assets.ocr_persistence import PostgresOcrResultStore
from app.modules.identity.domain import AccessPolicy, ResolvedSession
from app.modules.identity.persistence import SqlIdentityRepository
from app.modules.identity.service import IdentityService, IssuedSession, secret_hash, session_csrf
from app.modules.inference.ollama import (
    PROMPT_VERSION as LOCAL_PROMPT_VERSION,
)
from app.modules.inference.ollama import OllamaClient, OllamaProvider, local_prompt_hash
from app.modules.inference.olmocr import OlmOcrClient
from app.modules.inference.qwen import PROMPT_VERSION, QwenProvider, prompt_hash
from app.modules.recognition.model import (
    DocumentModelPort,
    LocalModelProfile,
    PinnedModelProfile,
    local_schema_hash,
    schema_hash,
)
from app.runtime.database import SqlAlchemyUnitOfWork, build_engine
from app.runtime.settings import ConfigurationError, Settings


def build_qwen_provider(settings: Settings) -> QwenProvider:
    # Explicit diagnostic/factory. Local startup never constructs a remote model client.
    if (
        not settings.ilons_api_key.get_secret_value()
        or not settings.qwen_timeout_seconds
        or not settings.qwen_auth_header
        or settings.qwen_auth_scheme is None
    ):
        raise ConfigurationError("Set the confirmed Qwen connection and key outside Git")
    profile = PinnedModelProfile(
        provider="external",
        base_url=settings.qwen_base_url,
        model=settings.qwen_model,
        generation_path=settings.qwen_generation_path,
        api_format=settings.qwen_api_format,
        prompt_version=PROMPT_VERSION,
        prompt_hash=prompt_hash(),
        schema_hash=schema_hash(),
        timeout_seconds=settings.qwen_timeout_seconds,
        max_output_tokens=settings.qwen_max_output_tokens,
        context_window_size=settings.qwen_context_window_size,
        max_input_bytes=settings.qwen_max_input_bytes,
        max_response_bytes=settings.qwen_max_response_bytes,
    )
    return QwenProvider(
        profile,
        key=settings.ilons_api_key.get_secret_value(),
        auth_header=settings.qwen_auth_header,
        auth_scheme=settings.qwen_auth_scheme,
    )


async def build_ollama_provider(settings: Settings) -> OllamaProvider:
    from uuid import uuid4

    client = OllamaClient(
        settings.local_base_url,
        timeout_seconds=settings.local_timeout_seconds,
        max_response_bytes=settings.local_max_response_bytes,
    )
    try:
        model = await client.inspect_model(
            settings.local_model, uuid4(), settings.local_model_digest
        )
        profile = LocalModelProfile(
            provider="local",
            base_url=settings.local_base_url,
            model=model.model,
            generation_path="/api/chat",
            api_format="ollama-chat",
            prompt_version=LOCAL_PROMPT_VERSION,
            prompt_hash=local_prompt_hash(),
            schema_hash=local_schema_hash(),
            timeout_seconds=settings.local_timeout_seconds,
            max_output_tokens=settings.local_max_output_tokens,
            context_window_size=settings.local_context_window_size,
            max_input_bytes=settings.local_max_input_bytes,
            max_response_bytes=settings.local_max_response_bytes,
            model_digest=model.digest,
            server_version=model.server_version,
            num_threads=settings.local_num_threads,
            keep_alive_seconds=settings.local_keep_alive_seconds,
            vision=model.vision,
        )
        return OllamaProvider(profile, client)
    except BaseException:
        await client.aclose()
        raise


async def build_document_model(settings: Settings) -> DocumentModelPort:
    if settings.model_provider == "local":
        return await build_ollama_provider(settings)
    return build_qwen_provider(settings)


def build_ocr_client(settings: Settings) -> OlmOcrClient:
    return OlmOcrClient(
        settings.olmocr_base_url,
        token=settings.olmocr_api_token.get_secret_value(),
        timeout_seconds=settings.olmocr_timeout_seconds,
        configuration_revision=settings.olmocr_profile_revision,
        max_input_bytes=settings.olmocr_max_input_bytes,
    )


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

    def recover_session(self, cookie: str) -> IssuedSession:
        with self.unit_of_work() as uow:
            repository = SqlIdentityRepository(uow.session)
            session = self.identity.resolve_session(repository, cookie)
            csrf_token = session_csrf(cookie)
            csrf_hash = secret_hash(csrf_token)
            if session.csrf_hash != csrf_hash:
                # Upgrade sessions created before recovery support, once per cookie.
                repository.update_csrf(session.token_hash, csrf_hash)
                uow.commit()
                session = self.identity.resolve_session(repository, cookie)
            return IssuedSession(session, cookie, csrf_token)

    def create_ocr_client(self) -> OlmOcrClient:
        # Explicit factory; creating a local API/runtime never calls or requires remote OCR.
        return build_ocr_client(self.settings)

    def create_qwen_provider(self) -> QwenProvider:
        return build_qwen_provider(self.settings)

    async def create_document_model(self) -> DocumentModelPort:
        return await build_document_model(self.settings)

    def ocr_result_store(self) -> PostgresOcrResultStore:
        return PostgresOcrResultStore(self.session_factory)

    def close(self) -> None:
        self.engine.dispose()
