from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from .calculation_citation_projection import (
    calculation_citation_items,
    record_calculation_stage_evidence,
)


def record_execution_operand_evidence(
    prediction: dict[str, Any],
    candidates: list[dict[str, Any]],
    canonical_sources: list[str],
) -> None:
    record_calculation_stage_evidence(
        prediction,
        calculation_citation_items(prediction, candidates),
        canonical_sources=canonical_sources,
    )


def typed_calculation_is_verified(prediction: dict[str, Any]) -> bool:
    for container in _trace_containers(prediction):
        trace = dict(container.get("finance_numeric_trace") or {})
        verification = dict(trace.get("calculation_verification") or {})
        execution = dict(trace.get("calculation_execution") or {})
        if verification.get("valid") and execution.get("status") == "ok":
            return True
    return False


def record_verified_claim_support(
    prediction: dict[str, Any],
    items: list[dict[str, Any]],
) -> None:
    unique: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        identity = identity_of(item).key
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(item)
    for metadata in citation_metadata_targets(prediction):
        metadata["verified_claim_support_evidence"] = list(unique)


def clear_answer_citation_state(prediction: dict[str, Any]) -> None:
    prediction["structured_citations"] = []
    prediction["predicted_citations"] = []
    for metadata in citation_metadata_targets(prediction):
        metadata["verified_claim_support_evidence"] = []
        metadata["emitted_citation_evidence"] = []
        metadata["cited_evidence"] = []


def authoritative_verified_claim_support(
    prediction: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]] | None:
    """Resolve one exact verified-claim support state or fail closed.

    Narrative FinanceBench answers may only emit citations from the versioned
    QueryPlan state committed by claim verification. Page aliases and merely
    selected evidence are intentionally insufficient authority.
    """

    authoritative: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []
    for metadata in citation_metadata_targets(prediction):
        plan = metadata.get("terminal_query_plan") or metadata.get("query_plan")
        if not isinstance(plan, dict):
            continue
        if str(plan.get("state_authority") or "") != "verified_claim_support.v1":
            continue
        support_items = [
            dict(item)
            for item in metadata.get("verified_claim_support_evidence") or []
            if isinstance(item, dict)
        ]
        authoritative.append((support_items, dict(plan)))
    if not authoritative:
        return None
    support_items, plan = authoritative[0]
    expected_ids = _verified_plan_support_ids(plan)
    support_ids = _item_identities(support_items)
    if not expected_ids or support_ids != expected_ids:
        return None
    for other_items, other_plan in authoritative[1:]:
        if _verified_plan_support_ids(other_plan) != expected_ids:
            return None
        if _item_identities(other_items) != expected_ids:
            return None
    selected = _selected_evidence(prediction)
    available = _available_evidence(prediction)
    if not selected or not available:
        return None
    if not expected_ids <= _item_identities(selected):
        return None
    if not expected_ids <= _item_identities(available):
        return None
    decision = _verify_decision(prediction)
    if str(decision.get("status") or "") != "supported":
        return None
    resolved = {
        identity_of(item).key: item for item in available if isinstance(item, dict)
    }
    return [resolved[evidence_id] for evidence_id in sorted(expected_ids)], plan


def citation_metadata_targets(
    prediction: dict[str, Any],
) -> list[dict[str, Any]]:
    metadata = prediction.get("evidence_metadata")
    if not isinstance(metadata, dict):
        metadata = {}
        prediction["evidence_metadata"] = metadata
    targets = [metadata]
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict) and isinstance(bundle.get("metadata"), dict):
        targets.append(bundle["metadata"])
    return targets


def _verified_plan_support_ids(plan: dict[str, Any]) -> set[str]:
    slots = [
        dict(slot)
        for slot in plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and bool(slot.get("required_for_verification"))
        and str(slot.get("role") or "") == "support"
    ]
    if not slots or any(
        str(slot.get("status") or "") != "verified_support"
        or not list(slot.get("evidence_ids") or [])
        for slot in slots
    ):
        return set()
    evidence_ids = {
        str(evidence_id).strip()
        for slot in slots
        for evidence_id in slot.get("evidence_ids") or []
        if str(evidence_id or "").strip()
    }
    return evidence_ids


def _item_identities(items: list[dict[str, Any]]) -> set[str]:
    identities: set[str] = set()
    for item in items:
        try:
            identities.add(identity_of(item).key)
        except (TypeError, ValueError):
            return set()
    return identities


def _selected_evidence(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for metadata in citation_metadata_targets(prediction):
        output.extend(
            item
            for item in metadata.get("selected_evidence") or []
            if isinstance(item, dict)
        )
    return output


def _available_evidence(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    output = list(_selected_evidence(prediction))
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        output.extend(
            item for item in bundle.get("items") or [] if isinstance(item, dict)
        )
    for metadata in citation_metadata_targets(prediction):
        for key in ("evidence", "generation_context_evidence"):
            output.extend(
                item for item in metadata.get(key) or [] if isinstance(item, dict)
            )
    return output


def _verify_decision(prediction: dict[str, Any]) -> dict[str, Any]:
    direct = prediction.get("verify_decision")
    if isinstance(direct, dict):
        return direct
    for metadata in citation_metadata_targets(prediction):
        decision = metadata.get("verify_decision")
        if isinstance(decision, dict):
            return decision
    return {}


def _trace_containers(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    containers = []
    metadata = prediction.get("evidence_metadata")
    if isinstance(metadata, dict):
        containers.append(metadata)
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        bundle_metadata = bundle.get("metadata")
        if isinstance(bundle_metadata, dict):
            containers.append(bundle_metadata)
        containers.append(bundle)
    return containers
