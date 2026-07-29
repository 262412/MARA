from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from kotaemon.base import RetrievedDocument


def cache_generation_context(
    pipeline: Any,
    message: str,
    history: list[Any],
    bundle: Any,
) -> None:
    """Make the selected evidence set the actual text-generation context."""

    cached = getattr(pipeline, "_mara_cached_retrieval", None)
    info = cached[3] if isinstance(cached, tuple) and len(cached) == 4 else []
    docs = [
        doc for item in bundle.items if (doc := _generation_document(item)) is not None
    ]
    pipeline._mara_cached_retrieval = (
        str(message or ""),
        list(history),
        docs,
        info,
    )
    bundle.metadata["generation_context_evidence"] = list(bundle.items)
    bundle.metadata["generation_context_contract"] = "selected_bundle.v1"


def _generation_document(item: dict[str, Any]) -> RetrievedDocument | None:
    text = _item_text(item)
    if not text:
        return None
    identity = identity_of(item).key
    metadata = dict(item.get("metadata") or {})
    for field in (
        "source_id",
        "source_name",
        "page_label",
        "modality",
        "element_id",
        "canonical_id",
        "parent_element_id",
        "section_id",
        "table_id",
        "row_index",
        "column_index",
        "cell_id",
        "caption",
        "ocr_text",
        "vlm_text",
    ):
        value = item.get(field)
        if value not in (None, ""):
            metadata[field] = value
    metadata["canonical_id"] = identity
    metadata.setdefault("file_id", str(item.get("source_id") or ""))
    metadata.setdefault(
        "file_name",
        str(item.get("source_name") or item.get("source_id") or "evidence"),
    )
    if str(item.get("modality") or "") == "table":
        metadata.setdefault("type", "table")
        metadata.setdefault("table_origin", text)
    return RetrievedDocument(
        text=text,
        doc_id=identity,
        metadata=metadata,
        score=_score(item),
    )


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _score(item: dict[str, Any]) -> float:
    metadata = dict(item.get("metadata") or {})
    for value in (
        item.get("reranker_score"),
        item.get("reranking_score"),
        item.get("score"),
        metadata.get("reranker_score"),
        metadata.get("reranking_score"),
        metadata.get("score"),
    ):
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0
