"""M13 transport and M15 runtime wiring."""

import json
import logging
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException

from app.http_api.access import authorize_request, check_origin
from app.http_api.routes import ContractUnavailable, router
from app.http_api.schemas import ApiError, LivenessResponse, ReadinessResponse
from app.modules.identity.domain import AccessDenied, AuthenticationRequired, InvalidCredentials
from app.runtime.container import AppContainer
from app.runtime.health import readiness
from app.runtime.settings import ConfigurationError, Settings
from app.runtime.telemetry import configure_logging

logger = logging.getLogger("case3.http")


def error_response(
    request: Request, status: int, code: str, message: str, **details
) -> JSONResponse:
    body = ApiError(
        code=code,
        message=message,
        details=details,
        correlation_id=request.state.correlation_id,
    )
    return JSONResponse(
        status_code=status,
        content=body.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


def service_error(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, InvalidCredentials):
        return error_response(request, 401, "invalid_credentials", "Неверный логин или пароль.")
    if isinstance(exc, AuthenticationRequired):
        return error_response(request, 401, "session_required", "Войдите в систему.")
    if isinstance(exc, AccessDenied):
        return error_response(
            request, 403, "access_denied", "Недостаточно прав или неверный CSRF-токен."
        )
    return error_response(
        request, 503, "dependency_unavailable", "Серверная зависимость недоступна."
    )


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging()
        try:
            application.state.settings = settings or Settings()
        except ValidationError:
            raise ConfigurationError(
                "Invalid runtime settings; check the selected profile"
            ) from None
        try:
            application.state.container = AppContainer(application.state.settings)
        except ConfigurationError:
            # An unconfigured checkout can serve docs/liveness, never accept protected work.
            application.state.container = None
        try:
            yield
        finally:
            if application.state.container:
                application.state.container.close()

    application = FastAPI(
        title="Sber Case 3 API",
        version="0.2.0",
        lifespan=lifespan,
        description=(
            "INF01: sessions and access checks implemented; business operations return 501."
        ),
    )
    application.state.container = None

    @application.middleware("http")
    async def request_context(request: Request, call_next):
        try:
            request.state.correlation_id = UUID(request.headers.get("X-Correlation-ID", ""))
        except ValueError:
            request.state.correlation_id = uuid4()
        try:
            if request.url.path.startswith("/api/v1/"):
                if request.url.path == "/api/v1/sessions" and request.method == "POST":
                    check_origin(request)
                else:
                    # Authorize before multipart parsing, including paths with invalid resource IDs.
                    request.state.session = await run_in_threadpool(authorize_request, request)
            response = await call_next(request)
        except (AccessDenied, AuthenticationRequired, ConfigurationError, SQLAlchemyError) as exc:
            response = service_error(request, exc)
        except Exception as exc:
            logger.error(
                json.dumps(
                    {
                        "event": "request_failed",
                        "error_type": type(exc).__name__,
                        "correlation_id": str(request.state.correlation_id),
                    }
                )
            )
            response = error_response(
                request, 500, "internal_error", "Не удалось выполнить запрос."
            )
        response.headers["X-Correlation-ID"] = str(request.state.correlation_id)
        response.headers["X-Content-Type-Options"] = "nosniff"
        if request.url.path.startswith("/api/v1/"):
            response.headers["Cache-Control"] = "no-store"
        # No URLs, query parameters, bodies, credentials or driver exception text.
        logger.info(
            json.dumps(
                {
                    "event": "http_request",
                    "method": request.method,
                    "status": response.status_code,
                    "correlation_id": str(request.state.correlation_id),
                }
            )
        )
        return response

    for error in (
        InvalidCredentials,
        AuthenticationRequired,
        AccessDenied,
        ConfigurationError,
        SQLAlchemyError,
    ):
        application.add_exception_handler(error, service_error)

    @application.exception_handler(ContractUnavailable)
    async def unimplemented(request: Request, exc: ContractUnavailable):
        return error_response(
            request, 501, "not_implemented", "Прикладной обработчик ещё не подключён."
        )

    @application.exception_handler(RequestValidationError)
    async def invalid_command(request: Request, exc: RequestValidationError):
        violations = [{"loc": list(item["loc"]), "type": item["type"]} for item in exc.errors()]
        return error_response(
            request, 422, "invalid_command", "Проверьте параметры запроса.", violations=violations
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(
            request, exc.status_code, "http_error", "Запрос не может быть выполнен."
        )

    @application.get("/health/live", response_model=LivenessResponse, operation_id="liveness")
    def liveness():
        return LivenessResponse()

    @application.get(
        "/health/ready",
        response_model=ReadinessResponse,
        operation_id="readiness",
        responses={503: {"model": ApiError, "description": "Dependencies not yet ready"}},
    )
    def readiness_endpoint(request: Request):
        report = readiness(request.app.state.container)
        if not report["api_ready"] or not report["pipeline_ready"]:
            return error_response(
                request, 503, "not_ready", "Стенд ещё не готов к полной проверке.", **report
            )
        return ReadinessResponse(**report)

    application.include_router(router)
    default_openapi = application.openapi

    def contract_openapi():
        schema = default_openapi()
        for path in schema["paths"].values():
            for operation in path.values():
                security = operation.get("security", [])
                if any("CsrfToken" in item for item in security):
                    operation["security"] = [{"SessionCookie": [], "CsrfToken": []}]
        return schema

    application.openapi = contract_openapi
    return application


app = create_app()
