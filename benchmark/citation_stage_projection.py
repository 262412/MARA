from __future__ import annotations

import re
from typing import Any

from ktem.docqa.evidence_identity import evidence_aliases, identity_of

_UUID_LIKE_SOURCE_RE = re.compile(
    r"^(?:[0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def is_uuid_like_source_id(source_id: str) -> bool:
    return bool(_UUID_LIKE_SOURCE_RE.fullmatch(str(source_id or "").strip()))


def source_ref_uses_uuid_like_source(source_ref: str) -> bool:
    source_id = str(source_ref or "").strip().split("#", 1)[0]
    return is_uuid_like_source_id(source_id)


def record_emitted_citation_evidence(
    prediction: dict[str, Any],
    *,
    citations: list[dict[str, str]],
    candidates: list[dict[str, Any]],
) -> None:
    cited_items: list[dict[str, Any]] = []
    cited_identities: set[str] = set()
    for citation in citations:
        for item in candidates:
            if not _citation_matches_item(citation, item):
                continue
            identity = identity_of(item).key
            if identity in cited_identities:
                continue
            cited_identities.add(identity)
            cited_items.append(item)

    evidence_bundle = prediction.get("evidence_bundle")
    metadata_targets: list[dict[str, Any]] = []
    if isinstance(evidence_bundle, dict):
        bundle_metadata = evidence_bundle.get("metadata")
        if isinstance(bundle_metadata, dict):
            metadata_targets.append(bundle_metadata)
    evidence_metadata = prediction.get("evidence_metadata")
    if not isinstance(evidence_metadata, dict):
        evidence_metadata = {}
        prediction["evidence_metadata"] = evidence_metadata
    metadata_targets.append(evidence_metadata)
    for metadata in metadata_targets:
        metadata["emitted_citation_evidence"] = list(cited_items)
        metadata["cited_evidence"] = list(cited_items)
        metadata["citation_stage_contract"] = "emitted_citation_evidence.v1"


def _citation_matches_item(
    citation: dict[str, str],
    item: dict[str, Any],
) -> bool:
    evidence_id = str(citation.get("evidence_id") or "").strip()
    if evidence_id:
        return evidence_id in evidence_aliases(item)
    citation_source = str(citation.get("source_id") or "").strip()
    citation_page = str(citation.get("page_label") or "").strip()
    item_sources = {
        str(item.get(key) or "").strip()
        for key in ("source_id", "document_id", "file_id", "runtime_source_id")
        if str(item.get(key) or "").strip()
    }
    item_pages = {
        str(item.get(key) or "").strip()
        for key in ("page_label", "page", "page_number", "dataset_page")
        if str(item.get(key) or "").strip()
    }
    for source_ref in item.get("source_backrefs") or []:
        source = str(source_ref or "").strip()
        if "#page:" in source:
            source_id, page_label = source.split("#page:", 1)
            item_sources.add(source_id)
            item_pages.add(page_label)
        elif "#source" in source:
            item_sources.add(source.split("#source", 1)[0])
    if citation_source and citation_source not in item_sources:
        return False
    if citation_page and citation_page not in item_pages:
        return False
    return bool(citation_source or citation_page)
