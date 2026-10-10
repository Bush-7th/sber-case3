"""Server-only Qwen diagnostics. Reads prepared original/OCR from M03, never prints facts."""

import argparse
import asyncio
import json
from dataclasses import asdict
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.modules.recognition.facts import DocumentType
from app.modules.recognition.model import ModelFailure, ModelRequest
from app.runtime.container import AppContainer, build_qwen_provider
from app.runtime.model_inputs import load_input as load_input
from app.runtime.model_inputs import positive_page as positive_page
from app.runtime.settings import ConfigurationError, Settings


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
