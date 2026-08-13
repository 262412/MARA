from __future__ import annotations

from typing import Any

from .boolean_authoritative_conflict import authoritative_conflict_complete
from .controller import RetrieveDecision, VerifyDecision, evaluate_retrieval_quality
from .evidence import EvidenceBundle
from .execution_models import RetrieveFn, RewriteFn, RouteExecutionResult
from .execution_planning import build_execution_workflow_plan
from .execution_recovery_events import authority_state as _authority_state
from .execution_recovery_events import boolean_slot_states as _boolean_slot_states
from .execution_recovery_events import bundle_evidence_ids as _bundle_evidence_ids
from .execution_recovery_events import (
    record_route_switch_reverification as _record_route_switch_reverification,
)
from .execution_recovery_events import recovery_trace_fields as _recovery_trace_fields
from .execution_recovery_events import (
    required_boolean_slot_state as _required_boolean_slot_state,
)
from .execution_results import guarded_result, verified_result
from .execution_route_switch_recovery import (
    switch_after_failed_retrieval,
    switch_after_failed_verification,
)
from .execution_verifier_rebind import rebind_existing_boolean_evidence
from .pipeline_stage_timings import PipelineStageTimings
from .query_planning import ensure_request_query_plan
from .retrieval_rounds import retrieve_for_verifier_recovery
from .route_budget import optional_stage_allowed
from .route_selection import ControllerDecision
from .typed_proposition_authority import TYPED_PROPOSITION_AUTHORITY_CONTRACT


def recover_after_failed_retrieval(
    request: Any,
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    workflow_plan: dict[str, Any],
    retrieve: RetrieveFn,
    timings: PipelineStageTimings,
) -> tuple[
    ControllerDecision,
    EvidenceBundle,
    RetrieveDecision,
    dict[str, Any],
    list[dict[str, Any]],
]:
    if retrieve_decision.status == "good":
        return decision, bundle, retrieve_decision, workflow_plan, []
    switched = timings.measure(
        "retry_seconds",
        switch_after_failed_retrieval,
        request,
        decision,
        retrieve_decision,
        bundle,
        retrieve,
    )
    if switched is None:
        return decision, bundle, retrieve_decision, workflow_plan, []
    recovered_decision, bundle, retrieve_decision, events = switched
    if recovered_decision.legacy_route != decision.legacy_route:
        workflow_plan = build_execution_workflow_plan(
            request,
            recovered_decision.legacy_route,
            recovered_decision.policy,
            recovered_decision.controller_mode,
            [],
        )
    return (
        recovered_decision,
        bundle,
        retrieve_decision,
        workflow_plan,
        events,
    )


def recover_after_failed_verification(
    request: Any,
    initial_result: RouteExecutionResult,
    retrieve: RetrieveFn,
    rewrite: RewriteFn | None,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
) -> RouteExecutionResult:
    _record_route_switch_reverification(initial_result)
    if not required_boolean_authority_missing(request, initial_result.verify_decision):
        _mark_resolved_initial_conflict(initial_result)
        return initial_result
    if not optional_stage_allowed(request):
        return initial_result
    candidate_answer = _raw_candidate(initial_result)
    policy = verifier_recovery_policy(
        request,
        initial_result.controller_decision,
        initial_result.evidence_bundle,
    )
    slot_state = _required_boolean_slot_state(initial_result.evidence_bundle)
    if slot_state == "retrieved_unverified" and policy != "crag_guarded":
        rebound, recovery_trace = _rebind_existing_verifier_recovery(
            request,
            initial_result,
            rewrite,
            candidate_answer,
            workflow_plan,
            trace_prefix,
            timings,
        )
        if not required_boolean_authority_missing(request, rebound.verify_decision):
            return rebound
        if policy == "controller_auto":
            recovery_trace[-1].pop("stop_reason", None)
            switched = _controller_verifier_recovery(
                request,
                rebound,
                retrieve,
                rewrite,
                candidate_answer,
                policy,
                [*trace_prefix, *recovery_trace],
                timings,
            )
            if switched is not None:
                return switched
            recovery_trace[-1]["stop_reason"] = "authority_recovery_exhausted"
            return rebound
        recovery_trace[-1].pop("stop_reason", None)
        return _same_route_verifier_recovery(
            request,
            rebound,
            retrieve,
            rewrite,
            candidate_answer,
            policy,
            workflow_plan,
            [*trace_prefix, *recovery_trace],
            timings,
        )
    return _same_route_verifier_recovery(
        request,
        initial_result,
        retrieve,
        rewrite,
        candidate_answer,
        policy,
        workflow_plan,
        trace_prefix,
        timings,
    )


def _rebind_existing_verifier_recovery(
    request: Any,
    initial_result: RouteExecutionResult,
    rewrite: RewriteFn | None,
    candidate_answer: str,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
) -> tuple[RouteExecutionResult, list[dict[str, Any]]]:
    before = _boolean_slot_states(initial_result.evidence_bundle)
    rebound_bundle = timings.measure(
        "retry_seconds",
        rebind_existing_boolean_evidence,
        request,
        initial_result.controller_decision.legacy_route,
        initial_result.evidence_bundle,
    )
    shared = _recovery_trace_fields(
        request,
        initial_result.verify_decision,
        initial_result.evidence_bundle,
        rebound_bundle,
    )
    rebind = {"stage": "evidence_rebind", "slot_states_before": before, **shared}
    reverify = {"stage": "reverify", "attempt": 1, **shared}
    recovery_trace = [rebind, reverify]
    result = complete_verifier_recovery(
        request,
        initial_result.controller_decision,
        initial_result.retrieve_decision,
        rebound_bundle,
        candidate_answer,
        rewrite,
        workflow_plan,
        [*trace_prefix, *recovery_trace],
        timings,
        terminal_event=reverify,
    )
    return result, recovery_trace


def _controller_verifier_recovery(
    request: Any,
    initial_result: RouteExecutionResult,
    retrieve: RetrieveFn,
    rewrite: RewriteFn | None,
    candidate_answer: str,
    policy: str,
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
) -> RouteExecutionResult | None:
    if policy != "controller_auto":
        return None
    switched = timings.measure(
        "retry_seconds",
        switch_after_failed_verification,
        request,
        initial_result.controller_decision,
        initial_result.verify_decision,
        initial_result.evidence_bundle,
        retrieve,
    )
    if switched is None:
        return None
    decision, bundle, retrieve_decision, event = switched
    workflow_plan = build_execution_workflow_plan(
        request,
        decision.legacy_route,
        decision.policy,
        decision.controller_mode,
        [],
    )
    return complete_verifier_recovery(
        request,
        decision,
        retrieve_decision,
        bundle,
        candidate_answer,
        rewrite,
        workflow_plan,
        [*trace_prefix, event],
        timings,
        terminal_event=event,
    )


def _same_route_verifier_recovery(
    request: Any,
    initial_result: RouteExecutionResult,
    retrieve: RetrieveFn,
    rewrite: RewriteFn | None,
    candidate_answer: str,
    policy: str,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
) -> RouteExecutionResult:
    recovered = timings.measure(
        "retry_seconds",
        retrieve_for_verifier_recovery,
        request,
        initial_result.controller_decision,
        retrieve,
        initial_result.evidence_bundle,
        evaluate=evaluate_retrieval_quality,
        retry_reason="required_boolean_authority_missing",
    )
    if recovered is None:
        return initial_result
    bundle, retrieve_decision, focused_query = recovered
    recovery_trace, terminal_event = same_route_verifier_recovery_trace(
        policy,
        initial_result.verify_decision,
        retrieve_decision,
        focused_query,
        request=request,
        initial_bundle=initial_result.evidence_bundle,
        recovered_bundle=bundle,
    )
    return complete_verifier_recovery(
        request,
        initial_result.controller_decision,
        retrieve_decision,
        bundle,
        candidate_answer,
        rewrite,
        workflow_plan,
        [*trace_prefix, *recovery_trace],
        timings,
        terminal_event=terminal_event,
    )


def complete_verifier_recovery(
    request: Any,
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    candidate_answer: str,
    rewrite: RewriteFn | None,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
    *,
    terminal_event: dict[str, Any],
) -> RouteExecutionResult:
    if retrieve_decision.status != "good":
        terminal_event.update(
            {
                "verification_status": "not_enough_evidence",
                "slot_states_after": _boolean_slot_states(bundle),
                "recovered_evidence_ids": _bundle_evidence_ids(bundle),
                "authority_state_after": str(
                    terminal_event.get("authority_state_before") or ""
                ),
                "authority_atoms_after": list(
                    terminal_event.get("authority_atoms_before") or []
                ),
                "authority_changed": False,
                "stop_reason": "authority_recovery_exhausted",
            }
        )
        return guarded_result(
            request,
            decision,
            retrieve_decision,
            bundle,
            workflow_plan,
            trace_prefix,
            timings,
        )
    result = verified_result(
        request,
        decision,
        retrieve_decision,
        bundle,
        candidate_answer,
        rewrite,
        workflow_plan,
        trace_prefix,
        timings,
    )
    _record_recovery_outcome(request, result, terminal_event)
    return result


def _record_recovery_outcome(
    request: Any,
    result: RouteExecutionResult,
    terminal_event: dict[str, Any],
) -> None:
    recovered = not required_boolean_authority_missing(request, result.verify_decision)
    conflict_resolved = (
        result.verify_decision.status == "verified_conflict"
        and authoritative_conflict_complete(
            result.verify_decision.authoritative_conflict
        )
    )
    authority_state_after, authority_atoms_after = _authority_state(
        result.verify_decision
    )
    authority_state_before = str(terminal_event.get("authority_state_before") or "")
    authority_atoms_before = list(terminal_event.get("authority_atoms_before") or [])
    terminal_event.update(
        {
            "verification_status": result.verify_decision.status,
            "slot_states_after": _boolean_slot_states(result.evidence_bundle),
            "recovered_evidence_ids": _bundle_evidence_ids(result.evidence_bundle),
            "authority_state_after": authority_state_after,
            "authority_atoms_after": authority_atoms_after,
            "authority_changed": (
                authority_state_before != authority_state_after
                or authority_atoms_before != authority_atoms_after
            ),
            "stop_reason": (
                "authority_conflict_resolved"
                if conflict_resolved
                else (
                    "authority_recovered"
                    if recovered
                    else "authority_recovery_exhausted"
                )
            ),
        }
    )


def same_route_verifier_recovery_trace(
    policy: str,
    verify_decision: VerifyDecision,
    retrieve_decision: RetrieveDecision,
    focused_query: str,
    *,
    request: Any | None = None,
    initial_bundle: EvidenceBundle | None = None,
    recovered_bundle: EvidenceBundle | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    shared = _recovery_trace_fields(
        request,
        verify_decision,
        initial_bundle,
        recovered_bundle,
    )
    retrieval_round = int(
        (recovered_bundle.metadata if recovered_bundle else {}).get(
            "verifier_recovery_round"
        )
        or 2
    )
    if policy != "crag_guarded":
        focused_retrieval = {
            "stage": "focused_retrieval",
            "retrieval_round": retrieval_round,
            "focused_query": focused_query,
            "status": retrieve_decision.status,
            **shared,
        }
        rebind = {
            "stage": "evidence_rebind",
            "retrieval_round": retrieval_round,
            "status": retrieve_decision.status,
            **shared,
        }
        reverify = {"stage": "reverify", "attempt": 1, **shared}
        return [focused_retrieval, rebind, reverify], reverify
    critic = {
        "stage": "critic",
        "status": verify_decision.status,
        "reason": verify_decision.reason,
        **shared,
    }
    focused_retrieval = {
        "stage": "focused_retrieval",
        "retrieval_round": retrieval_round,
        "focused_query": focused_query,
        "status": retrieve_decision.status,
        **shared,
    }
    rebind = {
        "stage": "evidence_rebind",
        "retrieval_round": retrieval_round,
        "status": retrieve_decision.status,
        **shared,
    }
    reverify = {"stage": "reverify", "attempt": 1, **shared}
    return [critic, focused_retrieval, rebind, reverify], reverify


def verifier_recovery_policy(
    request: Any,
    decision: ControllerDecision,
    bundle: EvidenceBundle | None = None,
) -> str:
    if str(getattr(request, "agent_mode", "") or "").strip().lower() == "thorough":
        return "crag_guarded"
    if decision.policy == "auto" and not decision.route_switch_used:
        return "controller_auto"
    return "text_rag"


def required_boolean_authority_missing(
    request: Any,
    verify_decision: VerifyDecision,
) -> bool:
    if verify_decision.mode == "off" or verify_decision.status == "not_requested":
        return False
    plan = ensure_request_query_plan(request)
    typed_required = plan.answer_type == "boolean" or any(
        slot.required_for_verification
        and str(slot.statement_kind or "").lower()
        in {"answer_relation", "boolean_proposition"}
        for slot in plan.evidence_slots
    )
    if not typed_required:
        return False
    typed = verify_decision.typed_authority
    if typed.get("contract_id") == TYPED_PROPOSITION_AUTHORITY_CONTRACT:
        state = str(typed.get("state") or "")
        required = {
            str(value).strip()
            for value in typed.get("required_slot_ids") or []
            if str(value).strip()
        }
        verified = {
            str(value).strip()
            for value in typed.get("verified_slot_ids") or []
            if str(value).strip()
        }
        atoms = [
            atom
            for atom in typed.get("authority_atoms") or []
            if isinstance(atom, dict)
        ]
        if state == "verified_conflict":
            return not authoritative_conflict_complete(
                verify_decision.authoritative_conflict
            )
        return not (
            verify_decision.status == "supported"
            and state == "verified_support"
            and required
            and required == verified
            and atoms
            and all(
                str(atom.get("evidence_id") or "")
                and str(atom.get("evidence_ref") or "")
                and str(atom.get("quote") or "")
                for atom in atoms
            )
        )
    if verify_decision.status == "verified_conflict":
        return not authoritative_conflict_complete(
            verify_decision.authoritative_conflict
        )
    return not (
        verify_decision.status == "supported"
        and verify_decision.canonical_answer_polarity in {"yes", "no"}
        and bool(verify_decision.authoritative_evidence_id)
        and bool(verify_decision.authoritative_evidence_ref)
        and bool(verify_decision.authoritative_quote)
    )


def _mark_resolved_initial_conflict(result: RouteExecutionResult) -> None:
    decision = result.verify_decision
    if decision.status != "verified_conflict" or not authoritative_conflict_complete(
        decision.authoritative_conflict
    ):
        return
    for event in reversed(result.controller_trace):
        if event.get("stage") == "verifier":
            event["stop_reason"] = "authority_conflict_resolved"
            break


def _raw_candidate(result: RouteExecutionResult) -> str:
    raw_answer = result.engine_terminal_state.get("raw_generated_answer")
    return str(result.answer if raw_answer is None else raw_answer)
