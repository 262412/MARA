from __future__ import annotations

import re
from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of
from ktem.docqa.evidence_locators import normalized_source_page_locators

from .citation_locators import CitationLocator

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
    alias_lookup = unambiguous_evidence_alias_lookup(candidates)
    for raw_citation in citations:
        citation = CitationLocator.from_mapping(raw_citation)
        if citation.kind in {"page", "source"} and not citation.evidence_identity:
            if not _locator_is_present(citation, candidates):
                continue
            page_record = citation.page_evidence_record()
            identity = str(page_record["canonical_id"])
            if identity not in cited_identities:
                cited_identities.add(identity)
                cited_items.append(page_record)
            continue
        for item in candidates:
            if not _citation_matches_item(
                citation,
                item,
                alias_lookup=alias_lookup,
            ):
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
    citation: CitationLocator | dict[str, str],
    item: dict[str, Any],
    *,
    alias_lookup: dict[str, dict[str, Any]] | None = None,
) -> bool:
    locator = (
        citation
        if isinstance(citation, CitationLocator)
        else CitationLocator.from_mapping(citation)
    )
    evidence_id = locator.evidence_identity
    citation_source = locator.source_id.strip().lower()
    citation_page = locator.page_label.strip().lower()
    item_identity = identity_of(item)
    if (
        locator.kind
        and locator.kind not in {"page", "source"}
        and locator.kind != item_identity.kind
    ):
        return False
    if evidence_id:
        if alias_lookup is not None:
            matched = alias_lookup.get(evidence_id)
            if matched is None or identity_of(matched) != item_identity:
                return False
        elif evidence_id not in exact_evidence_aliases(item):
            return False
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
    if evidence_id and evidence_id != item_identity.key and not citation_source:
        return False
    return bool(evidence_id or citation_source or citation_page)


def _locator_is_present(
    citation: CitationLocator,
    candidates: list[dict[str, Any]],
) -> bool:
    return any(
        (
            not citation.source_id
            or any(
                source == citation.source_id for source, _page in _item_locators(item)
            )
        )
        and (
            not citation.page_label
            or (
                citation.source_id,
                citation.page_label,
            )
            in _item_locators(item)
            or (
                not citation.source_id
                and any(
                    page == citation.page_label
                    for _source, page in _item_locators(item)
                )
            )
        )
        for item in candidates
    )


def _item_locators(item: dict[str, Any]) -> set[tuple[str, str]]:
    return normalized_source_page_locators(item)
