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
    for doc in ensure_list(record.get("docs")):
        if isinstance(doc, dict):
            parts.append(_doc_text(doc))
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
    if _is_qampari_record(record):
        return [_qampari_example(record, document_id, record_index)]
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


def _qampari_example(
    record: dict[str, Any],
    document_id: str,
    record_index: int,
) -> dict[str, Any]:
    evidence_sources = [
        text
        for text in (_doc_text(doc) for doc in ensure_list(record.get("docs")))
        if text
    ]
    answers = _qampari_answer_groups(record)
    return {
        "example_id": str(record.get("id") or f"{document_id}_qampari"),
        "document_ids": [document_id],
        "scope": "document",
        "modality": "text",
        "answer_type": "list_qa",
        "question": str(record.get("question") or "").strip(),
        "answers": _flat_qampari_answer(record),
        "evidence_sources": evidence_sources[:5],
        "gold_evidence": _gold_evidence(document_id, evidence_sources[0])
        if evidence_sources
        else [],
        "metadata": {
            "dataset_family": "citation_quality",
            "record_index": record_index,
            "alce_task": "qampari",
            "alce_answers": answers,
        },
    }


def _is_qampari_record(record: dict[str, Any]) -> bool:
    return (
        bool(str(record.get("question") or "").strip())
        and bool(_qampari_answer_groups(record))
        and not ensure_list(record.get("qa_pairs"))
    )


def _qampari_answer_groups(record: dict[str, Any]) -> list[list[str]]:
    groups: list[list[str]] = []
    for group in ensure_list(record.get("answers")):
        aliases = [
            str(item).strip() for item in ensure_list(group) if str(item).strip()
        ]
        if aliases:
            groups.append(aliases)
    return groups


def _flat_qampari_answer(record: dict[str, Any]) -> list[str]:
    answer = str(record.get("answer") or "").strip()
    if answer:
        return [answer]
    answers = [group[0] for group in _qampari_answer_groups(record) if group]
    return [", ".join(answers)] if answers else []


def _doc_text(doc: Any) -> str:
    if not isinstance(doc, dict):
        return ""
    return str(
        doc.get("text") or doc.get("summary") or doc.get("extraction") or ""
    ).strip()


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
