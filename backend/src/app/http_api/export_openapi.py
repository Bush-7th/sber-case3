"""Regenerate the checked-in schema, or fail if it differs from the source."""

import argparse
import json
from pathlib import Path

from app.main import create_app


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    options = parser.parse_args()
    destination = Path(__file__).resolve().parents[3] / "openapi.json"
    generated = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2) + "\n"
    if options.check:
        if not destination.exists() or destination.read_text() != generated:
            raise SystemExit("OpenAPI is stale: run python -m app.http_api.export_openapi")
        print("OpenAPI matches Pydantic/FastAPI source")
    else:
        destination.write_text(generated)
        print(f"Exported {destination}")


if __name__ == "__main__":
    main()
