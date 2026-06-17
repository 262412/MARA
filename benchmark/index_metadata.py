from __future__ import annotations

from typing import Any


def normalize_retrieved_hit(item: dict[str, Any]) -> dict[str, Any]:
    metadata = _merged_metadata(item)
    source_id = _first_text(item, metadata, "source_id", "file_id", "document_id")
    page_label = _first_text(
        item,
        metadata,
        "page_label",
        "page",
        "page_number",
        "page_num",
    )
    hit = {
        "evidence_id": _first_text(item, metadata, "evidence_id", "doc_id"),
        "document_id": _first_text(item, metadata, "document_id") or source_id,
        "source_id": source_id,
        "source_name": _first_text(item, metadata, "source_name", "file_name"),
        "page_label": page_label,
        "page_index": _page_index(item, metadata),
        "modality": _first_text(item, metadata, "modality", "element_type", "type"),
        "element_id": _first_text(item, metadata, "element_id", "element"),
        "score": item.get("score", metadata.get("score")),
        "text": _first_text(item, metadata, "text", "content", "snippet"),
        "source_backrefs": _source_backrefs(item, metadata),
    }
    return {key: value for key, value in hit.items() if value not in ("", [], None)}


def _merged_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update(metadata)
        return merged
    return metadata


def _first_text(
    item: dict[str, Any],
    metadata: dict[str, Any],
    *keys: str,
) -> str:
    for key in keys:
        value = item.get(key)
        if value in (None, ""):
            value = metadata.get(key)
        text = _text(value)
        if text:
            return text
    return ""


def _page_index(item: dict[str, Any], metadata: dict[str, Any]) -> int | None:
    text = _first_text(item, metadata, "page_index")
    if not text:
        return None
    return int(text)


def _source_backrefs(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> list[str]:
    refs = item.get("source_backrefs")
    if refs in (None, ""):
        refs = metadata.get("source_backrefs")
    if isinstance(refs, str):
        return [refs] if refs.strip() else []
    return [str(ref) for ref in refs or [] if str(ref).strip()]


def _text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()
