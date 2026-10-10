"""OpenAPI surface for CON01; application handlers will be wired in following tasks."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, Query, Request, Response, Security, UploadFile
from fastapi.security import APIKeyCookie, APIKeyHeader

from app.http_api import schemas as s
from app.http_api.access import runtime
from app.modules.identity.domain import AccessDenied
from app.runtime.application import ApplicationService


def service(request: Request) -> ApplicationService:
    return ApplicationService(
        runtime(request), request.state.session.actor, request.state.correlation_id
    )


class ContractUnavailable(Exception):
    """A declared operation has no application implementation yet."""


def unavailable() -> NoReturn:
    raise ContractUnavailable


ERROR_RESPONSES = {
    status: {"model": s.ApiError, "description": description}
    for status, description in {
        401: "Session required or expired",
        403: "Access or CSRF check denied",
        404: "Resource not found",
        409: "Revision or idempotency conflict",
        413: "Input exceeds configured limits",
        422: "Invalid command",
        501: "Contract exists; application handler is not implemented yet",
        503: "Required dependency unavailable before acceptance",
    }.items()
}
cookie = APIKeyCookie(name="session", scheme_name="SessionCookie", auto_error=False)
csrf = APIKeyHeader(name="X-CSRF-Token", scheme_name="CsrfToken", auto_error=False)
CsrfToken = Annotated[str | None, Security(csrf)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=128)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]

router = APIRouter(prefix="/api/v1", responses=ERROR_RESPONSES)
protected = APIRouter(dependencies=[Security(cookie)])


@router.post("/sessions", response_model=s.SessionResponse, operation_id="create_session")
def create_session(
    body: s.SessionCreate, request: Request, response: Response
) -> s.SessionResponse:
    container = runtime(request)
    issued = container.authenticate(body.username, body.password.get_secret_value())
    response.set_cookie(
        "session",
        issued.cookie,
        max_age=container.settings.session_hours * 3600,
        httponly=True,
        secure=container.settings.session_cookie_secure,
        samesite="strict",
        path="/api/v1",
    )
    response.headers["Cache-Control"] = "no-store"
    return s.SessionResponse(
        user=s.UserSummary(
            id=issued.session.actor.id,
            display_name=issued.session.actor.display_name,
            role=issued.session.actor.role,
        ),
        expires_at=issued.session.expires_at,
        csrf_token=issued.csrf_token,
    )


@protected.get("/sessions", response_model=s.SessionResponse, operation_id="get_session")
def get_session(request: Request, response: Response) -> s.SessionResponse:
    origin = request.headers.get("Origin")
    if request.headers.get("Sec-Fetch-Site") == "cross-site" or (
        origin is not None and origin not in request.app.state.settings.allowed_origins
    ):
        raise AccessDenied
    issued = runtime(request).recover_session(request.cookies["session"])
    response.headers["Cache-Control"] = "no-store"
    return s.SessionResponse(
        user=s.UserSummary(
            id=issued.session.actor.id,
            display_name=issued.session.actor.display_name,
            role=issued.session.actor.role,
        ),
        expires_at=issued.session.expires_at,
        csrf_token=issued.csrf_token,
    )


@protected.delete("/sessions", status_code=204, operation_id="delete_session")
def delete_session(request: Request, csrf_token: CsrfToken) -> Response:
    container = runtime(request)
    container.revoke_session(request.state.session)
    response = Response(status_code=204, headers={"Cache-Control": "no-store"})
    response.delete_cookie(
        "session",
        path="/api/v1",
        httponly=True,
        secure=container.settings.session_cookie_secure,
        samesite="strict",
    )
    return response


@protected.get("/programs", response_model=s.Page[s.ProgramSummary], operation_id="list_programs")
async def list_programs(
    request: Request, limit: Limit = 20, offset: Offset = 0
) -> s.Page[s.ProgramSummary]:
    return service(request).programs(limit, offset)


@protected.get(
    "/programs/{program_id}/versions",
    response_model=s.Page[s.ProgramVersion],
    operation_id="list_program_versions",
)
async def list_program_versions(
    request: Request,
    program_id: UUID,
    limit: Limit = 20,
    offset: Offset = 0,
) -> s.Page[s.ProgramVersion]:
    return service(request).list("version", limit, offset, program_id)


@protected.get("/packages", response_model=s.Page[s.PackageSummary], operation_id="list_packages")
async def list_packages(
    request: Request, limit: Limit = 20, offset: Offset = 0
) -> s.Page[s.PackageSummary]:
    value = service(request).list("package", limit, offset)
    value["items"] = [
        s.PackageSummary.model_validate(
            {k: v for k, v in item.items() if k in s.PackageSummary.model_fields}
        )
        for item in value["items"]
    ]
    return value


@protected.post(
    "/packages",
    response_model=s.PackageDetail,
    status_code=201,
    operation_id="create_package",
)
async def create_package(
    request: Request, body: s.PackageCreate, csrf_token: CsrfToken
) -> s.PackageDetail:
    return service(request).create_package(body)


@protected.get(
    "/packages/{package_id}",
    response_model=s.PackageDetail,
    operation_id="get_package",
)
async def get_package(request: Request, package_id: UUID) -> s.PackageDetail:
    return service(request).get("package", package_id)


@protected.post(
    "/packages/{package_id}/files",
    response_model=s.UploadResult,
    status_code=202,
    operation_id="upload_files",
)
async def upload_files(
    request: Request,
    package_id: UUID,
    files: Annotated[list[UploadFile], File(min_length=1)],
    expected_revision: Annotated[int, Form(ge=0)],
    csrf_token: CsrfToken,
    idempotency_key: IdempotencyKey,
) -> s.UploadResult:
    svc = service(request)
    svc.get("package", package_id)
    contents = []
    total = 0
    for file in files:
        content = await file.read(runtime(request).settings.olmocr_max_input_bytes + 1)
        total += len(content)
        if total > 100_000_000:
            from app.runtime.application import CommandError

            raise CommandError(413, "upload_too_large", "Пакет загрузки превышает 100 МБ.")
        contents.append((file.filename or "document", content))
        await file.close()
    return svc.upload(package_id, expected_revision, idempotency_key, contents)


@protected.patch(
    "/packages/{package_id}/configuration",
    response_model=s.RunRequested,
    operation_id="update_configuration",
)
async def update_configuration(
    request: Request,
    package_id: UUID,
    body: s.ConfigurationUpdate,
    csrf_token: CsrfToken,
) -> s.RunRequested:
    return service(request).configuration(package_id, body)


@protected.post(
    "/packages/{package_id}/verification-runs",
    response_model=s.RunRequested,
    status_code=202,
    operation_id="create_verification_run",
)
async def create_verification_run(
    request: Request,
    package_id: UUID,
    body: s.VerificationCreate,
    csrf_token: CsrfToken,
    idempotency_key: IdempotencyKey,
) -> s.RunRequested:
    return service(request).start(package_id, body, idempotency_key)


@protected.get(
    "/verification-runs/{run_id}",
    response_model=s.VerificationRun,
    operation_id="get_verification_run",
)
async def get_verification_run(request: Request, run_id: UUID) -> s.VerificationRun:
    value = service(request).get("run", run_id)
    value = {k: v for k, v in value.items() if not k.startswith("_")}
    return value


@protected.get(
    "/files/{file_id}/content",
    response_class=Response,
    operation_id="download_file",
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {"type": "string", "format": "binary"},
                }
            },
            "description": "Authorized original; Content-Disposition: attachment",
        }
    },
)
async def download_file(request: Request, file_id: UUID) -> Response:
    content, media, headers = service(request).content(file_id)
    return Response(content=content, media_type=media, headers=headers)


@protected.get(
    "/files/{file_id}/preview",
    response_class=Response,
    operation_id="get_file_preview",
    responses={
        200: {
            "content": {
                "application/pdf": {"schema": {"type": "string", "format": "binary"}},
                "image/png": {"schema": {"type": "string", "format": "binary"}},
            },
            "description": "Authorized preview; Office representations are derivatives",
        }
    },
)
async def get_file_preview(
    request: Request, file_id: UUID, page: Annotated[int, Query(ge=1)] = 1
) -> Response:
    content, media, headers = service(request).content(file_id, True, page)
    headers.pop("Content-Disposition", None)
    return Response(content=content, media_type=media, headers=headers)


@protected.get(
    "/files/{file_id}/sheets/{sheet}",
    response_model=s.SheetData,
    operation_id="get_sheet",
)
async def get_sheet(
    request: Request,
    file_id: UUID,
    sheet: str,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Offset = 0,
) -> s.SheetData:
    return service(request).sheet(file_id, sheet, limit, offset)


@protected.patch(
    "/document-units/{document_id}/type",
    response_model=s.RunRequested,
    operation_id="update_document_type",
)
async def update_document_type(
    request: Request,
    document_id: UUID,
    body: s.TypeUpdate,
    csrf_token: CsrfToken,
) -> s.RunRequested:
    return service(request).document_type(document_id, body)


@protected.patch(
    "/document-units/{document_id}/grouping",
    response_model=s.RunRequested,
    operation_id="update_document_grouping",
)
async def update_document_grouping(
    request: Request,
    document_id: UUID,
    body: s.GroupingUpdate,
    csrf_token: CsrfToken,
) -> s.RunRequested:
    unavailable()


@protected.post(
    "/packages/{package_id}/decisions",
    response_model=s.ApplicationDecision,
    status_code=201,
    operation_id="create_decision",
)
async def create_decision(
    request: Request,
    package_id: UUID,
    body: s.DecisionCreate,
    csrf_token: CsrfToken,
    idempotency_key: IdempotencyKey,
) -> s.ApplicationDecision:
    return service(request).decision(package_id, body, idempotency_key)


@protected.get(
    "/admin/program-drafts",
    response_model=s.Page[s.ProgramDraftSummary],
    operation_id="list_program_drafts",
    tags=["administrator"],
)
async def list_program_drafts(
    request: Request,
    limit: Limit = 20,
    offset: Offset = 0,
) -> s.Page[s.ProgramDraftSummary]:
    value = service(request).list("draft", limit, offset)
    value["items"] = [
        s.ProgramDraftSummary.model_validate(
            {k: v for k, v in item.items() if k in s.ProgramDraftSummary.model_fields}
        )
        for item in value["items"]
    ]
    return value


@protected.post(
    "/admin/program-drafts",
    response_model=s.ProgramDraft,
    status_code=201,
    operation_id="create_program_draft",
    tags=["administrator"],
)
async def create_program_draft(
    request: Request, body: s.ProgramDraftCreate, csrf_token: CsrfToken
) -> s.ProgramDraft:
    return service(request).draft_create(body)


@protected.get(
    "/admin/program-drafts/{draft_id}",
    response_model=s.ProgramDraft,
    operation_id="get_program_draft",
    tags=["administrator"],
)
async def get_program_draft(request: Request, draft_id: UUID) -> s.ProgramDraft:
    return service(request).get("draft", draft_id)


@protected.patch(
    "/admin/program-drafts/{draft_id}",
    response_model=s.ProgramDraft,
    operation_id="update_program_draft",
    tags=["administrator"],
)
async def update_program_draft(
    request: Request,
    draft_id: UUID,
    body: s.ProgramDraftUpdate,
    csrf_token: CsrfToken,
) -> s.ProgramDraft:
    return service(request).draft_update(draft_id, body)


@protected.patch(
    "/admin/program-drafts/{draft_id}/rules/{rule_id}",
    response_model=s.ProgramDraft,
    operation_id="update_rule",
    tags=["administrator"],
)
async def update_rule(
    request: Request,
    draft_id: UUID,
    rule_id: str,
    body: s.RuleUpdate,
    csrf_token: CsrfToken,
) -> s.ProgramDraft:
    return service(request).draft_update(draft_id, body, rule_id)


@protected.post(
    "/admin/program-drafts/{draft_id}/validate",
    response_model=s.DraftValidation,
    operation_id="validate_program_draft",
    tags=["administrator"],
)
async def validate_program_draft(
    request: Request,
    draft_id: UUID,
    body: s.RevisionCommand,
    csrf_token: CsrfToken,
) -> s.DraftValidation:
    return service(request).draft_validate(draft_id, body)


@protected.post(
    "/admin/program-drafts/{draft_id}/publish",
    response_model=s.ProgramVersion,
    status_code=201,
    operation_id="publish_program_draft",
    tags=["administrator"],
)
async def publish_program_draft(
    request: Request,
    draft_id: UUID,
    body: s.RevisionCommand,
    csrf_token: CsrfToken,
    idempotency_key: IdempotencyKey,
) -> s.ProgramVersion:
    return service(request).draft_publish(draft_id, body, idempotency_key)


@protected.get(
    "/packages/{package_id}/audit",
    response_model=s.Page[s.AuditEvent],
    operation_id="list_audit",
)
async def list_audit(
    request: Request,
    package_id: UUID,
    limit: Limit = 20,
    offset: Offset = 0,
) -> s.Page[s.AuditEvent]:
    svc = service(request)
    svc.get("package", package_id)
    return svc.list("audit", limit, offset, package_id)


router.include_router(protected)
