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
        "element_id_aliases": _first_list(item, metadata, "element_id_aliases"),
        "element_type_aliases": _first_list(item, metadata, "element_type_aliases"),
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


def _first_list(
    item: dict[str, Any],
    metadata: dict[str, Any],
    key: str,
) -> list[str]:
    values = _list_values(item.get(key))
    if not values:
        values = _list_values(metadata.get(key))
    return _dedupe_text(values)


def _page_index(item: dict[str, Any], metadata: dict[str, Any]) -> int | None:
    text = _first_text(item, metadata, "page_index")
    if not text:
        return None
    return int(text)


def _source_backrefs(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> list[str]:
    refs: list[str] = []
    for key in ("source_backrefs", "citations", "sources", "source_refs"):
        refs.extend(_source_ref_values(item.get(key)))
        refs.extend(_source_ref_values(metadata.get(key)))
    for key in ("citation", "source", "source_ref", "reference"):
        refs.extend(_source_ref_values(item.get(key)))
        refs.extend(_source_ref_values(metadata.get(key)))
    return _dedupe_text(refs)


def _source_ref_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _list_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if str(item).strip()]
    return []


def _dedupe_text(values: list[str]) -> list[str]:
    refs: list[str] = []
    for value in values:
        ref = str(value).strip()
        if ref and ref not in refs:
            refs.append(ref)
    return refs


def _text(value: Any) -> str:
    if value in (None, ""):
        return ""
    return str(value).strip()
