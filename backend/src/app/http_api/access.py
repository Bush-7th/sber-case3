from fastapi import Request

from app.modules.identity.domain import AccessDenied, AuthenticationRequired, ResolvedSession
from app.runtime.container import AppContainer
from app.runtime.settings import ConfigurationError


def runtime(request: Request) -> AppContainer:
    container = request.app.state.container
    if container is None:
        raise ConfigurationError("Runtime configuration is not available")
    return container


def check_origin(request: Request) -> None:
    if request.method not in {"POST", "PATCH", "DELETE", "PUT"}:
        return
    if request.headers.get("Sec-Fetch-Site") == "cross-site":
        raise AccessDenied
    origin = request.headers.get("Origin")
    if origin is not None and origin not in request.app.state.settings.allowed_origins:
        raise AccessDenied


def authorize_request(request: Request) -> ResolvedSession:
    check_origin(request)
    cookie = request.cookies.get("session")
    if not cookie:
        raise AuthenticationRequired
    container = runtime(request)
    session = container.resolve_session(cookie)
    if request.method in {"POST", "PATCH", "DELETE", "PUT"}:
        container.identity.check_csrf(session, request.headers.get("X-CSRF-Token"))
    path = request.url.path
    if path.startswith("/api/v1/admin/"):
        container.access.require_administrator(session.actor)
    elif path.startswith(
        (
            "/api/v1/packages",
            "/api/v1/files/",
            "/api/v1/document-units/",
            "/api/v1/verification-runs/",
        )
    ):
        container.access.require_specialist(session.actor)
    return session
