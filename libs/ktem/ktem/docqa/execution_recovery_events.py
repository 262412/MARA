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


def boolean_slot_states(bundle: EvidenceBundle | None) -> list[dict[str, Any]]:
    if bundle is None:
        return []
    plan: dict[str, Any] = {}
    for key in ("query_plan", "bound_query_plan"):
        candidate = bundle.metadata.get(key)
        if isinstance(candidate, dict):
            plan = candidate
            break
    return [
        {
            "slot_id": str(slot.get("slot_id") or ""),
            "status": str(slot.get("status") or "missing"),
            "evidence_ids": list(slot.get("evidence_ids") or []),
        }
        for slot in plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and str(slot.get("statement_kind") or "")
        in {"answer_relation", "boolean_proposition"}
        and bool(slot.get("required_for_verification"))
    ]


def required_boolean_slot_state(bundle: EvidenceBundle | None) -> str:
    statuses = {item["status"] for item in boolean_slot_states(bundle)}
    for status in (
        "verified_conflict",
        "verified_support",
        "retrieved_unverified",
        "retrieved_partial",
    ):
        if status in statuses:
            return status
    return "missing"


def recovery_trace_fields(
    request: Any | None,
    verify_decision: VerifyDecision,
    initial_bundle: EvidenceBundle | None,
    recovered_bundle: EvidenceBundle | None,
) -> dict[str, Any]:
    before_state, before_atoms = authority_state(verify_decision)
    return {
        "verifier_recovery_attempt": 1,
        "retry_reason": "required_boolean_authority_missing",
        "failure_type": "required_boolean_authority_missing",
        "recovered_evidence_ids": bundle_evidence_ids(recovered_bundle),
        "slot_states_before": boolean_slot_states(initial_bundle),
        "slot_states_after": boolean_slot_states(recovered_bundle),
        "agent_mode": str(getattr(request, "agent_mode", "") or "auto"),
        "verification_mode": str(
            getattr(request, "verification_mode", "") or verify_decision.mode or "off"
        ),
        "authority_state_before": before_state,
        "authority_atoms_before": before_atoms,
    }


def authority_state(decision: VerifyDecision) -> tuple[str, list[str]]:
    authority = decision.typed_authority
    if not isinstance(authority, dict):
        return "", []
    atoms = [
        ":".join(
            (
                str(atom.get("evidence_id") or ""),
                str(atom.get("evidence_ref") or atom.get("span_id") or ""),
            )
        )
        for atom in authority.get("authority_atoms") or []
        if isinstance(atom, dict)
    ]
    return str(authority.get("state") or ""), atoms


def record_route_switch_reverification(result: Any) -> None:
    evidence_ids = bundle_evidence_ids(result.evidence_bundle)
    for event in result.controller_trace:
        if event.get("stage") != "route_switch":
            continue
        event.setdefault("reverification_status", result.verify_decision.status)
        event.setdefault("reverification_reason", result.verify_decision.reason)
        event.setdefault("reverification_evidence_ids", evidence_ids)


def build_verifier_switch_event(
    request: Any,
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
    focused_query: str,
    failed_verification: VerifyDecision,
    failed_bundle: EvidenceBundle,
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
        "retrieval_round": int(
            recovered_bundle.metadata.get("verifier_recovery_round") or 2
        ),
        "focused_query": focused_query,
        "retry_reason": "required_boolean_authority_missing",
        "failure_type": "required_boolean_authority_missing",
        "failed_verifier_status": failed_verification.status,
        "failed_verifier_reason": failed_verification.reason,
        "recovered_evidence_ids": bundle_evidence_ids(recovered_bundle),
        "slot_states_before": boolean_slot_states(failed_bundle),
        "slot_states_after": boolean_slot_states(recovered_bundle),
        "agent_mode": str(getattr(request, "agent_mode", "") or "auto"),
        "verification_mode": str(
            getattr(request, "verification_mode", "")
            or failed_verification.mode
            or "off"
        ),
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
