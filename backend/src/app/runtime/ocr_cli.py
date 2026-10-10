"""Explicit server-only diagnostics; documents/results never enter stdout or Git."""

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.modules.assets.ocr import OcrFailure, OcrSource, OcrSourceConflict, PreparationFailure
from app.modules.assets.ocr_persistence import FileVersionRow, SqlOcrRepository
from app.modules.assets.ocr_preparation import prepare_ocr_content, rasterize_pdf_page
from app.modules.assets.ocr_service import OcrContentService
from app.modules.assets.persistence import PostgresBlobStore
from app.runtime.container import AppContainer, build_ocr_client
from app.runtime.settings import ConfigurationError, Settings

MEDIA = {
    ".pdf": "application/pdf",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def positive_page(value: str) -> int:
    page = int(value)
    if page < 1:
        raise argparse.ArgumentTypeError("Page numbering starts at 1")
    return page


def register_original(
    container: AppContainer, data: bytes, media: str, version_id: UUID
) -> OcrSource:
    from hashlib import sha256

    digest = sha256(data).hexdigest()
    with container.unit_of_work() as uow:
        existing = uow.session.get(FileVersionRow, version_id)
        if existing:
            source = OcrSource(existing.file_id, version_id, existing.original_blob_id, digest)
            SqlOcrRepository(uow.session).validate_source(source)
            return source
        blob = PostgresBlobStore(uow.session).put_immutable(uuid4(), data, media)
        source = OcrSource(uuid4(), version_id, blob.id, blob.sha256)
        SqlOcrRepository(uow.session).register_source(source)
        uow.commit()
        return source


async def sample(settings: Settings, args) -> dict:
    media = MEDIA.get(args.path.suffix.lower())
    if not media:
        raise PreparationFailure("preparation_unsupported_input", uuid4())
    if args.path.stat().st_size > settings.olmocr_max_input_bytes:
        raise PreparationFailure("preparation_input_too_large", uuid4())
    data = args.path.read_bytes()
    container = AppContainer(settings)
    try:
        version_id = args.file_version_id or uuid4()
        source = await asyncio.to_thread(register_original, container, data, media, version_id)
        if args.rasterize:
            if media != "application/pdf":
                raise PreparationFailure("preparation_unsupported_input", uuid4())
            pages = [await asyncio.to_thread(rasterize_pdf_page, source, data, args.page)]
            native_count = 0
        else:
            prepared = await asyncio.to_thread(
                prepare_ocr_content,
                source,
                data,
                media,
                max_pages=settings.ocr_preparation_max_pages,
                max_bytes=settings.olmocr_max_input_bytes,
            )
            if args.page > len(prepared):
                raise PreparationFailure("preparation_unsupported_input", uuid4())
            content = prepared[args.page - 1]
            pages = [content.ocr_page] if content.ocr_page else []
            native_count = len(content.native_text or "")
        records = []
        if pages:
            async with build_ocr_client(settings) as client:
                profile = await client.healthcheck(uuid4())
                service = OcrContentService(client, container.ocr_result_store())
                for page in pages:
                    prepared = await service.prepare(page, profile, uuid4())
                    result = prepared.result
                    records.append(
                        {
                            "ocr_result_id": str(result.id),
                            "page": result.page,
                            "text_characters": len(result.output.text),
                            "reused": prepared.reused,
                            "preparation_profile": result.preparation_profile,
                            "ocr_profile": result.profile.fingerprint,
                            "duration_ms": result.output.duration_ms,
                        }
                    )
        return {
            "event": "ocr_sample_complete",
            "file_id": str(source.file_id),
            "file_version_id": str(version_id),
            "native_text_characters": native_count,
            "ocr_results": records,
        }
    finally:
        container.close()


async def run(args):
    settings = Settings()
    if args.command == "health":
        async with build_ocr_client(settings) as client:
            profile = await client.healthcheck(uuid4())
            return {"event": "ocr_health", "profile": asdict(profile)}
    return await sample(settings, args)


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("health")
    scan = commands.add_parser("sample")
    scan.add_argument("path", type=Path)
    scan.add_argument("--file-version-id", type=UUID)
    scan.add_argument("--page", type=positive_page, default=1)
    scan.add_argument(
        "--rasterize",
        action="store_true",
        help="Explicitly test OCR on a PNG rendering of this real PDF page",
    )
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except OcrFailure as exc:
        print(
            json.dumps(
                {
                    "event": "preparation_failed" if exc.stage == "preparing" else "ocr_failed",
                    "stage": exc.stage,
                    "code": exc.code,
                    "retryable": exc.retryable,
                    "status": exc.status,
                    "retry_after_seconds": exc.retry_after_seconds,
                    "correlation_id": str(exc.correlation_id),
                }
            )
        )
        raise SystemExit(1) from None
    except (
        ConfigurationError,
        ValidationError,
        SQLAlchemyError,
        OcrSourceConflict,
        OSError,
        ValueError,
    ):
        print(json.dumps({"event": "ocr_diagnostic_failed"}))
        raise SystemExit(1) from None
    print(json.dumps(result))


if __name__ == "__main__":
    main()
