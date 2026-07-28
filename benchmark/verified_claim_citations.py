from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup


def verified_claim_support_items(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    alias_lookup = unambiguous_evidence_alias_lookup(candidates)
    items: list[dict[str, Any]] = []
    for metadata in _metadata_sources(prediction):
        by_claim = metadata.get("verified_claim_support_by_claim")
        if isinstance(by_claim, dict):
            for values in by_claim.values():
                for value in values or []:
                    if isinstance(value, dict):
                        items.append(value)
                        continue
                    item = alias_lookup.get(str(value or "").strip())
                    if item is not None:
                        items.append(item)
        items.extend(
            item
            for item in metadata.get("verified_claim_support_evidence") or []
            if isinstance(item, dict)
        )
    return items


def _metadata_sources(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    sources: list[dict[str, Any]] = []
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        bundle_metadata = evidence_bundle.get("metadata")
        if isinstance(bundle_metadata, dict):
            sources.append(bundle_metadata)
    evidence_metadata = prediction.get("evidence_metadata")
    if isinstance(evidence_metadata, dict):
        sources.append(evidence_metadata)
    return sources
