from typing import Annotated, Literal
from urllib.parse import urlsplit

from pydantic import Field, SecretStr, StringConstraints, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

HeaderName = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9-]+$")]


class ConfigurationError(Exception):
    """Safe startup error; never embeds input values or credentials."""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["local", "test", "production"] = "local"
    database_url: SecretStr | None = None
    db_host: str = "db"
    db_port: int = Field(default=5432, ge=1, le=65535)
    postgres_db: str = "case3"
    postgres_user: str = "case3"
    postgres_password: SecretStr | None = None
    session_hours: int = Field(default=8, ge=1, le=168)
    session_cookie_secure: bool = False
    allowed_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]
    blob_backend: Literal["postgres"] = "postgres"
    office_converter: Literal["disabled", "libreoffice"] = "disabled"

    model_provider: Literal["external", "local"] = "local"
    local_base_url: str = "http://ollama:11434"
    local_model: str = "qwen3-vl:4b-instruct"
    local_timeout_seconds: int = Field(default=300, gt=0)
    olmocr_base_url: str = "https://ocr.ilons.ru"
    olmocr_api_token: SecretStr = SecretStr("")
    olmocr_timeout_seconds: int = Field(default=300, gt=0)
    qwen_base_url: str = "https://llm.ilons.ru"
    qwen_model: str = "Qwen/Qwen3.8-27B"
    qwen_context_window_size: int = Field(default=262000, gt=0)
    ilons_api_key: SecretStr = SecretStr("")
    qwen_generation_path: str = ""
    qwen_api_format: str = ""
    qwen_auth_header: HeaderName | None = None
    qwen_auth_scheme: str | None = None
    qwen_timeout_seconds: int | None = Field(default=None, gt=0)

    bootstrap_specialist_username: str = "specialist"
    bootstrap_specialist_password: SecretStr = SecretStr("")
    bootstrap_admin_username: str = "administrator"
    bootstrap_admin_password: SecretStr = SecretStr("")

    @field_validator("qwen_auth_header", "qwen_timeout_seconds", mode="before")
    @classmethod
    def unset_optional_connection_field(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_profile(self):
        if self.app_env == "production" and not self.session_cookie_secure:
            raise ValueError("Production requires secure session cookies")
        if self.model_provider == "external":
            required = (
                self.ilons_api_key.get_secret_value(),
                self.qwen_generation_path,
                self.qwen_api_format,
                self.qwen_auth_header,
                self.qwen_timeout_seconds,
            )
            if not all(required):
                raise ValueError("External profile requires a confirmed Qwen contract and key")
            if self.qwen_auth_scheme is None:
                raise ValueError("Confirm Qwen auth scheme; an explicit empty string means raw key")
            if not self.qwen_generation_path.startswith("/"):
                raise ValueError("Qwen generation path must be an absolute API path")
            if "\r" in self.qwen_auth_scheme or "\n" in self.qwen_auth_scheme:
                raise ValueError("Invalid Qwen authorization scheme")
            addresses = [self.qwen_base_url, self.olmocr_base_url]
        else:
            if not self.local_base_url or not self.local_model:
                raise ValueError("Local profile requires Ollama address and model")
            addresses = [self.local_base_url]
        for address in addresses:
            parsed = urlsplit(address)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.hostname
                or parsed.username
                or parsed.password
                or parsed.query
                or parsed.fragment
            ):
                raise ValueError("Provider address must be HTTP(S), without embedded credentials")
        return self

    def sqlalchemy_url(self) -> URL:
        if self.database_url:
            try:
                url = make_url(self.database_url.get_secret_value())
            except (ArgumentError, ValueError):
                raise ConfigurationError("Invalid DATABASE_URL") from None
            if url.drivername != "postgresql+psycopg":
                raise ConfigurationError("DATABASE_URL must use postgresql+psycopg")
            return url
        if not self.postgres_password or not self.postgres_password.get_secret_value():
            raise ConfigurationError("Set POSTGRES_PASSWORD or DATABASE_URL outside Git")
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.db_host,
            port=self.db_port,
            database=self.postgres_db,
        )
