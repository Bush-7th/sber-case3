"""Contract application. Runtime services are wired by INF01 and later tasks."""

from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.http_api.routes import ContractUnavailable, router
from app.http_api.schemas import ApiError


def error_response(
    request: Request,
    status: int,
    code: str,
    message: str,
    **details,
) -> JSONResponse:
    body = ApiError(
        code=code,
        message=message,
        details=details,
        correlation_id=request.state.correlation_id,
    )
    return JSONResponse(status_code=status, content=body.model_dump(mode="json"))


def create_app() -> FastAPI:
    application = FastAPI(
        title="Sber Case 3 API",
        version="0.1.0",
        description="CON01 contract. Application operations return 501 until implemented.",
    )

    @application.middleware("http")
    async def correlation_id(request: Request, call_next):
        try:
            request.state.correlation_id = UUID(request.headers.get("X-Correlation-ID", ""))
        except ValueError:
            request.state.correlation_id = uuid4()
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = str(request.state.correlation_id)
        return response

    @application.exception_handler(ContractUnavailable)
    async def unimplemented(request: Request, exc: ContractUnavailable):
        return error_response(
            request,
            501,
            "not_implemented",
            "Прикладной обработчик ещё не подключён.",
        )

    @application.exception_handler(RequestValidationError)
    async def invalid_command(request: Request, exc: RequestValidationError):
        # Exclude input and validator context: they may contain passwords or document content.
        violations = [{"loc": list(item["loc"]), "type": item["type"]} for item in exc.errors()]
        return error_response(
            request,
            422,
            "invalid_command",
            "Проверьте параметры запроса.",
            violations=violations,
        )

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return error_response(
            request,
            exc.status_code,
            "http_error",
            "Запрос не может быть выполнен.",
        )

    application.include_router(router)
    default_openapi = application.openapi

    def contract_openapi():
        schema = default_openapi()
        for path in schema["paths"].values():
            for operation in path.values():
                security = operation.get("security", [])
                if any("CsrfToken" in item for item in security):
                    # The cookie and CSRF token are both required, not alternative credentials.
                    operation["security"] = [{"SessionCookie": [], "CsrfToken": []}]
        return schema

    application.openapi = contract_openapi
    return application


app = create_app()
