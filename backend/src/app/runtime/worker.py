"""M11 standalone durable worker. Short leases/transactions around long model calls."""

import asyncio
import json
import logging
from contextlib import suppress
from dataclasses import asdict
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select

from app.http_api import schemas as s
from app.modules.assets.local_preparation import prepare_local_image
from app.modules.assets.ocr import OcrFailure, OcrProfile, OcrSource
from app.modules.assets.ocr_preparation import prepare_ocr_content, rasterize_pdf_page
from app.modules.assets.ocr_service import OcrContentService
from app.modules.assets.persistence import PostgresBlobStore
from app.modules.assets.text_projection import project_ocr_text
from app.modules.recognition.facts import DocumentType, PageLocation
from app.modules.recognition.model import ModelFailure, ModelRequest, PreparedSource
from app.runtime.application import now, put, row
from app.runtime.container import AppContainer
from app.runtime.rule_engine import evaluate, issue
from app.runtime.settings import ConfigurationError, Settings
from app.runtime.workflow_storage import JobRow

logger = logging.getLogger("case3.worker")


class LeaseLost(Exception):
    pass


def claim(container):
    with container.unit_of_work() as uow:
        job = uow.session.scalar(
            select(JobRow)
            .where(
                or_(
                    JobRow.status == "queued",
                    (JobRow.status == "running") & (JobRow.lease_until < now()),
                )
            )
            .order_by(JobRow.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if not job:
            return None
        job.status, job.lease, job.lease_until = "running", uuid4(), now() + timedelta(seconds=60)
        result = job.run_id, job.lease
        uow.commit()
        return result


def heartbeat(container, run_id, lease):
    with container.unit_of_work() as uow:
        job = uow.session.scalar(select(JobRow).where(JobRow.run_id == run_id).with_for_update())
        if job.lease != lease or job.status != "running" or job.lease_until < now():
            raise LeaseLost
        job.lease_until = now() + timedelta(seconds=60)
        uow.commit()


async def keep_lease(container, run_id, lease):
    while True:
        await asyncio.sleep(10)
        await asyncio.to_thread(heartbeat, container, run_id, lease)


def snapshot(container, run_id):
    with container.unit_of_work() as uow:
        run = row(uow.session, run_id, "run").data
        package = run.get("_input") or row(uow.session, UUID(run["package_id"]), "package").data
        version = row(uow.session, UUID(package["program_version_id"]), "version").data
        return json.loads(json.dumps(run)), json.loads(json.dumps(package)), version


def publish(container, run, lease, package_snapshot, definition, final=False):
    with container.unit_of_work() as uow:
        job = uow.session.scalar(select(JobRow).where(JobRow.run_id == run.id).with_for_update())
        if (
            job.lease != lease
            or job.status != "running"
            or job.lease_until is None
            or job.lease_until < now()
        ):
            raise LeaseLost
        found = row(uow.session, run.package_id, "package", lock=True)
        package = json.loads(json.dumps(found.data))
        current = package["input_revision"] == run.input_revision and package[
            "current_run_id"
        ] == str(run.id)
        run.freshness = s.Freshness.current if current else s.Freshness.outdated
        run.progress_version += 1
        counts = {
            name: sum(f.processing == name for f in run.files)
            for name in ("accepted", "determining", "checked", "processing_error")
        }
        run.progress = s.RunProgress(total=len(run.files), **counts)
        complete = final and bool(run.files) and counts["processing_error"] == 0
        run.coverage = s.Coverage.complete if complete else s.Coverage.partial
        requirements, rules, issues = evaluate(
            definition,
            run.documents,
            s.ProjectContext.model_validate(package_snapshot["project_context"]),
            run.reference_date,
            final,
        )
        issues += [problem for f in run.files for problem in f.issues]
        if not run.files:
            issues.append(issue("empty_package", "Загрузите документы для проверки."))
        verdict = (
            "issues"
            if any(i.severity == "error" for i in issues)
            else "review_required"
            if issues or not complete
            else "pass"
        )
        run.report = s.MachineReport(
            id=run.report.id if run.report else uuid4(),
            package_id=run.package_id,
            run_id=run.id,
            input_revision=run.input_revision,
            progress_version=run.progress_version,
            program_version_id=package_snapshot["program_version_id"],
            created_at=now(),
            reference_date=run.reference_date,
            timezone=run.timezone,
            coverage=run.coverage,
            provisional=not complete,
            freshness=run.freshness,
            verdict=verdict,
            requirements=requirements,
            rules=rules,
            issues=issues,
        )
        stored = row(uow.session, run.id, "run", lock=True)
        # Preserve pinned private metadata while replacing only the public snapshot.
        stored.data = {**stored.data, **run.model_dump(mode="json")}
        for document in run.documents:
            put(
                uow.session,
                "document",
                document.model_dump(mode="json"),
                found.owner_id,
                run.package_id,
            )
        if current:
            metadata = {str(f.file.id): f.file.model_dump(mode="json") for f in run.files}
            package["files"] = [metadata.get(f["id"], f) for f in package["files"]]
            for file_id, summary in metadata.items():
                file_row = row(uow.session, UUID(file_id), "file")
                file_row.data = {**file_row.data, **summary}
            package.update(
                report=run.report.model_dump(mode="json"),
                verdict=verdict,
                report_freshness="current",
                report_provisional=run.report.provisional,
                updated_at=now().isoformat(),
            )
            found.data = package
        if final:
            job.status, job.lease_until = "done", None
        uow.commit()


async def retry(operation):
    for attempt in range(3):
        try:
            return await operation()
        except (ModelFailure, OcrFailure) as exc:
            if not exc.retryable or attempt == 2:
                raise
            await asyncio.sleep(max(2**attempt, exc.retry_after_seconds or 0))


async def prepare(container, file, stage):
    with container.unit_of_work() as uow:
        data = row(uow.session, file.id, "file").data
        with PostgresBlobStore(uow.session).open(UUID(data["blob_id"])) as stream:
            original = stream.read()
    source = OcrSource(file.id, file.file_version_id, UUID(data["blob_id"]), file.sha256)
    from app.modules.assets.office_preparation import docx_request, xlsx_request

    if file.format == "docx":
        return await asyncio.to_thread(docx_request, source, original)
    if file.format == "xlsx":
        return await asyncio.to_thread(xlsx_request, source, original)
    pages = await asyncio.to_thread(
        prepare_ocr_content,
        source,
        original,
        data["media_type"],
        max_pages=container.settings.ocr_preparation_max_pages,
        max_bytes=container.settings.olmocr_max_input_bytes,
    )
    file.page_count = len(pages)
    sources = []
    port = None
    try:
        for item in pages:
            location = PageLocation(
                kind="page", file_id=file.id, file_version_id=file.file_version_id, page=item.page
            )
            if item.native_text:
                sources.append(
                    PreparedSource(
                        f"source-{item.page}",
                        location,
                        item.native_text,
                        preparation_profile=item.preparation_profile,
                    )
                )
            elif container.settings.model_provider == "local":
                image = item.ocr_page
                if image.media_type == "application/pdf":
                    image = await asyncio.to_thread(rasterize_pdf_page, source, original, item.page)
                image = await asyncio.to_thread(
                    prepare_local_image, image, max_side=container.settings.local_image_max_side
                )
                sources.append(
                    PreparedSource(
                        f"source-{item.page}",
                        location,
                        "",
                        "vision",
                        preparation_profile=image.preparation_profile,
                        image=image.data,
                        media_type=image.media_type,
                    )
                )
            else:
                await stage("ocr")
                if port is None:
                    port = container.create_ocr_client()
                profile = OcrProfile(port.base_url, port.configuration_revision)
                result = await retry(
                    lambda port=port, item=item, profile=profile: OcrContentService(
                        port, container.ocr_result_store()
                    ).prepare(item.ocr_page, profile, uuid4())
                )
                projection = project_ocr_text(result.result.output.text)
                sources.append(
                    PreparedSource(
                        f"source-{item.page}",
                        location,
                        projection.text,
                        "ocr",
                        result.result.id,
                        item.preparation_profile + "/" + projection.profile,
                    )
                )
        return ModelRequest(tuple(sources))
    finally:
        if port:
            await port.aclose()


async def process(container, run_id, lease):
    data, package, version = await asyncio.to_thread(snapshot, container, run_id)
    private_profile = data.pop("_profile", None)
    data.pop("_input", None)
    run = s.VerificationRun.model_validate(data)
    definition = s.ProgramDefinition.model_validate(version["definition"])
    beat = asyncio.create_task(keep_lease(container, run_id, lease))
    provider = None
    try:
        run.status = s.RunStatus.running
        await asyncio.to_thread(publish, container, run, lease, package, definition)
        try:
            if run.model_profile.provider != container.settings.model_provider:
                raise ConfigurationError("Run profile differs from worker profile")
            provider = await container.create_document_model()
            actual = asdict(provider.profile)
            if run.model_profile.model != provider.profile.model:
                raise ConfigurationError("Run model differs from worker model")
            if private_profile is not None and private_profile != actual:
                raise ConfigurationError("Pinned model profile changed")
            with container.unit_of_work() as uow:
                stored = row(uow.session, run_id, "run", lock=True)
                stored.data = {**stored.data, "_profile": actual}
                uow.commit()
            run.model_profile.model = provider.profile.model
            run.model_profile.prompt_version = provider.profile.prompt_version
        except (ModelFailure, ConfigurationError) as exc:
            code = getattr(exc, "code", "model_configuration_error")
            for check in run.files:
                if check.processing == "checked":
                    continue
                check.processing = s.ProcessingStatus.processing_error
                check.error = s.ApiError(
                    code=code,
                    message="Модель недоступна или настройки изменились.",
                    correlation_id=uuid4(),
                )
                check.issues = [issue(code, check.error.message, "warning", "technical")]
            run.status = s.RunStatus.failed
            await asyncio.to_thread(publish, container, run, lease, package, definition, True)
            return
        # Rebuild incomplete files after a crash; preserve already validated completed files.
        for check in run.files:
            if check.processing == "checked":
                continue
            check.processing, check.processing_stage = (
                s.ProcessingStatus.determining,
                s.ProcessingStage.preparing,
            )
            check.error, check.issues = None, []

            async def stage(name, check=check):
                check.processing_stage = s.ProcessingStage(name)
                await asyncio.to_thread(publish, container, run, lease, package, definition)

            try:
                await stage("preparing")
                request = await prepare(container, check.file, stage)
                forced = package.get("type_overrides", {}).get(str(check.file.id))
                if forced:
                    request = ModelRequest(request.sources, DocumentType(forced))
                await stage("extracting")
                result = await retry(
                    lambda request=request: provider.analyze(request, provider.profile, uuid4())
                )
                await stage("validating")
                with container.unit_of_work() as uow:
                    put(
                        uow.session,
                        "model_result",
                        {
                            "id": str(result.invocation.id),
                            "file_id": str(check.file.id),
                            "run_id": str(run.id),
                            "payload": result.payload.model_dump(mode="json"),
                            "invocation": json.loads(
                                json.dumps(asdict(result.invocation), default=str)
                            ),
                        },
                        UUID(package["owner_id"])
                        if "owner_id" in package
                        else row(uow.session, run.package_id, "package").owner_id,
                        run.package_id,
                    )
                    uow.commit()
                for fragment in result.fragments:
                    locations = [
                        source.location
                        for source in request.sources
                        if source.id in fragment.source_ids
                    ]
                    document = s.DocumentUnit(
                        id=uuid4(),
                        version_id=uuid4(),
                        predicted_type=fragment.predicted_type,
                        effective_type=fragment.effective_type,
                        type_overridden=bool(forced),
                        fragments=[
                            s.SourceFragmentRef(id=uuid4(), location=location)
                            for location in locations
                        ],
                        fields=list(fragment.fields),
                    )
                    if document.effective_type == "unknown":
                        document.issues.append(
                            issue("unknown_document_type", "Вид документа не определён.")
                        )
                        check.issues.extend(document.issues)
                    run.documents.append(document)
                    check.document_unit_ids.append(document.id)
                check.invocations.append(
                    s.ProviderMetadata(
                        provider=result.invocation.profile.provider,
                        model=result.invocation.profile.model,
                        prompt_version=result.invocation.profile.prompt_version,
                        schema_hash=result.invocation.profile.schema_hash,
                        invocation_id=result.invocation.id,
                    )
                )
                check.processing, check.processing_stage, check.verdict = (
                    s.ProcessingStatus.checked,
                    None,
                    s.Verdict.review_required,
                )
            except (OcrFailure, ModelFailure, ValueError) as exc:
                code = getattr(exc, "code", "preparation_failed")
                check.processing, check.verdict = (
                    s.ProcessingStatus.processing_error,
                    s.Verdict.review_required,
                )
                check.error = s.ApiError(
                    code=code,
                    message="Файл не обработан. Проверьте источник и повторите проверку.",
                    details={
                        "stage": getattr(exc, "stage", str(check.processing_stage)),
                        "retryable": getattr(exc, "retryable", False),
                    },
                    correlation_id=uuid4(),
                )
                check.issues = [issue(code, check.error.message, "warning", "technical")]
                check.issues[0].next_action = s.IssueAction(
                    action="retry_verification", target=s.ResourceRef(kind="file", id=check.file.id)
                )
            await asyncio.to_thread(publish, container, run, lease, package, definition)
        run.status = s.RunStatus.completed
        await asyncio.to_thread(publish, container, run, lease, package, definition, True)
    finally:
        beat.cancel()
        with suppress(asyncio.CancelledError, LeaseLost):
            await beat
        if provider:
            await provider.aclose()


async def main():
    container = AppContainer(Settings())
    try:
        while True:
            try:
                claimed = await asyncio.to_thread(claim, container)
                if claimed:
                    await process(container, *claimed)
                else:
                    await asyncio.sleep(1)
            except LeaseLost:
                logger.warning("worker_lease_lost")
            except Exception as exc:
                # Lease expiration recovers interrupted jobs. Never log document/driver contents.
                logger.error("worker_failure type=%s", type(exc).__name__)
                await asyncio.sleep(5)
    finally:
        container.close()


if __name__ == "__main__":
    asyncio.run(main())
