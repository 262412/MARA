from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .common import load_json, load_jsonl, pick, write_v2_manifest


def normalize_vidore_manifest(
    source_path: str | Path,
    output_path: str | Path,
    documents_root: str | Path | None = None,
) -> Path:
    source_path = Path(source_path).resolve()
    documents_root = (
        Path(documents_root).resolve() if documents_root else source_path.parent
    )
    rows = _load_rows(source_path)
    documents: dict[str, dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        document_id = _document_id(row, index)
        documents.setdefault(
            document_id, _document_record(row, document_id, documents_root)
        )
        examples.append(_example(row, document_id, index))

    return write_v2_manifest(
        output_path,
        dataset_name="vidore",
        documents=list(documents.values()),
        examples=examples,
    )


def _load_rows(source_path: Path) -> list[dict[str, Any]]:
    if source_path.is_dir():
        rows: list[dict[str, Any]] = []
        for candidate in sorted(source_path.rglob("*")):
            if candidate.suffix.lower() in {".json", ".jsonl", ".parquet"}:
                rows.extend(_load_rows(candidate))
        return rows
    if source_path.suffix.lower() == ".jsonl":
        return load_jsonl(source_path)
    if source_path.suffix.lower() == ".json":
        payload = load_json(source_path)
        return payload if isinstance(payload, list) else list(payload.get("data", []))
    if source_path.suffix.lower() == ".parquet":
        return _load_parquet_rows(source_path)
    raise ValueError(f"Unsupported ViDoRe source file: {source_path}")


def _load_parquet_rows(source_path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("ViDoRe parquet conversion requires pandas.") from exc
    frame = pd.read_parquet(source_path)
    return [dict(row) for row in frame.to_dict(orient="records")]


def _document_id(row: dict[str, Any], index: int) -> str:
    base = str(pick(row, "doc_id", "document_id", "image_id", default=f"doc_{index}"))
    page = pick(row, "page", "page_number", "page_idx")
    if page is None:
        return base
    return f"{base}_page_{page}"


def _document_record(
    row: dict[str, Any],
    document_id: str,
    documents_root: Path,
) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "path": str(_image_path(row, document_id, documents_root)),
        "format_type": "png",
        "modality": "page_image",
        "metadata": {"dataset_family": "visual_retrieval"},
    }


def _image_path(row: dict[str, Any], document_id: str, documents_root: Path) -> Path:
    value = pick(
        row, "image_filename", "image_path", "path", default=f"{document_id}.png"
    )
    path = Path(str(value))
    if path.is_absolute():
        return path
    return documents_root / path


def _example(row: dict[str, Any], document_id: str, index: int) -> dict[str, Any]:
    page = pick(row, "page", "page_number", "page_idx")
    return {
        "example_id": str(pick(row, "query_id", "id", default=f"vidore_{index}")),
        "document_ids": [document_id],
        "scope": "page",
        "modality": "page_image",
        "answer_type": "retrieval",
        "question": str(pick(row, "query", "question", default="")).strip(),
        "answers": [
            str(item).strip() for item in _answer_values(row) if str(item).strip()
        ],
        "evidence_pages": [page] if page is not None else [],
        "gold_evidence": [
            {
                "document_id": document_id,
                "page": page,
                "modality": "page_image",
                "citation": f"{document_id}#page:{page}",
            }
        ],
        "metadata": {"dataset_family": "visual_retrieval"},
    }


def _answer_values(row: dict[str, Any]) -> list[Any]:
    value = pick(row, "answers", "answer", default=[])
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.startswith("["):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        return decoded if isinstance(decoded, list) else [decoded]
    return [value]
