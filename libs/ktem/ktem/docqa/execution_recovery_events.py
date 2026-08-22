from __future__ import annotations

from typing import Any

from .boolean_authoritative_conflict import authoritative_conflict_complete
from .controller import RetrieveDecision, VerifyDecision
from .evidence import EvidenceBundle
from .execution_models import RouteExecutionResult
from .query_planning import ensure_request_query_plan
from .recovery_progress import (
    semantic_progress_evidence_ids,
    semantic_progress_slot_states,
)
from .route_budget import route_budget_metadata
from .route_selection import ControllerDecision
from .typed_retrieval_recovery import verifier_recovery_frame


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


def typed_slot_states(bundle: EvidenceBundle | None) -> list[dict[str, Any]]:
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


def required_typed_slot_state(bundle: EvidenceBundle | None) -> str:
    statuses = {item["status"] for item in typed_slot_states(bundle)}
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
    *,
    candidate_answer: str = "",
) -> dict[str, Any]:
    before_state, before_atoms = authority_state(verify_decision)
    reason = required_authority_recovery_reason(request)
    before_ids = bundle_evidence_ids(initial_bundle)
    after_ids = bundle_evidence_ids(recovered_bundle)
    new_ids = [value for value in after_ids if value not in before_ids]
    removed_ids = [value for value in before_ids if value not in after_ids]
    before_slots = typed_slot_states(initial_bundle)
    after_slots = typed_slot_states(recovered_bundle)
    before_semantic_ids = semantic_progress_evidence_ids(initial_bundle)
    after_semantic_ids = semantic_progress_evidence_ids(recovered_bundle)
    new_semantic_ids = [
        value for value in after_semantic_ids if value not in before_semantic_ids
    ]
    removed_semantic_ids = [
        value for value in before_semantic_ids if value not in after_semantic_ids
    ]
    before_semantic_slots = semantic_progress_slot_states(
        initial_bundle,
        before_slots,
    )
    after_semantic_slots = semantic_progress_slot_states(
        recovered_bundle,
        after_slots,
    )
    semantic_slot_state_changed = before_semantic_slots != after_semantic_slots
    typed = verify_decision.typed_authority
    typed = typed if isinstance(typed, dict) else {}
    return {
        "verifier_recovery_attempt": 1,
        "retry_reason": reason,
        "failure_type": reason,
        "typed_failure_reason": str(typed.get("reason") or ""),
        "recovered_evidence_ids": after_ids,
        "evidence_ids_before": before_ids,
        "evidence_ids_after": after_ids,
        "new_evidence_ids": new_ids,
        "removed_evidence_ids": removed_ids,
        "semantic_evidence_ids_before": before_semantic_ids,
        "semantic_evidence_ids_after": after_semantic_ids,
        "new_semantic_evidence_ids": new_semantic_ids,
        "removed_semantic_evidence_ids": removed_semantic_ids,
        "slot_states_before": before_slots,
        "slot_states_after": after_slots,
        "slot_state_changed": before_slots != after_slots,
        "semantic_slot_states_before": before_semantic_slots,
        "semantic_slot_states_after": after_semantic_slots,
        "semantic_slot_state_changed": semantic_slot_state_changed,
        "proposition_binding_changed": bool(
            new_semantic_ids or removed_semantic_ids or semantic_slot_state_changed
        ),
        "candidate_answer_before": candidate_answer,
        "candidate_answer_after": candidate_answer,
        "candidate_changed": False,
        "agent_mode": str(getattr(request, "agent_mode", "") or "auto"),
        "verification_mode": str(
            getattr(request, "verification_mode", "") or verify_decision.mode or "off"
        ),
        "authority_state_before": before_state,
        "authority_atoms_before": before_atoms,
        **route_budget_metadata(request),
    }


def recovery_has_progress(fields: dict[str, Any]) -> bool:
    return bool(
        fields.get("new_semantic_evidence_ids")
        or fields.get("semantic_slot_state_changed")
        or fields.get("authority_changed")
    )


def retrieval_no_progress_decision(
    trace: list[dict[str, Any]],
    decision: RetrieveDecision,
) -> RetrieveDecision | None:
    event = next(
        (
            value
            for value in reversed(trace)
            if value.get("stop_reason") == "recovery_no_progress"
        ),
        None,
    )
    if event is None:
        return None
    return RetrieveDecision(
        status=("poor" if event.get("evidence_ids_after") == [] else decision.status),
        reason=(
            "Retrieval recovery produced no new semantic candidate or slot state. "
            "stop_reason=recovery_no_progress."
        ),
        retry=False,
    )


def same_route_verifier_recovery_trace(
    policy: str,
    verify_decision: VerifyDecision,
    retrieve_decision: Any,
    focused_query: str,
    *,
    request: Any | None = None,
    initial_bundle: EvidenceBundle | None = None,
    recovered_bundle: EvidenceBundle | None = None,
    candidate_answer: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    shared = recovery_trace_fields(
        request,
        verify_decision,
        initial_bundle,
        recovered_bundle,
        candidate_answer=candidate_answer,
    )
    shared["recovery_frame"] = verifier_recovery_frame(request)
    retrieval_round = int(
        (recovered_bundle.metadata if recovered_bundle else {}).get(
            "verifier_recovery_round"
        )
        or 2
    )
    focused = {
        "stage": "focused_retrieval",
        "retrieval_round": retrieval_round,
        "focused_query": focused_query,
        "status": retrieve_decision.status,
        "recovery_action": "targeted_retrieval",
        **shared,
    }
    rebind = {
        "stage": "evidence_rebind",
        "retrieval_round": retrieval_round,
        "status": retrieve_decision.status,
        "recovery_action": "rebind_recovered_evidence",
        **shared,
    }
    reverify = {
        "stage": "reverify",
        "attempt": 1,
        "recovery_action": "fresh_reverification",
        **shared,
    }
    if policy != "crag_guarded":
        return [focused, rebind, reverify], reverify
    critic = {
        "stage": "critic",
        "status": verify_decision.status,
        "reason": verify_decision.reason,
        **shared,
    }
    return [critic, focused, rebind, reverify], reverify


def copy_reverification_outcome(
    route_switch_event: dict[str, Any],
    reverify_event: dict[str, Any],
) -> None:
    for key in (
        "slot_states_after",
        "recovered_evidence_ids",
        "authority_state_after",
        "authority_atoms_after",
        "authority_changed",
        "candidate_answer_after",
        "candidate_changed",
        "verification_status",
    ):
        route_switch_event[key] = reverify_event.get(key)


def required_authority_recovery_reason(request: Any | None) -> str:
    if request is None:
        return "required_typed_authority_missing"
    plan = ensure_request_query_plan(request)
    answer_type = str(getattr(plan, "answer_type", "") or "").lower()
    kinds = {
        str(getattr(slot, "statement_kind", "") or "").lower()
        for slot in getattr(plan, "evidence_slots", ()) or ()
        if bool(getattr(slot, "required_for_verification", False))
    }
    if answer_type == "boolean" or "boolean_proposition" in kinds:
        return "required_boolean_authority_missing"
    if "answer_relation" in kinds:
        return "required_answer_relation_authority_missing"
    return "required_typed_authority_missing"


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


def mark_resolved_initial_conflict(result: RouteExecutionResult) -> None:
    decision = result.verify_decision
    if decision.status != "verified_conflict" or not authoritative_conflict_complete(
        decision.authoritative_conflict
    ):
        return
    for event in reversed(result.controller_trace):
        if event.get("stage") == "verifier":
            event["stop_reason"] = "authority_conflict_resolved"
            break


def raw_candidate(result: RouteExecutionResult) -> str:
    raw_answer = result.engine_terminal_state.get("raw_generated_answer")
    return str(result.answer if raw_answer is None else raw_answer)


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
    reason = required_authority_recovery_reason(request)
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
        "retry_reason": reason,
        "failure_type": reason,
        "failed_verifier_status": failed_verification.status,
        "failed_verifier_reason": failed_verification.reason,
        "recovered_evidence_ids": bundle_evidence_ids(recovered_bundle),
        "slot_states_before": typed_slot_states(failed_bundle),
        "slot_states_after": typed_slot_states(recovered_bundle),
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


boolean_slot_states = typed_slot_states
required_boolean_slot_state = required_typed_slot_state


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
