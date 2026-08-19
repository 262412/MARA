from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_alias_lookup import unambiguous_evidence_alias_lookup
from ktem.docqa.evidence_identity import identity_of


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
        if not items:
            items.extend(_qasper_authoritative_items(metadata, alias_lookup))
    return items


def verified_claim_support_groups(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    alias_lookup = unambiguous_evidence_alias_lookup(candidates)
    groups: dict[str, list[dict[str, Any]]] = {}
    for metadata in _metadata_sources(prediction):
        by_claim = metadata.get("verified_claim_support_by_claim")
        if not isinstance(by_claim, dict):
            continue
        for claim_id, values in by_claim.items():
            group = groups.setdefault(str(claim_id), [])
            for value in values or []:
                item = (
                    value if isinstance(value, dict) else alias_lookup.get(str(value))
                )
                if item is None:
                    continue
                identity = identity_of(item).key
                if all(identity_of(existing).key != identity for existing in group):
                    group.append(item)
    resolved_groups = [group for group in groups.values() if group]
    if resolved_groups:
        return resolved_groups
    decision_groups = _verified_decision_support_groups(prediction, alias_lookup)
    if decision_groups:
        return decision_groups
    for metadata in _metadata_sources(prediction):
        authoritative = _qasper_authoritative_items(metadata, alias_lookup)
        if authoritative:
            return [authoritative]
    flat = verified_claim_support_items(prediction, candidates)
    return [[item] for item in flat]


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


def _qasper_authoritative_items(
    metadata: dict[str, Any],
    alias_lookup: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    trace = metadata.get("qasper_answerability")
    if not isinstance(trace, dict):
        return []
    evidence_id = str(trace.get("authoritative_quote_evidence_id") or "").strip()
    item = alias_lookup.get(evidence_id)
    return [item] if item is not None else []


def _verified_decision_support_groups(
    prediction: dict[str, Any],
    alias_lookup: dict[str, dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    decision = prediction.get("verify_decision")
    if not isinstance(decision, dict):
        decision = prediction.get("engine_verify_decision")
    if not isinstance(decision, dict):
        return []
    groups: list[list[dict[str, Any]]] = []
    for result in decision.get("claim_results") or []:
        if (
            not isinstance(result, dict)
            or str(result.get("status") or "") != "supported"
        ):
            continue
        group: list[dict[str, Any]] = []
        for evidence_id in result.get("supporting_evidence_ids") or []:
            item = alias_lookup.get(str(evidence_id).strip())
            if item is not None and all(
                identity_of(existing).key != identity_of(item).key for existing in group
            ):
                group.append(item)
        if group:
            groups.append(group)
    return groups
