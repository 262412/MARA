from __future__ import annotations

from dataclasses import replace
from typing import Any

from .boolean_authoritative_conflict import authoritative_conflict_complete
from .controller import RetrieveDecision, evaluate_retrieval_quality
from .evidence import EvidenceBundle
from .execution_models import RetrieveFn, RewriteFn, RouteExecutionResult, VerifyFn
from .execution_planning import build_execution_workflow_plan
from .execution_recovery_events import authority_state as _authority_state
from .execution_recovery_events import bundle_evidence_ids as _bundle_evidence_ids
from .execution_recovery_events import (
    copy_reverification_outcome as _copy_reverification_outcome,
)
from .execution_recovery_events import (
    mark_resolved_initial_conflict as _mark_resolved_initial_conflict,
)
from .execution_recovery_events import raw_candidate as _raw_candidate
from .execution_recovery_events import (
    record_route_switch_reverification as _record_route_switch_reverification,
)
from .execution_recovery_events import recovery_has_progress as _recovery_has_progress
from .execution_recovery_events import recovery_trace_fields as _recovery_trace_fields
from .execution_recovery_events import required_authority_recovery_reason
from .execution_recovery_events import required_typed_slot_state as _typed_slot_state
from .execution_recovery_events import (
    retrieval_no_progress_decision as _retrieval_no_progress_decision,
)
from .execution_recovery_events import same_route_verifier_recovery_trace
from .execution_recovery_events import typed_slot_states as _typed_slot_states
from .execution_authority_policy import required_typed_authority_missing
from .execution_results import guarded_result, verified_result
from .execution_route_switch_recovery import (
    switch_after_failed_retrieval,
    switch_after_failed_verification,
)
from .execution_verifier_rebind import rebind_existing_boolean_evidence
from .pipeline_stage_timings import PipelineStageTimings
from .retrieval_rounds import retrieve_for_verifier_recovery
from .route_budget import optional_stage_allowed, route_budget_metadata
from .route_selection import ControllerDecision
from .typed_retrieval_recovery import verifier_recovery_frame


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
    recovery_trace = _typed_retrieval_recovery_trace(bundle)
    if retrieve_decision.status == "good":
        return decision, bundle, retrieve_decision, workflow_plan, recovery_trace
    no_progress = _retrieval_no_progress_decision(recovery_trace, retrieve_decision)
    if no_progress is not None:
        return decision, bundle, no_progress, workflow_plan, recovery_trace
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
        events = list(recovery_trace)
        stop_reason = str(bundle.metadata.get("retrieval_stop_reason") or "")
        if retrieve_decision.status == "poor" and not retrieve_decision.retry:
            events.append(
                {
                    "stage": "retrieval_recovery",
                    "recovery_action": "stop_without_generation",
                    "stop_reason": stop_reason or "retrieval_unrecoverable",
                    "missing_required_slot_ids": list(
                        bundle.metadata.get("missing_required_slot_ids") or []
                    ),
                    "retrieval_rounds": int(
                        bundle.metadata.get("retrieval_rounds") or 1
                    ),
                }
            )
        return decision, bundle, retrieve_decision, workflow_plan, events
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
        [*recovery_trace, *events],
    )


def recover_after_failed_verification(
    request: Any,
    initial_result: RouteExecutionResult,
    retrieve: RetrieveFn,
    rewrite: RewriteFn | None,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
    verify: VerifyFn,
) -> RouteExecutionResult:
    _record_route_switch_reverification(initial_result)
    if not required_typed_authority_missing(request, initial_result.verify_decision):
        _mark_resolved_initial_conflict(initial_result)
        return initial_result
    if not optional_stage_allowed(request):
        return _skip_optional_verifier_recovery(request, initial_result)
    candidate_answer = _raw_candidate(initial_result)
    policy = verifier_recovery_policy(
        request,
        initial_result.controller_decision,
        initial_result.evidence_bundle,
    )
    slot_state = _typed_slot_state(initial_result.evidence_bundle)
    if slot_state == "retrieved_unverified" and policy != "crag_guarded":
        rebound, recovery_trace = _rebind_existing_verifier_recovery(
            request,
            initial_result,
            rewrite,
            candidate_answer,
            workflow_plan,
            trace_prefix,
            timings,
            verify,
        )
        if not required_typed_authority_missing(request, rebound.verify_decision):
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
                verify,
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
            verify,
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
        verify,
    )


def _rebind_existing_verifier_recovery(
    request: Any,
    initial_result: RouteExecutionResult,
    rewrite: RewriteFn | None,
    candidate_answer: str,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
    verify: VerifyFn,
) -> tuple[RouteExecutionResult, list[dict[str, Any]]]:
    before = _typed_slot_states(initial_result.evidence_bundle)
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
        candidate_answer=candidate_answer,
    )
    rebind = {
        "stage": "evidence_rebind",
        "slot_states_before": before,
        "recovery_action": "rebind_existing_evidence",
        **shared,
    }
    if not _recovery_has_progress(shared):
        return replace(
            initial_result,
            controller_trace=[*initial_result.controller_trace, rebind],
        ), [rebind]
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
        verify,
        terminal_event=reverify,
    )
    return result, recovery_trace


def _skip_optional_verifier_recovery(
    request: Any,
    initial_result: RouteExecutionResult,
) -> RouteExecutionResult:
    event = {
        "stage": "verifier_recovery",
        "recovery_action": "skip_optional_recovery",
        "failure_type": required_authority_recovery_reason(request),
        "stop_reason": "insufficient_remaining_time",
        **route_budget_metadata(request),
    }
    return replace(
        initial_result,
        controller_trace=[*initial_result.controller_trace, event],
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
    verify: VerifyFn,
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
    shared = _recovery_trace_fields(
        request,
        initial_result.verify_decision,
        initial_result.evidence_bundle,
        bundle,
        candidate_answer=candidate_answer,
    )
    event.update(shared)
    event["recovery_frame"] = verifier_recovery_frame(request)
    event["recovery_action"] = "targeted_route_switch"
    if not _recovery_has_progress(shared):
        event.update(
            {
                "authority_changed": False,
                "recovery_action": "stop_without_reverify",
                "stop_reason": "recovery_no_progress",
            }
        )
        return replace(
            initial_result,
            controller_trace=[*initial_result.controller_trace, event],
        )
    workflow_plan = build_execution_workflow_plan(
        request,
        decision.legacy_route,
        decision.policy,
        decision.controller_mode,
        [],
    )
    reverify = {
        "stage": "reverify",
        "attempt": 1,
        "recovery_action": "fresh_reverification",
        **shared,
    }
    result = complete_verifier_recovery(
        request,
        decision,
        retrieve_decision,
        bundle,
        candidate_answer,
        rewrite,
        workflow_plan,
        [*trace_prefix, event, reverify],
        timings,
        verify,
        terminal_event=reverify,
    )
    _copy_reverification_outcome(event, reverify)
    return result


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
    verify: VerifyFn,
) -> RouteExecutionResult:
    recovered = timings.measure(
        "retry_seconds",
        retrieve_for_verifier_recovery,
        request,
        initial_result.controller_decision,
        retrieve,
        initial_result.evidence_bundle,
        evaluate=evaluate_retrieval_quality,
        retry_reason=required_authority_recovery_reason(request),
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
        candidate_answer=candidate_answer,
    )
    if not _recovery_has_progress(terminal_event):
        stop_fields = {
            "authority_changed": False,
            "recovery_action": "stop_without_reverify",
            "stop_reason": "recovery_no_progress",
        }
        terminal_event.update(stop_fields)
        recovery_trace = [
            event for event in recovery_trace if event.get("stage") != "reverify"
        ]
        recovery_trace[-1].update(
            {
                **stop_fields,
            }
        )
        return replace(
            initial_result,
            controller_trace=[
                *initial_result.controller_trace,
                *recovery_trace,
            ],
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
        verify,
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
    verify: VerifyFn,
    *,
    terminal_event: dict[str, Any],
) -> RouteExecutionResult:
    if retrieve_decision.status != "good":
        terminal_event.update(
            {
                "verification_status": "not_enough_evidence",
                "slot_states_after": _typed_slot_states(bundle),
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
            verify=verify,
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
        verify=verify,
    )
    _record_recovery_outcome(request, result, terminal_event)
    return result


def _record_recovery_outcome(
    request: Any,
    result: RouteExecutionResult,
    terminal_event: dict[str, Any],
) -> None:
    recovered = not required_typed_authority_missing(request, result.verify_decision)
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
    candidate_before = str(terminal_event.get("candidate_answer_before") or "")
    candidate_after = str(result.answer or "")
    terminal_event.update(
        {
            "verification_status": result.verify_decision.status,
            "slot_states_after": _typed_slot_states(result.evidence_bundle),
            "recovered_evidence_ids": _bundle_evidence_ids(result.evidence_bundle),
            "authority_state_after": authority_state_after,
            "authority_atoms_after": authority_atoms_after,
            "authority_changed": (
                authority_state_before != authority_state_after
                or authority_atoms_before != authority_atoms_after
            ),
            "candidate_answer_after": candidate_after,
            "candidate_changed": candidate_before.strip() != candidate_after.strip(),
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


def _typed_retrieval_recovery_trace(bundle: EvidenceBundle) -> list[dict[str, Any]]:
    event = bundle.metadata.get("typed_retrieval_recovery_trace")
    return [dict(event)] if isinstance(event, dict) else []
