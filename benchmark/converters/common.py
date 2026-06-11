from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def pick(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return default


def safe_stem(value: Any) -> str:
    text = str(value or "document").strip()
    safe = "".join(
        char if char.isalnum() or char in {"-", "_"} else "_" for char in text
    )
    return "_".join(part for part in safe.split("_") if part) or "document"


def materialize_text_document(
    output_path: str | Path,
    document_id: str,
    text: str,
) -> Path:
    output_path = Path(output_path).resolve()
    document_dir = output_path.parent / "documents"
    document_dir.mkdir(parents=True, exist_ok=True)
    document_path = document_dir / f"{safe_stem(document_id)}.txt"
    document_path.write_text(text.strip() + "\n", encoding="utf-8")
    return document_path


def write_v2_manifest(
    output_path: str | Path,
    *,
    dataset_name: str,
    documents: list[dict[str, Any]],
    examples: list[dict[str, Any]],
    routes: list[dict[str, Any]] | None = None,
) -> Path:
    output_path = Path(output_path).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": 2,
        "dataset_name": dataset_name,
        "documents": documents,
        "examples": examples,
    }
    if routes is not None:
        payload["routes"] = routes
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
