from __future__ import annotations

from typing import Any

from .controller import VerifyDecision
from .evidence import EvidenceBundle
from .route_selection import ControllerDecision


def bundle_evidence_ids(bundle: EvidenceBundle | None) -> list[str]:
    if bundle is None:
        return []
    return list(
        dict.fromkeys(
            str(item.get("evidence_id") or "")
            for item in bundle.items
            if str(item.get("evidence_id") or "")
        )
    )


def record_route_switch_reverification(result: Any) -> None:
    evidence_ids = bundle_evidence_ids(result.evidence_bundle)
    for event in result.controller_trace:
        if event.get("stage") != "route_switch":
            continue
        event.setdefault("reverification_status", result.verify_decision.status)
        event.setdefault("reverification_reason", result.verify_decision.reason)
        event.setdefault("reverification_evidence_ids", evidence_ids)


def build_verifier_switch_event(
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
    focused_query: str,
    failed_verification: VerifyDecision,
    recovered_bundle: EvidenceBundle,
    rejected_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    event = {
        "stage": "route_switch",
        "transition_id": f"verifier-recovery:1:{decision.legacy_route}->{route}",
        "from_route": decision.legacy_route,
        "to_route": route,
        "route_switch_used": True,
        "route_switch_candidates": list(candidates),
        "verifier_recovery_attempt": 1,
        "retrieval_round": 2,
        "focused_query": focused_query,
        "retry_reason": "required_boolean_authority_missing",
        "failure_type": "required_boolean_authority_missing",
        "failed_verifier_status": failed_verification.status,
        "failed_verifier_reason": failed_verification.reason,
        "recovered_evidence_ids": bundle_evidence_ids(recovered_bundle),
    }
    if rejected_candidates:
        event["rejected_route_switch_candidates"] = list(rejected_candidates)
    return event


def build_retrieval_switch_event(
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
    failed_decision: Any,
    failed_bundle: EvidenceBundle,
    recovered_bundle: EvidenceBundle,
    rejected_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    event = {
        "stage": "route_switch",
        "from_route": decision.legacy_route,
        "to_route": route,
        "reason": failed_decision.reason,
        "failure_type": "retrieval_adequacy_failure",
        "route_switch_used": True,
        "route_switch_candidates": list(candidates),
        "failed_retrieval_rounds": int(
            failed_bundle.metadata.get("retrieval_rounds") or 1
        ),
        "failed_slot_coverage": failed_bundle.metadata.get("slot_coverage"),
        "failed_missing_required_slot_count": failed_bundle.metadata.get(
            "missing_required_slot_count"
        ),
        "recovered_evidence_ids": bundle_evidence_ids(recovered_bundle),
    }
    if rejected_candidates:
        event["rejected_route_switch_candidates"] = list(rejected_candidates)
    return event
