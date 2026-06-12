from __future__ import annotations

from typing import Any


def retrieved_hits_from_docqa_evidence(
    evidence_bundle: dict[str, Any],
    evidence_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    bundle_items = (
        evidence_bundle.get("items") if isinstance(evidence_bundle, dict) else []
    )
    evidence_items = bundle_items or evidence_metadata.get("evidence") or []
    return [
        _retrieved_hit_from_evidence_item(item)
        for item in evidence_items
        if isinstance(item, dict)
    ]


def evidence_pages(retrieved_hits: list[dict[str, Any]]) -> list[str]:
    pages: list[str] = []
    for hit in retrieved_hits:
        page = str(hit.get("page_label") or "").strip()
        if page and page not in pages:
            pages.append(page)
    return pages


def evidence_sources(retrieved_hits: list[dict[str, Any]]) -> list[str]:
    sources: list[str] = []
    for hit in retrieved_hits:
        refs = list(hit.get("source_backrefs") or [])
        if not refs:
            source_id = str(
                hit.get("source_id") or hit.get("document_id") or ""
            ).strip()
            page = str(hit.get("page_label") or "").strip()
            refs = [f"{source_id}#page:{page}"] if source_id and page else []
        for ref in refs:
            source = str(ref).strip()
            if source and source not in sources:
                sources.append(source)
    return sources


def evidence_element_ids(retrieved_hits: list[dict[str, Any]]) -> list[str]:
    element_ids: list[str] = []
    for hit in retrieved_hits:
        element_id = str(hit.get("element_id") or "").strip()
        if element_id and element_id not in element_ids:
            element_ids.append(element_id)
    return element_ids


def _retrieved_hit_from_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    source_id = str(item.get("source_id") or item.get("file_id") or "").strip()
    source_name = str(item.get("source_name") or item.get("file_name") or "").strip()
    page_label = str(item.get("page_label") or item.get("page") or "").strip()
    modality = str(
        item.get("modality") or item.get("element_type") or item.get("type") or ""
    ).strip()
    hit = {
        "evidence_id": str(item.get("evidence_id") or item.get("doc_id") or "").strip(),
        "document_id": source_id,
        "source_id": source_id,
        "source_name": source_name,
        "page_label": page_label,
        "modality": modality,
        "element_id": str(item.get("element_id") or "").strip(),
        "score": item.get("score"),
        "text": str(item.get("text") or item.get("content") or ""),
        "source_backrefs": _item_source_backrefs(item, source_id, page_label),
    }
    return {key: value for key, value in hit.items() if value not in ("", [], None)}


def _item_source_backrefs(
    item: dict[str, Any],
    source_id: str,
    page_label: str,
) -> list[str]:
    refs = [str(ref) for ref in item.get("source_backrefs") or [] if str(ref).strip()]
    if refs:
        return refs
    if source_id and page_label:
        return [f"{source_id}#page:{page_label}"]
    return []
