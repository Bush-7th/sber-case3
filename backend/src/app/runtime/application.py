"""M15 wiring of application operations to durable DTO snapshots (M02/M04/M10)."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePath
from urllib.parse import quote
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.http_api import schemas as s
from app.modules.assets.ocr import OcrSource
from app.modules.assets.ocr_persistence import SqlOcrRepository
from app.modules.assets.persistence import PostgresBlobStore
from app.modules.identity.domain import AccessDenied
from app.runtime.workflow_storage import JobRow, ResourceRow


class CommandError(Exception):
    def __init__(self, status, code, message):
        self.status, self.code, self.message = status, code, message


def now():
    return datetime.now(UTC)


def row(session, resource_id, kind, actor=None, lock=False):
    query = select(ResourceRow).where(ResourceRow.id == resource_id, ResourceRow.kind == kind)
    if lock:
        query = query.with_for_update()
    found = session.scalar(query)
    if found is None:
        raise CommandError(404, "not_found", "Объект не найден.")
    if actor is not None and found.owner_id != actor.id:
        raise AccessDenied
    return found


def put(session, kind, value, owner=None, parent=None):
    value_id = UUID(str(value["id"]))
    found = session.get(ResourceRow, value_id)
    if found:
        found.data = value
    else:
        session.add(
            ResourceRow(
                id=value_id,
                kind=kind,
                owner_id=owner,
                parent_id=parent,
                data=value,
                created_at=now(),
            )
        )
    return value_id


def revision(data, expected):
    if data["input_revision"] != expected:
        raise CommandError(409, "revision_conflict", "Заявка изменилась. Обновите данные.")


def invalidate(data):
    data["input_revision"] += 1
    data["updated_at"] = now().isoformat()
    if data["report"]:
        data["report"]["freshness"] = "outdated"
        data["report_freshness"] = "outdated"
    if data["decision"]:
        data["decision"]["freshness"] = "outdated"
        data["decision_freshness"] = "outdated"


def command_id(actor, scope, key):
    return uuid5(NAMESPACE_URL, f"case3/command/{actor.id}/{scope}/{key}")


def replay(session, actor, scope, key, digest):
    found = session.get(ResourceRow, command_id(actor, scope, key))
    if not found:
        return None
    if found.data["digest"] != digest:
        raise CommandError(409, "idempotency_conflict", "Ключ уже использован для другой команды.")
    return found.data["response"]


def remember(session, actor, scope, key, digest, response):
    put(
        session,
        "command",
        {"id": str(command_id(actor, scope, key)), "digest": digest, "response": response},
        actor.id,
    )


def body_digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def page(items, limit, offset):
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "limit": limit,
        "offset": offset,
    }


class ApplicationService:
    def __init__(self, container, actor, correlation_id):
        self.container, self.actor, self.correlation_id = container, actor, correlation_id

    def audit(self, session, package, action, run_id=None):
        event = s.AuditEvent(
            id=uuid4(),
            actor=s.UserSummary(
                id=self.actor.id, display_name=self.actor.display_name, role=self.actor.role
            ),
            action=action,
            resource=s.ResourceRef(kind="package", id=package["id"]),
            input_revision=package["input_revision"],
            run_id=run_id,
            created_at=now(),
            correlation_id=self.correlation_id,
        )
        put(session, "audit", event.model_dump(mode="json"), self.actor.id, UUID(package["id"]))

    def list(self, kind, limit, offset, parent=None):
        with self.container.unit_of_work() as uow:
            query = select(ResourceRow).where(ResourceRow.kind == kind)
            if kind in {"package", "audit"}:
                query = query.where(ResourceRow.owner_id == self.actor.id)
            if parent:
                query = query.where(ResourceRow.parent_id == parent)
            rows = uow.session.scalars(
                query.order_by(ResourceRow.created_at.desc(), ResourceRow.id)
            ).all()
            items = [r.data for r in rows]
        return page(items, limit, offset)

    def programs(self, limit, offset):
        versions = self.list("version", 100, 0)["items"]
        latest = {}
        for v in versions:
            if v["program_id"] not in latest or v["version"] > latest[v["program_id"]]["version"]:
                latest[v["program_id"]] = v
        return page(
            [
                {"id": k, "name": v["definition"]["name"], "latest_version_id": v["id"]}
                for k, v in latest.items()
            ],
            limit,
            offset,
        )

    def get(self, kind, resource_id):
        with self.container.unit_of_work() as uow:
            found = row(
                uow.session,
                resource_id,
                kind,
                self.actor if kind in {"package", "run", "file", "document"} else None,
            )
            data = json.loads(json.dumps(found.data))
            if kind == "run":
                package = row(uow.session, found.parent_id, "package", self.actor).data
                if package["input_revision"] != data["input_revision"] or package[
                    "current_run_id"
                ] != str(resource_id):
                    data["freshness"] = "outdated"
                    if data["report"]:
                        data["report"]["freshness"] = "outdated"
            return data

    def create_package(self, body):
        with self.container.unit_of_work() as uow:
            version = row(uow.session, body.program_version_id, "version").data
            value = s.PackageDetail(
                id=uuid4(),
                title=body.title,
                program_id=version["program_id"],
                program_version_id=body.program_version_id,
                input_revision=0,
                created_at=now(),
                updated_at=now(),
                current_run_id=None,
                verdict=None,
                report_freshness=None,
                report_provisional=None,
                decision_status="not_decided",
                decision_freshness=None,
                project_context=body.project_context,
            )
            data = value.model_dump(mode="json")
            put(uow.session, "package", data, self.actor.id)
            self.audit(uow.session, data, "package.created")
            uow.commit()
            return data

    def queue(self, session, package):
        settings = self.container.settings
        run_id = uuid4()
        local = settings.model_provider == "local"
        run = s.VerificationRun(
            id=run_id,
            package_id=package["id"],
            input_revision=package["input_revision"],
            progress_version=0,
            status="queued",
            coverage="partial",
            freshness="current",
            reference_date=now().astimezone(ZoneInfo("Europe/Moscow")).date(),
            timezone="Europe/Moscow",
            model_profile=s.ModelProfile(
                provider=settings.model_provider,
                model=settings.local_model if local else settings.qwen_model,
                prompt_version="local-extract-v1" if local else "extract-v1",
                preparation_version="native-or-ocr-v1",
            ),
            progress=s.RunProgress(
                total=len(package["files"]),
                accepted=len(package["files"]),
                determining=0,
                checked=0,
                processing_error=0,
            ),
            files=[
                s.FileCheck(
                    file=f,
                    processing="accepted",
                    processing_stage="preparing",
                    predicted_type=None,
                    verdict=None,
                )
                for f in package["files"]
            ],
        )
        captured = json.loads(json.dumps(package))
        overrides = session.scalars(
            select(ResourceRow).where(
                ResourceRow.kind == "type_override", ResourceRow.parent_id == UUID(package["id"])
            )
        ).all()
        captured["type_overrides"] = {r.data["file_id"]: r.data["document_type"] for r in overrides}
        put(
            session,
            "run",
            {**run.model_dump(mode="json"), "_input": captured},
            self.actor.id,
            UUID(package["id"]),
        )
        session.flush()
        session.add(
            JobRow(run_id=run_id, status="queued", lease=None, lease_until=None, created_at=now())
        )
        package["current_run_id"] = str(run_id)
        package["updated_at"] = now().isoformat()
        # Old reports stay visible and explicitly outdated while the new run is pending.
        if package["report"]:
            package["report"]["freshness"] = "outdated"
            package["report_freshness"] = "outdated"
        return s.RunRequested(
            package_id=package["id"],
            input_revision=package["input_revision"],
            run_id=run_id,
            correlation_id=self.correlation_id,
        ).model_dump(mode="json")

    def start(self, package_id, body, key):
        scope = f"{package_id}/verify"
        digest = body_digest(body.model_dump(mode="json"))
        with self.container.unit_of_work() as uow:
            found = row(uow.session, package_id, "package", self.actor, True)
            cached = replay(uow.session, self.actor, scope, key, digest)
            if cached:
                return cached
            data = json.loads(json.dumps(found.data))
            revision(data, body.expected_revision)
            response = self.queue(uow.session, data)
            found.data = data
            self.audit(uow.session, data, "verification.requested", UUID(response["run_id"]))
            remember(uow.session, self.actor, scope, key, digest, response)
            uow.commit()
            return response

    def configuration(self, package_id, body):
        with self.container.unit_of_work() as uow:
            found = row(uow.session, package_id, "package", self.actor, True)
            data = json.loads(json.dumps(found.data))
            revision(data, body.expected_revision)
            if body.program_version_id:
                version = row(uow.session, body.program_version_id, "version").data
                data["program_version_id"], data["program_id"] = (
                    version["id"],
                    version["program_id"],
                )
            if body.project_context:
                data["project_context"] = body.project_context.model_dump(mode="json")
            invalidate(data)
            response = self.queue(uow.session, data)
            found.data = data
            self.audit(uow.session, data, "package.configuration_changed", UUID(response["run_id"]))
            uow.commit()
            return response

    def upload(self, package_id, expected, key, files):
        scope = f"{package_id}/upload"
        digest = body_digest(
            {
                "revision": expected,
                "files": [(name, sha256(content).hexdigest()) for name, content in files],
            }
        )
        with self.container.unit_of_work() as uow:
            found = row(uow.session, package_id, "package", self.actor, True)
            cached = replay(uow.session, self.actor, scope, key, digest)
            if cached:
                return cached
            data = json.loads(json.dumps(found.data))
            revision(data, expected)
            accepted, rejected = [], []
            media = {
                "pdf": "application/pdf",
                "png": "image/png",
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "doc": "application/msword",
                "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "xls": "application/vnd.ms-excel",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
            for original, content in files:
                name = PurePath(original.replace("\\", "/")).name[:200] or "document"
                extension = name.rsplit(".", 1)[-1].lower()
                if (
                    extension not in media
                    or not content
                    or len(content) > self.container.settings.olmocr_max_input_bytes
                ):
                    error = s.ApiError(
                        code="unsupported_or_large_file",
                        message="Неподдерживаемый, пустой или слишком большой файл.",
                        correlation_id=self.correlation_id,
                    )
                    rejected.append(
                        s.UploadRejection(original_name=name, error=error).model_dump(mode="json")
                    )
                    continue
                blob = PostgresBlobStore(uow.session).put_immutable(
                    uuid4(), content, media[extension]
                )
                source = OcrSource(uuid4(), uuid4(), blob.id, blob.sha256)
                SqlOcrRepository(uow.session).register_source(source)
                summary = s.FileSummary(
                    id=source.file_id,
                    file_version_id=source.file_version_id,
                    original_name=name,
                    format="jpg" if extension == "jpeg" else extension,
                    size_bytes=len(content),
                    sha256=blob.sha256,
                    created_at=now(),
                ).model_dump(mode="json")
                accepted.append(summary)
                put(
                    uow.session,
                    "file",
                    {**summary, "blob_id": str(blob.id), "media_type": media[extension]},
                    self.actor.id,
                    package_id,
                )
            run_id = None
            if accepted:
                data["files"].extend(accepted)
                invalidate(data)
                run_id = self.queue(uow.session, data)["run_id"]
                found.data = data
                self.audit(uow.session, data, "files.uploaded", UUID(run_id))
            response = s.UploadResult(
                package_id=package_id,
                input_revision=data["input_revision"],
                accepted=accepted,
                rejected=rejected,
                run_id=run_id,
                correlation_id=self.correlation_id,
            ).model_dump(mode="json")
            remember(uow.session, self.actor, scope, key, digest, response)
            uow.commit()
            return response

    def content(self, file_id, preview=False, page_number=1):
        from app.modules.assets.ocr_preparation import rasterize_pdf_page

        with self.container.unit_of_work() as uow:
            data = row(uow.session, file_id, "file", self.actor).data
            with PostgresBlobStore(uow.session).open(UUID(data["blob_id"])) as stream:
                content = stream.read()
        media = data["media_type"]
        if preview and media == "application/pdf":
            source = OcrSource(
                file_id, UUID(data["file_version_id"]), UUID(data["blob_id"]), data["sha256"]
            )
            content = rasterize_pdf_page(source, content, page_number).data
            media = "image/png"
        elif preview and media not in {"image/png", "image/jpeg"}:
            raise CommandError(
                501, "preview_unavailable", "Просмотр Office пока не подключён; скачайте оригинал."
            )
        elif preview and page_number != 1:
            raise CommandError(404, "page_not_found", "Страница не найдена.")
        return (
            content,
            media,
            {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(data['original_name'])}"},
        )

    def sheet(self, file_id, sheet, limit, offset):
        from app.modules.assets.office_preparation import xlsx_sheets

        data = self.get("file", file_id)
        if data["format"] != "xlsx":
            raise CommandError(501, "sheet_unavailable", "Просмотр XLS пока не подключён.")
        content, _, _ = self.content(file_id)
        cells = xlsx_sheets(content).get(sheet)
        if cells is None:
            raise CommandError(404, "sheet_not_found", "Лист не найден.")
        return s.SheetData(
            file_id=file_id,
            file_version_id=data["file_version_id"],
            sheet=sheet,
            cells=cells[offset : offset + limit],
            offset=offset,
            limit=limit,
            total=len(cells),
        )

    def decision(self, package_id, body, key):
        scope = f"{package_id}/decision"
        digest = body_digest(body.model_dump(mode="json"))
        with self.container.unit_of_work() as uow:
            found = row(uow.session, package_id, "package", self.actor, True)
            cached = replay(uow.session, self.actor, scope, key, digest)
            if cached:
                return cached
            data = json.loads(json.dumps(found.data))
            revision(data, body.expected_revision)
            if body.report_id and (
                not data["report"]
                or data["report"]["id"] != str(body.report_id)
                or data["report"]["freshness"] != "current"
            ):
                raise CommandError(409, "report_outdated", "Выберите актуальный отчёт.")
            value = s.ApplicationDecision(
                id=uuid4(),
                package_id=package_id,
                input_revision=body.expected_revision,
                report_id=body.report_id,
                action=body.action,
                reason=body.reason,
                author=s.UserSummary(
                    id=self.actor.id, display_name=self.actor.display_name, role=self.actor.role
                ),
                decided_at=now(),
                freshness="current",
            ).model_dump(mode="json")
            data["decision"] = value
            data["decision_status"], data["decision_freshness"] = body.action, "current"
            data["updated_at"] = now().isoformat()
            found.data = data
            self.audit(uow.session, data, "decision." + body.action)
            remember(uow.session, self.actor, scope, key, digest, value)
            uow.commit()
            return value

    def document_type(self, document_id, body):
        with self.container.unit_of_work() as uow:
            document = row(uow.session, document_id, "document", self.actor)
            found = row(uow.session, document.parent_id, "package", self.actor, True)
            data = json.loads(json.dumps(found.data))
            revision(data, body.expected_revision)
            current = row(uow.session, UUID(data["current_run_id"]), "run", self.actor).data
            if document_id not in [UUID(d["id"]) for d in current["documents"]]:
                raise CommandError(
                    409, "document_outdated", "Документ относится к прежней проверке."
                )
            file_ids = {f["location"]["file_id"] for f in document.data["fragments"]}
            for file_id in file_ids:
                check = next(f for f in current["files"] if f["file"]["id"] == file_id)
                if len(check["document_unit_ids"]) > 1:
                    raise CommandError(
                        409,
                        "compound_type_override_unavailable",
                        "Разделение составного файла пока не подключено.",
                    )
                override_id = uuid5(UUID(file_id), "type-override")
                put(
                    uow.session,
                    "type_override",
                    {
                        "id": str(override_id),
                        "file_id": file_id,
                        "document_type": str(body.document_type),
                        "reason": body.reason,
                    },
                    self.actor.id,
                    document.parent_id,
                )
            uow.session.flush()
            invalidate(data)
            response = self.queue(uow.session, data)
            found.data = data
            self.audit(uow.session, data, "document.type_changed", UUID(response["run_id"]))
            uow.commit()
            return response

    def draft_create(self, body):
        with self.container.unit_of_work() as uow:
            base = (
                row(uow.session, body.base_version_id, "version").data
                if body.base_version_id
                else None
            )
            definition = (
                s.ProgramDefinition.model_validate(base["definition"])
                if base
                else s.ProgramDefinition(
                    name=body.name, description="", document_types=[], requirements=[], rules=[]
                )
            )
            definition.name = body.name
            value = s.ProgramDraft(
                id=uuid4(),
                program_id=base["program_id"] if base else None,
                name=body.name,
                revision=0,
                status="draft",
                updated_at=now(),
                base_version_id=body.base_version_id,
                definition=definition,
            ).model_dump(mode="json")
            put(uow.session, "draft", value)
            uow.commit()
            return value

    def draft_update(self, draft_id, body, rule_id=None):
        with self.container.unit_of_work() as uow:
            found = row(uow.session, draft_id, "draft", lock=True)
            value = json.loads(json.dumps(found.data))
            if value["revision"] != body.expected_revision or value["status"] != "draft":
                raise CommandError(
                    409, "revision_conflict", "Черновик изменился или уже опубликован."
                )
            if rule_id:
                if body.rule.id != rule_id:
                    raise CommandError(
                        422, "rule_id_mismatch", "ID правила не совпадает с адресом."
                    )
                rules = value["definition"]["rules"]
                rules[:] = [r for r in rules if r["id"] != rule_id] + [
                    body.rule.model_dump(mode="json")
                ]
            else:
                value["definition"] = body.definition.model_dump(mode="json")
                value["name"] = body.definition.name
            value["revision"] += 1
            value["updated_at"] = now().isoformat()
            found.data = value
            uow.commit()
            return value

    def draft_validate(self, draft_id, body):
        value = self.get("draft", draft_id)
        if value["revision"] != body.expected_revision:
            raise CommandError(409, "revision_conflict", "Черновик изменился.")
        from app.runtime.rule_engine import validate_definition

        issues = validate_definition(s.ProgramDefinition.model_validate(value["definition"]))
        return s.DraftValidation(
            draft_id=draft_id,
            revision=body.expected_revision,
            valid=not issues,
            issues=issues,
            correlation_id=self.correlation_id,
        )

    def draft_publish(self, draft_id, body, key):
        scope, digest = f"{draft_id}/publish", body_digest(body.model_dump(mode="json"))
        with self.container.unit_of_work() as uow:
            found = row(uow.session, draft_id, "draft", lock=True)
            cached = replay(uow.session, self.actor, scope, key, digest)
            if cached:
                return cached
            draft = json.loads(json.dumps(found.data))
            if draft["revision"] != body.expected_revision or draft["status"] != "draft":
                raise CommandError(409, "revision_conflict", "Черновик изменился или опубликован.")
            from app.runtime.rule_engine import validate_definition

            definition = s.ProgramDefinition.model_validate(draft["definition"])
            if validate_definition(definition):
                raise CommandError(422, "invalid_catalog", "Исправьте замечания проверки каталога.")
            program_id = UUID(draft["program_id"]) if draft["program_id"] else uuid4()
            # Serialize simultaneous publications for the same program.
            from sqlalchemy import text

            uow.session.execute(
                text("SELECT pg_advisory_xact_lock(:key)"), {"key": program_id.int % (2**63 - 1)}
            )
            versions = uow.session.scalars(
                select(ResourceRow).where(
                    ResourceRow.kind == "version", ResourceRow.parent_id == program_id
                )
            ).all()
            number = max((r.data["version"] for r in versions), default=0) + 1
            value = s.ProgramVersion(
                id=uuid4(),
                program_id=program_id,
                version=number,
                published_at=now(),
                definition=definition,
            ).model_dump(mode="json")
            put(uow.session, "version", value, parent=program_id)
            draft.update(
                status="published", program_id=str(program_id), updated_at=now().isoformat()
            )
            found.data = draft
            remember(uow.session, self.actor, scope, key, digest, value)
            uow.commit()
            return value
