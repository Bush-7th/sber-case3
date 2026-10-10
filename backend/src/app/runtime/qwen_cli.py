"""Server-only Qwen diagnostics. Reads prepared original/OCR from M03, never prints facts."""

import argparse
import asyncio
import json
from dataclasses import asdict
from hashlib import sha256
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.modules.assets.ocr_persistence import FileVersionRow, OcrResultRow
from app.modules.assets.ocr_preparation import prepare_ocr_content
from app.modules.assets.persistence import PostgresBlobStore
from app.modules.assets.text_projection import project_ocr_text
from app.modules.recognition.facts import DocumentType, PageLocation
from app.modules.recognition.model import ModelFailure, ModelRequest, PreparedSource
from app.runtime.container import AppContainer, build_qwen_provider
from app.runtime.settings import ConfigurationError, Settings


def positive_page(value: str) -> int:
    page = int(value)
    if page < 1:
        raise argparse.ArgumentTypeError("Page numbering starts at 1")
    return page


def load_input(
    container: AppContainer, version_id: UUID, *, ocr_result_id: UUID | None, page: int | None
) -> ModelRequest:
    # Only M03 owns these reads; this diagnostic is explicit wiring, not a domain repository.
    with container.unit_of_work() as uow:
        version = uow.session.get(FileVersionRow, version_id)
        if version is None:
            raise ValueError("Unknown source version")
        file_id, original_id = version.file_id, version.original_blob_id
        if ocr_result_id:
            row = uow.session.scalar(
                select(OcrResultRow).where(
                    OcrResultRow.id == ocr_result_id, OcrResultRow.file_version_id == version_id
                )
            )
            if row is None:
                raise ValueError("Unknown saved OCR result")
            projection = project_ocr_text(row.text)
            sources = (
                PreparedSource(
                    "source-1",
                    PageLocation(
                        kind="page", file_id=file_id, file_version_id=version_id, page=row.page
                    ),
                    projection.text,
                    "ocr",
                    row.id,
                    row.preparation_profile + "/" + projection.profile,
                ),
            )
            return ModelRequest(sources)
        store = PostgresBlobStore(uow.session)
        blob = store.head(original_id)
        with store.open(original_id) as stream:
            data = stream.read()
    if sha256(data).hexdigest() != blob.sha256:
        raise ValueError("Original integrity mismatch")
    from app.modules.assets.ocr import OcrSource

    source = OcrSource(file_id, version_id, original_id, blob.sha256)
    prepared = prepare_ocr_content(
        source,
        data,
        blob.media_type,
        max_pages=container.settings.ocr_preparation_max_pages,
        max_bytes=container.settings.olmocr_max_input_bytes,
    )
    if page is not None:
        if page < 1 or page > len(prepared):
            raise ValueError("Unknown page")
        prepared = [prepared[page - 1]]
    sources = []
    for item in prepared:
        if not item.native_text:
            # The diagnostic never triggers another OCR attempt or fabricates empty-page text.
            raise ValueError("Run OCR preparation first and select its saved result")
        sources.append(
            PreparedSource(
                f"source-{item.page}",
                PageLocation(
                    kind="page", file_id=file_id, file_version_id=version_id, page=item.page
                ),
                item.native_text,
                preparation_profile=item.preparation_profile + "/native-text-v1",
            )
        )
    return ModelRequest(tuple(sources))


async def run(args):
    settings = Settings()
    async with build_qwen_provider(settings) as provider:
        if args.command == "models":
            models = await provider.available_models(uuid4())
            return {
                "event": "qwen_models",
                "configured_model_available": settings.qwen_model in models,
                "models": models,
            }
        container = AppContainer(settings)
        try:
            request = await asyncio.to_thread(
                load_input,
                container,
                args.file_version_id,
                ocr_result_id=args.ocr_result_id,
                page=args.page,
            )
            if args.forced_type:
                request = ModelRequest(request.sources, DocumentType(args.forced_type))
            output = await provider.analyze(request, provider.profile, uuid4())
            return {
                "event": "qwen_sample_complete",
                "file_version_id": str(args.file_version_id),
                "invocation_id": str(output.invocation.id),
                "duration_ms": output.invocation.duration_ms,
                "profile": asdict(output.invocation.profile),
                "preparation_profiles": output.invocation.preparation_profiles,
                "fragments": [
                    {
                        "predicted_type": f.predicted_type,
                        "effective_type": f.effective_type,
                        "source_count": len(f.source_ids),
                        "known_fields": [v.field_id for v in f.fields if v.known_state == "known"],
                        "missing_fields": [
                            v.field_id for v in f.fields if v.known_state == "missing"
                        ],
                        "unreadable_fields": [
                            v.field_id for v in f.fields if v.known_state == "unreadable"
                        ],
                    }
                    for f in output.fragments
                ],
            }
        finally:
            container.close()


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("models")
    sample = commands.add_parser("sample")
    sample.add_argument("file_version_id", type=UUID)
    choice = sample.add_mutually_exclusive_group()
    choice.add_argument("--ocr-result-id", type=UUID)
    choice.add_argument("--page", type=positive_page)
    sample.add_argument("--forced-type", choices=[t.value for t in DocumentType])
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except ModelFailure as exc:
        print(
            json.dumps(
                {
                    "event": "qwen_failed",
                    "code": exc.code,
                    "stage": exc.stage,
                    "retryable": exc.retryable,
                    "status": exc.status,
                    "retry_after_seconds": exc.retry_after_seconds,
                    "correlation_id": str(exc.correlation_id),
                    "reason": exc.reason,
                }
            )
        )
        raise SystemExit(1) from None
    except (ConfigurationError, ValidationError, SQLAlchemyError, OSError, ValueError):
        print(json.dumps({"event": "qwen_diagnostic_failed"}))
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
