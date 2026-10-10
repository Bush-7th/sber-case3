"""Explicit Ollama diagnostics, CPU only; documents and facts never enter stdout."""

import argparse
import asyncio
import json
from dataclasses import asdict
from pathlib import Path
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.modules.assets.ocr import OcrSourceConflict, PreparationFailure
from app.modules.recognition.facts import DocumentType
from app.modules.recognition.model import ModelFailure, ModelRequest
from app.runtime.container import AppContainer, build_document_model
from app.runtime.model_inputs import MEDIA, load_input, positive_page, register_original
from app.runtime.settings import ConfigurationError, Settings


async def run(args):
    settings = Settings()
    if settings.model_provider != "local":
        raise ConfigurationError("Local diagnostics require MODEL_PROVIDER=local")
    async with await build_document_model(settings) as provider:
        if args.command == "inspect":
            return {"event": "local_model_inspected", "profile": asdict(provider.profile)}
        container = AppContainer(settings)
        try:
            version_id = args.file_version_id
            if args.command == "file":
                media = MEDIA.get(args.path.suffix.lower())
                if not media or args.path.stat().st_size > settings.olmocr_max_input_bytes:
                    raise ValueError("Unsupported original or input limit")
                version_id = version_id or uuid4()
                await asyncio.to_thread(
                    register_original, container, args.path.read_bytes(), media, version_id
                )
                print(
                    json.dumps(
                        {"event": "local_original_registered", "file_version_id": str(version_id)}
                    )
                )
            request = await asyncio.to_thread(
                load_input,
                container,
                version_id,
                ocr_result_id=None,
                page=args.page,
                local_images=True,
                rasterize=args.rasterize,
            )
            if args.forced_type:
                request = ModelRequest(request.sources, DocumentType(args.forced_type))
            result = await provider.analyze(request, provider.profile, uuid4())
            running = await provider.running_model(uuid4())
            return {
                "event": "local_sample_complete",
                "file_version_id": str(version_id),
                "invocation_id": str(result.invocation.id),
                "duration_ms": result.invocation.duration_ms,
                "profile": asdict(result.invocation.profile),
                "running_model": running,
                "calls": [asdict(call) for call in result.invocation.calls],
                "preparation_profiles": result.invocation.preparation_profiles,
                "fragments": [
                    {
                        "predicted_type": f.predicted_type,
                        "effective_type": f.effective_type,
                        "known_fields": [v.field_id for v in f.fields if v.known_state == "known"],
                        "missing_fields": [
                            v.field_id for v in f.fields if v.known_state == "missing"
                        ],
                        "unreadable_fields": [
                            v.field_id for v in f.fields if v.known_state == "unreadable"
                        ],
                    }
                    for f in result.fragments
                ],
            }
        finally:
            container.close()
            if args.unload:
                try:
                    await provider.unload(uuid4())
                except ModelFailure as exc:
                    # Cleanup must not hide the original extraction error or an accepted result.
                    print(json.dumps({"event": "local_unload_failed", "code": exc.code}))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    sample = commands.add_parser("sample")
    sample.add_argument("file_version_id", type=UUID)
    file = commands.add_parser("file")
    file.add_argument("path", type=Path)
    file.add_argument("--file-version-id", type=UUID)
    for command in (sample, file):
        command.add_argument("--page", type=positive_page, default=1)
        command.add_argument("--rasterize", action="store_true")
        command.add_argument("--forced-type", choices=[t.value for t in DocumentType])
        command.add_argument("--unload", action="store_true")
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
    except ModelFailure as exc:
        print(
            json.dumps(
                {
                    "event": "local_failed",
                    "code": exc.code,
                    "stage": exc.stage,
                    "retryable": exc.retryable,
                    "status": exc.status,
                    "reason": exc.reason,
                    "correlation_id": str(exc.correlation_id),
                }
            )
        )
        raise SystemExit(1) from None
    except (
        ConfigurationError,
        PreparationFailure,
        ValidationError,
        SQLAlchemyError,
        OSError,
        ValueError,
        OcrSourceConflict,
    ):
        print(json.dumps({"event": "local_diagnostic_failed"}))
        raise SystemExit(1) from None
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
