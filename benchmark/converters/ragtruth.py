from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import load_jsonl, materialize_text_document, write_v2_manifest


def normalize_ragtruth_manifest(
    source_info_path: str | Path,
    response_path: str | Path,
    output_path: str | Path,
) -> Path:
    sources = {str(item["source_id"]): item for item in load_jsonl(source_info_path)}
    documents = [
        _document_record(output_path, source_id, source)
        for source_id, source in sources.items()
    ]
    examples = [
        _example(response, sources[str(response["source_id"])], index)
        for index, response in enumerate(load_jsonl(response_path))
        if str(response.get("source_id")) in sources
    ]
    return write_v2_manifest(
        output_path,
        dataset_name="ragtruth",
        documents=documents,
        examples=examples,
    )


def _document_record(
    output_path: str | Path,
    source_id: str,
    source: dict[str, Any],
) -> dict[str, Any]:
    source_text = _source_text(source)
    document_path = materialize_text_document(
        output_path,
        source_id,
        source_text,
    )
    return {
        "document_id": source_id,
        "path": str(document_path),
        "format_type": "txt",
        "modality": "text",
        "metadata": {
            "dataset_family": "hallucination_verification",
            "task_type": source.get("task_type"),
            "source_label": str(source.get("source") or "").strip(),
        },
    }


def _example(
    response: dict[str, Any],
    source: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    source_id = str(response["source_id"])
    labels = list(response.get("labels") or [])
    source_text = _source_text(source)
    return {
        "example_id": str(response.get("id") or f"{source_id}_{index}"),
        "document_ids": [source_id],
        "scope": "document",
        "modality": "text",
        "answer_type": "verification",
        "question": str(source.get("prompt") or source.get("task_type") or "").strip(),
        "answers": [str(response.get("response") or "").strip()],
        "gold_evidence": [
            {
                "document_id": source_id,
                "span": source_text,
                "citation": f"{source_id}#source",
            }
        ],
        "expected_guardrails": {
            "allow_abstention": True,
            "unsupported_claims_expected": bool(labels),
        },
        "metadata": {
            "dataset_family": "hallucination_verification",
            "model": response.get("model"),
            "quality": response.get("quality"),
            "label_count": len(labels),
            "labels": labels,
            "task_type": source.get("task_type"),
            "source_info": source_text,
            "response": str(response.get("response") or "").strip(),
            "source_label": str(source.get("source") or "").strip(),
        },
    }


def _source_text(source: dict[str, Any]) -> str:
    return str(source.get("source_info") or source.get("source") or "").strip()
