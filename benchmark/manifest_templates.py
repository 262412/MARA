from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import load_manifest


def apply_route_template(
    manifest_path: str | Path,
    template_path: str | Path,
    output_path: str | Path,
    *,
    dataset_name: str | None = None,
) -> Path:
    """Write a runnable v2 manifest by combining dataset rows with template routes."""
    source = load_manifest(manifest_path)
    template = load_manifest(template_path)
    if not template.routes:
        raise ValueError("route template must define at least one route")

    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": 2,
        "dataset_name": dataset_name or source.dataset_name,
        "documents": [document.to_dict() for document in source.documents.values()],
        "examples": [example.to_dict() for example in source.examples],
        "routes": [dict(route) for route in template.routes],
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
