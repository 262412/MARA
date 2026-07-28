from __future__ import annotations

from typing import Any

from .docqa_runtime_sources import canonicalize_docqa_hits
from .index_metadata import normalize_retrieved_hit


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
            refs = _fallback_source_backrefs(source_id, page)
        for ref in refs:
            source = str(ref).strip()
            if source and source not in sources:
                sources.append(source)
    return sources


def evidence_element_ids(retrieved_hits: list[dict[str, Any]]) -> list[str]:
    element_ids: list[str] = []
    for hit in retrieved_hits:
        element_id = str(
            hit.get("cell_id")
            or hit.get("element_id")
            or dict(hit.get("identity") or {}).get("local_id")
            or ""
        ).strip()
        if element_id and element_id not in element_ids:
            element_ids.append(element_id)
    return element_ids


def metadata_page_coverage(evidence_metadata: dict[str, Any]) -> list[str]:
    pages: list[str] = []
    for item in evidence_metadata.get("page_coverage") or []:
        page = _page_coverage_label(item)
        if page and page not in pages:
            pages.append(page)
    return pages


def metadata_page_coverage_sources(
    evidence_metadata: dict[str, Any],
    documents: list[Any],
    selected_file_ids: list[str],
) -> list[str]:
    hits = _metadata_page_coverage_hits(evidence_metadata, documents)
    canonical_hits = canonicalize_docqa_hits(hits, documents, selected_file_ids)
    return evidence_sources(canonical_hits)


def _retrieved_hit_from_evidence_item(item: dict[str, Any]) -> dict[str, Any]:
    hit = normalize_retrieved_hit(item)
    source_id = str(hit.get("source_id") or hit.get("document_id") or "").strip()
    page_label = str(hit.get("page_label") or "").strip()
    hit["source_backrefs"] = _item_source_backrefs(hit, source_id, page_label)
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
    if source_id:
        return [f"{source_id}#source"]
    return []


def _fallback_source_backrefs(source_id: str, page_label: str) -> list[str]:
    if source_id and page_label:
        return [f"{source_id}#page:{page_label}"]
    if source_id:
        return [f"{source_id}#source"]
    return []


def _metadata_page_coverage_hits(
    evidence_metadata: dict[str, Any],
    documents: list[Any],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for item in evidence_metadata.get("page_coverage") or []:
        page = _page_coverage_label(item)
        if not page:
            continue
        hit = _page_coverage_hit(item)
        hit["page_label"] = page
        if not _has_source_locator(hit):
            if len(documents) != 1:
                continue
            hit["source_id"] = documents[0].document_id
        hits.append(hit)
    return hits


def _page_coverage_hit(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    hit = {
        key: value
        for key, value in item.items()
        if key
        in {
            "document_id",
            "file_id",
            "page",
            "page_label",
            "page_number",
            "source_backrefs",
            "source_id",
            "source_name",
        }
    }
    if hit.get("file_id") and not (hit.get("source_id") or hit.get("document_id")):
        hit["source_id"] = hit["file_id"]
    return hit


def _has_source_locator(hit: dict[str, Any]) -> bool:
    return bool(
        str(
            hit.get("source_id")
            or hit.get("document_id")
            or hit.get("file_id")
            or hit.get("source_name")
            or ""
        ).strip()
        or hit.get("source_backrefs")
    )


def _page_coverage_label(item: Any) -> str:
    if isinstance(item, dict):
        item = item.get("page_label") or item.get("page") or item.get("page_number")
    if item is None:
        return ""
    return str(item).strip()
