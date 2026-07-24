from __future__ import annotations

from collections import Counter
from typing import Any

from ktem.docqa.multimodal_index import (
    element_records_from_documents,
    page_image_records_from_documents,
)
from ktem.docqa.visual_retriever import rank_page_image_records

from kotaemon.base import RetrievedDocument

_LARGE_IMAGE_METADATA_KEYS = {
    "image_origin",
    "image_ref",
    "page_image_path",
    "page_visual_embedding",
    "rendered_page_image",
    "visual_embedding",
}


def build_mara_evidence_metadata(
    docs: list[RetrievedDocument], understanding: dict[str, Any]
) -> dict[str, Any]:
    modality_counts: Counter[str] = Counter()
    page_coverage: list[str] = []
    source_ids: list[str] = []
    evidence_ids: list[str] = []
    evidence = []

    for doc in docs:
        item = _evidence_item(doc)
        evidence.append(item)
        _append_unique(page_coverage, item["page_label"])
        _append_unique(source_ids, item["file_id"])
        _append_unique(evidence_ids, item["evidence_id"])
        modality_counts[item["element_type"]] += 1

    metadata = {
        "requested_modalities": list(understanding.get("modalities", [])),
        "modality_counts": dict(modality_counts),
        "page_coverage": page_coverage,
        "source_ids": source_ids,
        "evidence_ids": evidence_ids,
        "evidence": evidence,
    }
    _add_multimodal_index_records(
        metadata,
        docs,
        question=str(understanding.get("question") or ""),
    )
    return metadata


def _evidence_item(doc: RetrievedDocument) -> dict[str, Any]:
    metadata = _merged_doc_metadata(doc)
    file_id = str(metadata.get("file_id") or "").strip()
    file_name = str(metadata.get("file_name") or "").strip()
    evidence_id = str(getattr(doc, "doc_id", "") or "").strip()
    page_label = str(metadata.get("page_label") or "").strip()
    element_type = str(
        metadata.get("element_type")
        or metadata.get("type")
        or metadata.get("modality")
        or "text"
    )
    element_id = str(metadata.get("element_id") or "").strip()
    if not element_id and element_type == "text" and page_label:
        element_id = evidence_id
    return {
        "evidence_id": evidence_id,
        "file_id": file_id,
        "source_id": file_id,
        "file_name": file_name,
        "source_name": file_name,
        "page_label": page_label,
        "element_type": element_type,
        "element_id": element_id,
        "bbox": metadata.get("bbox"),
        "caption": str(metadata.get("caption") or "").strip(),
        "text": str(getattr(doc, "text", "") or getattr(doc, "content", "") or ""),
        "ocr_text": str(metadata.get("ocr_text") or "").strip(),
        "table_origin": str(metadata.get("table_origin") or "").strip(),
        "formula_normalized": str(
            metadata.get("formula_normalized")
            or metadata.get("normalized_formula")
            or ""
        ).strip(),
        "slide_number": metadata.get("slide_number"),
        "retrieval_path": str(metadata.get("retrieval_path") or "").strip(),
        "score": getattr(doc, "score", None),
        "metadata": metadata,
        "source_backrefs": _source_backrefs(metadata),
    }


def _source_backrefs(metadata: dict[str, Any]) -> list[str]:
    file_id = str(metadata.get("file_id") or "").strip()
    page_label = str(metadata.get("page_label") or "").strip()
    return [f"{file_id}#page:{page_label}"] if file_id and page_label else []


def _merged_doc_metadata(doc: RetrievedDocument) -> dict[str, Any]:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update(metadata)
        return _without_large_image_payloads(merged)
    return _without_large_image_payloads(metadata)


def _without_large_image_payloads(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if key not in _LARGE_IMAGE_METADATA_KEYS
    }


def _append_unique(target: list[str], value: str) -> None:
    if value and value not in target:
        target.append(value)


def _add_multimodal_index_records(
    metadata: dict[str, Any],
    docs: list[RetrievedDocument],
    *,
    question: str,
) -> None:
    page_image_index = page_image_records_from_documents(docs)
    if page_image_index:
        ranked_pages, scores = rank_page_image_records(
            question,
            page_image_index,
        )
        metadata["page_image_index"] = ranked_pages
        metadata["visual_retriever_scores"] = scores
    element_index = element_records_from_documents(docs)
    if element_index:
        metadata["element_index"] = element_index
