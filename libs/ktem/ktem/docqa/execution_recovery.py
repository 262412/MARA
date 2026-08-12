from __future__ import annotations

from typing import Any

from .controller import (
    RetrieveDecision,
    RouteDecision,
    VerifyDecision,
    evaluate_retrieval_quality,
)
from .evidence import EvidenceBundle
from .execution_models import RetrieveFn, RewriteFn, RouteExecutionResult
from .execution_planning import build_execution_workflow_plan, controller_decision
from .execution_results import guarded_result, verified_result
from .execution_retrieval import retrieve_and_evaluate
from .pipeline_stage_timings import PipelineStageTimings
from .query_planning import ensure_request_query_plan
from .retrieval_rounds import retrieve_for_verifier_recovery
from .route_budget import optional_stage_allowed, route_budget_metadata
from .route_capabilities import route_switch_candidate_evaluation
from .route_selection import ControllerDecision, mark_route_switch_recovery


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
    decision, bundle, retrieve_decision, event = switched
    workflow_plan = build_execution_workflow_plan(
        request,
        decision.legacy_route,
        decision.policy,
        decision.controller_mode,
        [],
    )
    return decision, bundle, retrieve_decision, workflow_plan, [event]


def recover_after_failed_verification(
    request: Any,
    initial_result: RouteExecutionResult,
    retrieve: RetrieveFn,
    rewrite: RewriteFn | None,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
) -> RouteExecutionResult:
    if not required_boolean_authority_missing(request, initial_result.verify_decision):
        return initial_result
    if not optional_stage_allowed(request):
        return initial_result
    candidate_answer = _raw_candidate(initial_result)
    policy = verifier_recovery_policy(request, initial_result.controller_decision)
    switched = _controller_verifier_recovery(
        request,
        initial_result,
        retrieve,
        rewrite,
        candidate_answer,
        policy,
        trace_prefix,
        timings,
    )
    if switched is not None:
        return switched
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
    recovered = not required_boolean_authority_missing(request, result.verify_decision)
    terminal_event.update(
        {
            "verification_status": result.verify_decision.status,
            "stop_reason": (
                "authority_recovered" if recovered else "authority_recovery_exhausted"
            ),
        }
    )
    return result


def same_route_verifier_recovery_trace(
    policy: str,
    verify_decision: VerifyDecision,
    retrieve_decision: RetrieveDecision,
    focused_query: str,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    shared = {
        "verifier_recovery_attempt": 1,
        "retry_reason": "required_boolean_authority_missing",
    }
    if policy != "crag_guarded":
        event = {
            "stage": "verifier_recovery",
            "attempt": 1,
            "retrieval_round": 2,
            "focused_query": focused_query,
            **shared,
        }
        return [event], event
    critic = {
        "stage": "critic",
        "status": verify_decision.status,
        "reason": verify_decision.reason,
        **shared,
    }
    focused_retrieval = {
        "stage": "focused_retrieval",
        "retrieval_round": 2,
        "focused_query": focused_query,
        "status": retrieve_decision.status,
        **shared,
    }
    rebind = {
        "stage": "evidence_rebind",
        "retrieval_round": 2,
        "status": retrieve_decision.status,
        **shared,
    }
    reverify = {"stage": "reverify", "attempt": 1, **shared}
    return [critic, focused_retrieval, rebind, reverify], reverify


def verifier_recovery_policy(
    request: Any,
    decision: ControllerDecision,
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
    plan = ensure_request_query_plan(request)
    boolean_required = plan.answer_type == "boolean" or any(
        slot.required_for_verification
        and str(slot.statement_kind or "").lower() == "boolean_proposition"
        for slot in plan.evidence_slots
    )
    if not boolean_required:
        return False
    return not (
        verify_decision.status == "supported"
        and verify_decision.canonical_answer_polarity in {"yes", "no"}
        and bool(verify_decision.authoritative_evidence_id)
        and bool(verify_decision.authoritative_evidence_ref)
        and bool(verify_decision.authoritative_quote)
    )


def switch_after_failed_verification(
    request: Any,
    decision: ControllerDecision,
    failed_verification: VerifyDecision,
    failed_bundle: EvidenceBundle,
    retrieve: RetrieveFn,
) -> tuple[ControllerDecision, EvidenceBundle, RetrieveDecision, dict[str, Any]] | None:
    candidates, rejected_candidates = route_switch_candidate_evaluation(
        request,
        decision.legacy_route,
    )
    if not candidates:
        if rejected_candidates:
            failed_bundle.metadata["rejected_route_switch_candidates"] = list(
                rejected_candidates
            )
        return None
    route = candidates[0]
    switched_decision = _verifier_switch_decision(decision, route, candidates)
    recovered = retrieve_for_verifier_recovery(
        request,
        switched_decision,
        retrieve,
        failed_bundle,
        evaluate=evaluate_retrieval_quality,
        retry_reason="required_boolean_authority_missing",
    )
    if recovered is None:
        return None
    bundle, retrieve_decision, focused_query = recovered
    event = _verifier_switch_event(
        decision,
        route,
        candidates,
        focused_query,
        failed_verification,
        rejected_candidates,
    )
    return switched_decision, bundle, retrieve_decision, event


def _verifier_switch_decision(
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
) -> ControllerDecision:
    switched = controller_decision(
        RouteDecision(
            route=route,
            policy="route_switch",
            controller_mode=decision.controller_mode,
            requires_retrieval=True,
            reason=(
                f"Switched from {decision.legacy_route} after required Boolean "
                "authority was not established."
            ),
        )
    )
    return mark_route_switch_recovery(
        switched,
        initial_decision=decision,
        candidates=candidates,
        override_reason="Route switch used after required Boolean authority failure.",
    )


def _verifier_switch_event(
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
    focused_query: str,
    failed_verification: VerifyDecision,
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
        "failed_verifier_status": failed_verification.status,
        "failed_verifier_reason": failed_verification.reason,
    }
    if rejected_candidates:
        event["rejected_route_switch_candidates"] = list(rejected_candidates)
    return event


def switch_after_failed_retrieval(
    request: Any,
    decision: ControllerDecision,
    failed_decision: RetrieveDecision,
    failed_bundle: EvidenceBundle,
    retrieve: RetrieveFn,
) -> tuple[ControllerDecision, EvidenceBundle, RetrieveDecision, dict[str, Any]] | None:
    if not optional_stage_allowed(request):
        failed_bundle.metadata.update(route_budget_metadata(request))
        failed_bundle.metadata[
            "route_switch_skipped_reason"
        ] = "insufficient_remaining_time"
        return None
    candidates, rejected_candidates = route_switch_candidate_evaluation(
        request,
        decision.legacy_route,
    )
    if rejected_candidates:
        failed_bundle.metadata["rejected_route_switch_candidates"] = list(
            rejected_candidates
        )
    for route in candidates:
        switched = _retrieval_switch_decision(decision, route, candidates)
        bundle, retrieve_decision = retrieve_and_evaluate(
            request,
            switched,
            retrieve,
            max_rounds=1,
        )
        event = _retrieval_switch_event(
            decision,
            route,
            candidates,
            failed_decision,
            failed_bundle,
            rejected_candidates,
        )
        if retrieve_decision.status == "good":
            return switched, bundle, retrieve_decision, event
    return None


def _retrieval_switch_decision(
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
) -> ControllerDecision:
    switched = controller_decision(
        RouteDecision(
            route=route,
            policy="route_switch",
            controller_mode=decision.controller_mode,
            requires_retrieval=True,
            reason=(f"Switched from {decision.legacy_route} after failed retrieval."),
        )
    )
    return mark_route_switch_recovery(
        switched,
        initial_decision=decision,
        candidates=candidates,
    )


def _retrieval_switch_event(
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
    failed_decision: RetrieveDecision,
    failed_bundle: EvidenceBundle,
    rejected_candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    event = {
        "stage": "route_switch",
        "from_route": decision.legacy_route,
        "to_route": route,
        "reason": failed_decision.reason,
        "route_switch_used": True,
        "route_switch_candidates": list(candidates),
        "failed_retrieval_rounds": int(
            failed_bundle.metadata.get("retrieval_rounds") or 1
        ),
        "failed_slot_coverage": failed_bundle.metadata.get("slot_coverage"),
        "failed_missing_required_slot_count": failed_bundle.metadata.get(
            "missing_required_slot_count"
        ),
    }
    if rejected_candidates:
        event["rejected_route_switch_candidates"] = list(rejected_candidates)
    return event


def _raw_candidate(result: RouteExecutionResult) -> str:
    raw_answer = result.engine_terminal_state.get("raw_generated_answer")
    return str(result.answer if raw_answer is None else raw_answer)
