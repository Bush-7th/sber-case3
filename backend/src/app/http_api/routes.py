"""OpenAPI surface for CON01; application handlers will be wired in following tasks."""

from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import APIRouter, File, Form, Header, Query, Request, Response, Security, UploadFile
from fastapi.security import APIKeyCookie, APIKeyHeader

from app.http_api import schemas as s
from app.http_api.access import runtime


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
async def list_programs(limit: Limit = 20, offset: Offset = 0) -> s.Page[s.ProgramSummary]:
    unavailable()


@protected.get(
    "/programs/{program_id}/versions",
    response_model=s.Page[s.ProgramVersion],
    operation_id="list_program_versions",
)
async def list_program_versions(
    program_id: UUID,
    limit: Limit = 20,
    offset: Offset = 0,
) -> s.Page[s.ProgramVersion]:
    unavailable()


@protected.get("/packages", response_model=s.Page[s.PackageSummary], operation_id="list_packages")
async def list_packages(limit: Limit = 20, offset: Offset = 0) -> s.Page[s.PackageSummary]:
    unavailable()


@protected.post(
    "/packages",
    response_model=s.PackageDetail,
    status_code=201,
    operation_id="create_package",
)
async def create_package(body: s.PackageCreate, csrf_token: CsrfToken) -> s.PackageDetail:
    unavailable()


@protected.get(
    "/packages/{package_id}",
    response_model=s.PackageDetail,
    operation_id="get_package",
)
async def get_package(package_id: UUID) -> s.PackageDetail:
    unavailable()


@protected.post(
    "/packages/{package_id}/files",
    response_model=s.UploadResult,
    status_code=202,
    operation_id="upload_files",
)
async def upload_files(
    package_id: UUID,
    files: Annotated[list[UploadFile], File(min_length=1)],
    expected_revision: Annotated[int, Form(ge=0)],
    csrf_token: CsrfToken,
    idempotency_key: IdempotencyKey,
) -> s.UploadResult:
    unavailable()


@protected.patch(
    "/packages/{package_id}/configuration",
    response_model=s.RunRequested,
    operation_id="update_configuration",
)
async def update_configuration(
    package_id: UUID,
    body: s.ConfigurationUpdate,
    csrf_token: CsrfToken,
) -> s.RunRequested:
    unavailable()


@protected.post(
    "/packages/{package_id}/verification-runs",
    response_model=s.RunRequested,
    status_code=202,
    operation_id="create_verification_run",
)
async def create_verification_run(
    package_id: UUID,
    body: s.VerificationCreate,
    csrf_token: CsrfToken,
    idempotency_key: IdempotencyKey,
) -> s.RunRequested:
    unavailable()


@protected.get(
    "/verification-runs/{run_id}",
    response_model=s.VerificationRun,
    operation_id="get_verification_run",
)
async def get_verification_run(run_id: UUID) -> s.VerificationRun:
    unavailable()


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
async def download_file(file_id: UUID) -> Response:
    unavailable()


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
async def get_file_preview(file_id: UUID, page: Annotated[int, Query(ge=1)] = 1) -> Response:
    unavailable()


@protected.get(
    "/files/{file_id}/sheets/{sheet}",
    response_model=s.SheetData,
    operation_id="get_sheet",
)
async def get_sheet(
    file_id: UUID,
    sheet: str,
    limit: Annotated[int, Query(ge=1, le=1000)] = 200,
    offset: Offset = 0,
) -> s.SheetData:
    unavailable()


@protected.patch(
    "/document-units/{document_id}/type",
    response_model=s.RunRequested,
    operation_id="update_document_type",
)
async def update_document_type(
    document_id: UUID,
    body: s.TypeUpdate,
    csrf_token: CsrfToken,
) -> s.RunRequested:
    unavailable()


@protected.patch(
    "/document-units/{document_id}/grouping",
    response_model=s.RunRequested,
    operation_id="update_document_grouping",
)
async def update_document_grouping(
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
    package_id: UUID,
    body: s.DecisionCreate,
    csrf_token: CsrfToken,
    idempotency_key: IdempotencyKey,
) -> s.ApplicationDecision:
    unavailable()


@protected.get(
    "/admin/program-drafts",
    response_model=s.Page[s.ProgramDraftSummary],
    operation_id="list_program_drafts",
    tags=["administrator"],
)
async def list_program_drafts(
    limit: Limit = 20,
    offset: Offset = 0,
) -> s.Page[s.ProgramDraftSummary]:
    unavailable()


@protected.post(
    "/admin/program-drafts",
    response_model=s.ProgramDraft,
    status_code=201,
    operation_id="create_program_draft",
    tags=["administrator"],
)
async def create_program_draft(body: s.ProgramDraftCreate, csrf_token: CsrfToken) -> s.ProgramDraft:
    unavailable()


@protected.get(
    "/admin/program-drafts/{draft_id}",
    response_model=s.ProgramDraft,
    operation_id="get_program_draft",
    tags=["administrator"],
)
async def get_program_draft(draft_id: UUID) -> s.ProgramDraft:
    unavailable()


@protected.patch(
    "/admin/program-drafts/{draft_id}",
    response_model=s.ProgramDraft,
    operation_id="update_program_draft",
    tags=["administrator"],
)
async def update_program_draft(
    draft_id: UUID,
    body: s.ProgramDraftUpdate,
    csrf_token: CsrfToken,
) -> s.ProgramDraft:
    unavailable()


@protected.patch(
    "/admin/program-drafts/{draft_id}/rules/{rule_id}",
    response_model=s.ProgramDraft,
    operation_id="update_rule",
    tags=["administrator"],
)
async def update_rule(
    draft_id: UUID,
    rule_id: str,
    body: s.RuleUpdate,
    csrf_token: CsrfToken,
) -> s.ProgramDraft:
    unavailable()


@protected.post(
    "/admin/program-drafts/{draft_id}/validate",
    response_model=s.DraftValidation,
    operation_id="validate_program_draft",
    tags=["administrator"],
)
async def validate_program_draft(
    draft_id: UUID,
    body: s.RevisionCommand,
    csrf_token: CsrfToken,
) -> s.DraftValidation:
    unavailable()


@protected.post(
    "/admin/program-drafts/{draft_id}/publish",
    response_model=s.ProgramVersion,
    status_code=201,
    operation_id="publish_program_draft",
    tags=["administrator"],
)
async def publish_program_draft(
    draft_id: UUID,
    body: s.RevisionCommand,
    csrf_token: CsrfToken,
    idempotency_key: IdempotencyKey,
) -> s.ProgramVersion:
    unavailable()


@protected.get(
    "/packages/{package_id}/audit",
    response_model=s.Page[s.AuditEvent],
    operation_id="list_audit",
)
async def list_audit(
    package_id: UUID,
    limit: Limit = 20,
    offset: Offset = 0,
) -> s.Page[s.AuditEvent]:
    unavailable()


router.include_router(protected)
