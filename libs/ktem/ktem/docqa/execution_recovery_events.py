from __future__ import annotations

from typing import Any

from .boolean_authoritative_conflict import authoritative_conflict_complete
from .controller import RetrieveDecision, VerifyDecision
from .evidence import EvidenceBundle
from .execution_models import RouteExecutionResult
from .query_planning import ensure_request_query_plan
from .recovery_progress import (
    canonical_proposition_binding_digest,
    canonical_recovery_evidence_ids,
    normalized_slot_state_digest,
    semantic_progress_evidence_ids,
    semantic_progress_slot_states,
    semantic_raw_evidence_digest,
    semantic_recovery_pack_digest,
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
    semantic_fields = _semantic_progress_fields(
        initial_bundle,
        recovered_bundle,
        before_slots,
        after_slots,
    )
    digest_fields = _semantic_digest_fields(
        request,
        initial_bundle,
        recovered_bundle,
    )
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
        **semantic_fields,
        **digest_fields,
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


def _semantic_progress_fields(
    initial_bundle: EvidenceBundle | None,
    recovered_bundle: EvidenceBundle | None,
    before_slots: list[dict[str, Any]],
    after_slots: list[dict[str, Any]],
) -> dict[str, Any]:
    before_ids = semantic_progress_evidence_ids(initial_bundle)
    after_ids = semantic_progress_evidence_ids(recovered_bundle)
    new_ids = [value for value in after_ids if value not in before_ids]
    removed_ids = [value for value in before_ids if value not in after_ids]
    before_semantic_slots = semantic_progress_slot_states(initial_bundle, before_slots)
    after_semantic_slots = semantic_progress_slot_states(recovered_bundle, after_slots)
    before_digest = normalized_slot_state_digest(initial_bundle, before_slots)
    after_digest = normalized_slot_state_digest(recovered_bundle, after_slots)
    slot_state_applicable = bool(before_digest or after_digest)
    slot_state_changed = bool(slot_state_applicable and before_digest != after_digest)
    return {
        "semantic_evidence_ids_before": before_ids,
        "semantic_evidence_ids_after": after_ids,
        "new_semantic_evidence_ids": new_ids,
        "removed_semantic_evidence_ids": removed_ids,
        "semantic_slot_states_before": before_semantic_slots,
        "semantic_slot_states_after": after_semantic_slots,
        "semantic_slot_state_changed": slot_state_changed,
        "normalized_slot_state_digest_before": before_digest,
        "normalized_slot_state_digest_after": after_digest,
        "normalized_slot_state_digest_changed": slot_state_changed,
        "normalized_slot_state_digest_applicable": slot_state_applicable,
        "slot_state_digest_before": before_digest,
        "slot_state_digest_after": after_digest,
        "slot_state_digest_changed": slot_state_changed,
        "slot_state_digest_applicable": slot_state_applicable,
    }


def _semantic_digest_fields(
    request: Any | None,
    initial_bundle: EvidenceBundle | None,
    recovered_bundle: EvidenceBundle | None,
) -> dict[str, Any]:
    pack_before = semantic_recovery_pack_digest(request, initial_bundle)
    pack_after = semantic_recovery_pack_digest(request, recovered_bundle)
    pack_applicable = bool(pack_before or pack_after)
    pack_changed = bool(pack_applicable and pack_before != pack_after)
    proposition_before = canonical_proposition_binding_digest(
        request,
        initial_bundle,
    )
    proposition_after = canonical_proposition_binding_digest(
        request,
        recovered_bundle,
    )
    proposition_binding_applicable = bool(proposition_before or proposition_after)
    proposition_binding_changed = bool(
        proposition_binding_applicable and proposition_before != proposition_after
    )
    raw_before = semantic_raw_evidence_digest(initial_bundle)
    raw_after = semantic_raw_evidence_digest(recovered_bundle)
    evidence_applicable = bool(raw_before or raw_after)
    evidence_changed = bool(evidence_applicable and raw_before != raw_after)
    return {
        "semantic_pack_digest_before": pack_before,
        "semantic_pack_digest_after": pack_after,
        "semantic_pack_digest_changed": pack_changed,
        "semantic_pack_digest_applicable": pack_applicable,
        "canonical_proposition_binding_digest_before": proposition_before,
        "canonical_proposition_binding_digest_after": proposition_after,
        "canonical_proposition_binding_digest_changed": proposition_binding_changed,
        "canonical_proposition_binding_digest_applicable": (
            proposition_binding_applicable
        ),
        "proposition_binding_digest_before": proposition_before,
        "proposition_binding_digest_after": proposition_after,
        "proposition_binding_digest_changed": proposition_binding_changed,
        "proposition_binding_digest_applicable": proposition_binding_applicable,
        "proposition_binding_changed": proposition_binding_changed,
        "raw_evidence_digest_before": raw_before,
        "raw_evidence_digest_after": raw_after,
        "raw_evidence_digest_changed": evidence_changed,
        "raw_evidence_digest_applicable": evidence_applicable,
        "evidence_digest_before": raw_before,
        "evidence_digest_after": raw_after,
        "evidence_digest_changed": evidence_changed,
        "evidence_digest_applicable": evidence_applicable,
        "canonical_evidence_ids_before": canonical_recovery_evidence_ids(
            initial_bundle
        ),
        "canonical_evidence_ids_after": canonical_recovery_evidence_ids(
            recovered_bundle
        ),
        "recovery_transition": {
            "from": "verification",
            "to": _semantic_recovery_kind(
                initial_bundle,
                semantic_pack_changed=proposition_binding_changed,
            ),
            "status": (
                "pack_changed" if proposition_binding_changed else "no_pack_change"
            ),
        },
    }


def recovery_has_progress(fields: dict[str, Any]) -> bool:
    return any(
        fields.get(applicable_key) is True and fields.get(changed_key) is True
        for applicable_key, changed_key in (
            (
                "normalized_slot_state_digest_applicable",
                "normalized_slot_state_digest_changed",
            ),
            ("slot_state_digest_applicable", "slot_state_digest_changed"),
            (
                "canonical_proposition_binding_digest_applicable",
                "canonical_proposition_binding_digest_changed",
            ),
            (
                "proposition_binding_digest_applicable",
                "proposition_binding_digest_changed",
            ),
            ("semantic_pack_digest_applicable", "semantic_pack_digest_changed"),
        )
    )


def mark_recovery_no_progress(event: dict[str, Any]) -> dict[str, Any]:
    """Mark a recovery event as terminal without creating a reverify step."""

    event.update(
        {
            "recovery_action": "stop_without_reverify",
            "stop_reason": "recovery_no_progress",
            "authority_changed": False,
            "candidate_changed": False,
            "proposition_binding_changed": False,
        }
    )
    return event


def _semantic_recovery_kind(
    bundle: EvidenceBundle | None,
    *,
    semantic_pack_changed: bool = False,
) -> str:
    if semantic_pack_changed:
        return "evidence_retrieval"
    metadata = bundle.metadata if bundle is not None else {}
    authority = metadata.get("semantic_proposition_authority")
    authority = authority if isinstance(authority, dict) else {}
    verifier = metadata.get("semantic_proposition_verifier")
    verifier = verifier if isinstance(verifier, dict) else {}
    current_reason = _current_semantic_rejection_reason(authority, verifier)
    classified = _recovery_kind_for_reason(current_reason)
    if classified:
        return classified
    transitions = verifier.get("recovery_transitions") or []
    for transition in reversed(transitions):
        if not isinstance(transition, dict):
            continue
        kind = str(transition.get("to") or "")
        if kind in {"proof_repair", "quote_rebind", "proposition_repair"}:
            return kind
    return "evidence_retrieval"


def _current_semantic_rejection_reason(
    authority: dict[str, Any],
    verifier: dict[str, Any],
) -> str:
    rejected = verifier.get("rejected_transactions") or []
    for transaction in reversed(rejected):
        if not isinstance(transaction, dict):
            continue
        reason = str(transaction.get("runtime_rejection_reason") or "").strip()
        if reason:
            return reason.casefold()
    for value in (
        verifier.get("audit_reason"),
        authority.get("reason"),
        verifier.get("reason"),
    ):
        reason = str(value or "").strip()
        if reason:
            return reason.casefold()
    return ""


def _recovery_kind_for_reason(reason: str) -> str:
    if not reason:
        return ""
    if any(value in reason for value in ("quote", "span", "offset")):
        return "quote_rebind"
    if "question_proposition" in reason:
        return "proposition_repair"
    if any(
        value in reason
        for value in (
            "audit",
            "premise",
            "conclusion",
            "contradiction",
            "entailment",
            "quantifier",
            "scope",
            "polarity",
        )
    ):
        return "proof_repair"
    return ""


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
    mark_recovery_no_progress(event)
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
    if not recovery_has_progress(shared):
        mark_recovery_no_progress(rebind)
        if policy != "crag_guarded":
            return [focused, rebind], rebind
        critic = {
            "stage": "critic",
            "status": verify_decision.status,
            "reason": verify_decision.reason,
            **shared,
        }
        return [critic, focused, rebind], rebind
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
