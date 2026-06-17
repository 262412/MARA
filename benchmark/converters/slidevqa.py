from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import (
    ensure_list,
    materialize_binary_document,
    pick,
    safe_stem,
    write_v2_manifest,
)


def normalize_slidevqa_parquet_manifest(
    source_path: str | Path,
    output_path: str | Path,
) -> Path:
    source_path = Path(source_path).resolve()
    output_path = Path(output_path).resolve()
    rows = _load_rows(source_path)
    documents: dict[str, dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []

    for index, row in enumerate(rows):
        deck_id = safe_stem(pick(row, "deck_name", "deck_id", default=f"deck_{index}"))
        page_document_ids = _page_documents(row, deck_id, output_path, documents)
        if not page_document_ids:
            continue

        question = str(pick(row, "question", default="")).strip()
        if not question:
            continue

        examples.append(
            _example(
                row,
                index=index,
                deck_id=deck_id,
                question=question,
                page_document_ids=page_document_ids,
            )
        )

    return write_v2_manifest(
        output_path,
        dataset_name="slidevqa",
        documents=list(documents.values()),
        examples=examples,
    )


def _load_rows(source_path: Path) -> list[dict[str, Any]]:
    if source_path.is_dir():
        rows: list[dict[str, Any]] = []
        for candidate in sorted(source_path.rglob("*.parquet")):
            rows.extend(_load_rows(candidate))
        return rows
    if source_path.suffix.lower() != ".parquet":
        raise ValueError(f"Unsupported SlideVQA source file: {source_path}")
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("SlideVQA parquet conversion requires pandas.") from exc
    frame = pd.read_parquet(source_path)
    return [dict(row) for row in frame.to_dict(orient="records")]


def _page_documents(
    row: dict[str, Any],
    deck_id: str,
    output_path: Path,
    documents: dict[str, dict[str, Any]],
) -> list[str]:
    page_document_ids: list[str] = []
    for page_number, image in _page_images(row):
        document_id = f"{deck_id}_page_{page_number}"
        page_document_ids.append(document_id)
        if document_id in documents:
            continue
        content = image["bytes"]
        document_path = materialize_binary_document(output_path, document_id, content)
        documents[document_id] = {
            "document_id": document_id,
            "path": str(document_path),
            "format_type": document_path.suffix.lower().lstrip(".") or "png",
            "modality": "page_image",
            "metadata": {
                "dataset_family": "slide_qa",
                "deck_name": row.get("deck_name"),
                "deck_url": row.get("deck_url"),
                "page": page_number,
            },
        }
    return page_document_ids


def _page_images(row: dict[str, Any]) -> list[tuple[int, dict[str, bytes]]]:
    pages: list[tuple[int, dict[str, bytes]]] = []
    for key, value in row.items():
        if not key.startswith("page_") or not isinstance(value, dict):
            continue
        page_number = _page_number(key)
        content = value.get("bytes")
        if page_number is not None and isinstance(content, bytes):
            pages.append((page_number, {"bytes": content}))
    return sorted(pages, key=lambda item: item[0])


def _page_number(key: str) -> int | None:
    try:
        return int(key.rsplit("_", 1)[1])
    except (IndexError, ValueError):
        return None


def _example(
    row: dict[str, Any],
    *,
    index: int,
    deck_id: str,
    question: str,
    page_document_ids: list[str],
) -> dict[str, Any]:
    evidence_pages = [
        page
        for page in (
            _page_value(item) for item in _list_value(row.get("evidence_pages"))
        )
        if page is not None
    ]
    return {
        "example_id": str(pick(row, "qa_id", "id", default=f"{deck_id}_{index}")),
        "document_ids": page_document_ids,
        "scope": "multi_document",
        "modality": "page_image",
        "answer_type": "extractive",
        "question": question,
        "answers": [
            str(item).strip()
            for item in ensure_list(pick(row, "answers", "answer", default=[]))
            if str(item).strip()
        ],
        "evidence_pages": evidence_pages,
        "gold_evidence": _gold_evidence(deck_id, evidence_pages, page_document_ids),
        "metadata": {
            "dataset_family": "slide_qa",
            "deck_name": row.get("deck_name"),
            "deck_url": row.get("deck_url"),
        },
    }


def _list_value(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if hasattr(value, "tolist"):
        converted = value.tolist()
        return converted if isinstance(converted, list) else [converted]
    return [value]


def _page_value(value: Any) -> int | str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return text


def _gold_evidence(
    deck_id: str,
    evidence_pages: list[int | str],
    page_document_ids: list[str],
) -> list[dict[str, Any]]:
    page_documents = {
        _page_value(document_id.rsplit("_page_", 1)[1]): document_id
        for document_id in page_document_ids
        if "_page_" in document_id
    }
    return [
        {
            "document_id": page_documents.get(page, f"{deck_id}_page_{page}"),
            "page": page,
            "modality": "page_image",
            "citation": f"{page_documents.get(page, f'{deck_id}_page_{page}')}#page:{page}",
        }
        for page in evidence_pages
    ]
