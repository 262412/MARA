from __future__ import annotations

import re
from typing import Any

from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of

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
    citation_source = str(citation.get("source_id") or "").strip()
    citation_page = str(citation.get("page_label") or "").strip()
    if evidence_id and evidence_id not in exact_evidence_aliases(item):
        return False
    if evidence_id:
        return True
    locators = _item_locators(item)
    if citation_source and citation_page:
        if (citation_source, citation_page) not in locators:
            return False
    elif citation_source and not any(
        source == citation_source for source, _ in locators
    ):
        return False
    elif citation_page and not any(page == citation_page for _, page in locators):
        return False
    return bool(evidence_id or citation_source or citation_page)


def _item_locators(item: dict[str, Any]) -> set[tuple[str, str]]:
    sources = [
        str(item.get(key) or "").strip()
        for key in ("source_id", "document_id", "file_id", "runtime_source_id")
        if str(item.get(key) or "").strip()
    ]
    pages = [
        str(item.get(key) or "").strip()
        for key in ("page_label", "page", "page_number", "dataset_page")
        if str(item.get(key) or "").strip()
    ]
    locators = {(source, page) for source in sources for page in pages}
    locators.update((source, "") for source in sources if not pages)
    locators.update(("", page) for page in pages if not sources)
    for source_ref in item.get("source_backrefs") or []:
        value = str(source_ref or "").strip()
        if "#page:" in value:
            source_id, page_label = value.split("#page:", 1)
            locators.add((source_id.strip(), page_label.split("#", 1)[0].strip()))
        elif "#source" in value:
            locators.add((value.split("#source", 1)[0].strip(), ""))
    return {locator for locator in locators if any(locator)}
