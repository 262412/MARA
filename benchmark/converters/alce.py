from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ensure_list, load_json, materialize_text_document, write_v2_manifest


def normalize_alce_manifest(
    source_path: str | Path,
    output_path: str | Path,
) -> Path:
    records = ensure_list(load_json(source_path))
    documents: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []

    for record_index, record in enumerate(records):
        if not isinstance(record, dict):
            continue
        document_id = f"alce_{record_index}"
        document_path = materialize_text_document(
            output_path,
            document_id,
            _record_text(record),
        )
        documents.append(
            {
                "document_id": document_id,
                "path": str(document_path),
                "format_type": "txt",
                "modality": "text",
                "metadata": {"dataset_family": "citation_quality"},
            }
        )
        examples.extend(_examples(record, document_id, record_index))

    return write_v2_manifest(
        output_path,
        dataset_name="alce",
        documents=documents,
        examples=examples,
    )


def _record_text(record: dict[str, Any]) -> str:
    parts: list[str] = []
    for qa in ensure_list(record.get("qa_pairs")):
        if isinstance(qa, dict):
            parts.append(str(qa.get("context") or ""))
    for annotation in ensure_list(record.get("annotations")):
        if isinstance(annotation, dict):
            parts.append(str(annotation.get("long_answer") or ""))
    return "\n\n".join(part for part in parts if part.strip())


def _examples(
    record: dict[str, Any],
    document_id: str,
    record_index: int,
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for qa_index, qa in enumerate(ensure_list(record.get("qa_pairs"))):
        if not isinstance(qa, dict):
            continue
        context = str(qa.get("context") or "").strip()
        examples.append(
            {
                "example_id": f"{document_id}_{qa_index}",
                "document_ids": [document_id],
                "scope": "document",
                "modality": "text",
                "answer_type": "citation_qa",
                "question": str(qa.get("question") or "").strip(),
                "answers": [
                    str(item).strip()
                    for item in ensure_list(qa.get("short_answers"))
                    if str(item).strip()
                ],
                "evidence_sources": [context] if context else [],
                "gold_evidence": _gold_evidence(document_id, context),
                "metadata": {
                    "dataset_family": "citation_quality",
                    "record_index": record_index,
                },
            }
        )
    return examples


def _gold_evidence(document_id: str, context: str) -> list[dict[str, Any]]:
    if not context:
        return []
    return [
        {
            "document_id": document_id,
            "span": context,
            "citation": f"{document_id}#context:1",
        }
    ]
