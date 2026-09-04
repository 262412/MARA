from __future__ import annotations

from dataclasses import replace
from typing import Any

from .controller import RetrieveDecision, evaluate_retrieval_quality
from .evidence import EvidenceBundle
from .execution_authority_policy import required_typed_authority_missing
from .execution_models import (
    GenerateFn,
    RetrieveFn,
    RewriteFn,
    RouteExecutionResult,
    VerifyFn,
)
from .execution_planning import build_execution_workflow_plan
from .execution_qasper_candidate_recovery import (
    regenerate_qasper_candidate as _regenerate_qasper_candidate,
)
from .execution_recovery_completion import complete_verifier_recovery
from .execution_recovery_events import (
    copy_reverification_outcome as _copy_reverification_outcome,
)
from .execution_recovery_events import (
    mark_recovery_no_progress as _mark_recovery_no_progress,
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
    *,
    generate: GenerateFn | None = None,
) -> RouteExecutionResult:
    if initial_result.verify_decision.status == "execution_failed":
        return initial_result
    return _recover_after_failed_verification(
        request,
        initial_result,
        retrieve,
        rewrite,
        workflow_plan,
        trace_prefix,
        timings,
        verify,
        generate=generate,
    )


def _recover_after_failed_verification(
    request: Any,
    initial_result: RouteExecutionResult,
    retrieve: RetrieveFn,
    rewrite: RewriteFn | None,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
    verify: VerifyFn,
    *,
    generate: GenerateFn | None = None,
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
        return _recover_retrieved_unverified(
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
            generate=generate,
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
        generate=generate,
    )


def _recover_retrieved_unverified(
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
    *,
    generate: GenerateFn | None,
) -> RouteExecutionResult:
    rebound, recovery_trace = _rebind_existing_verifier_recovery(
        request,
        initial_result,
        rewrite,
        candidate_answer,
        workflow_plan,
        trace_prefix,
        timings,
        verify,
        generate=generate,
    )
    if not required_typed_authority_missing(request, rebound.verify_decision):
        return rebound
    terminal_event = recovery_trace[-1]
    terminal_event.pop("stop_reason", None)
    terminal_event["recovery_action"] = "rebind_existing_evidence"
    prefixed_trace = [*trace_prefix, *recovery_trace]
    if policy == "controller_auto":
        switched = _controller_verifier_recovery(
            request,
            rebound,
            retrieve,
            rewrite,
            candidate_answer,
            policy,
            prefixed_trace,
            timings,
            verify,
            generate=generate,
        )
        if switched is not None:
            return switched
        _mark_recovery_no_progress(terminal_event)
        return rebound
    return _same_route_verifier_recovery(
        request,
        rebound,
        retrieve,
        rewrite,
        candidate_answer,
        policy,
        workflow_plan,
        prefixed_trace,
        timings,
        verify,
        generate=generate,
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
    *,
    generate: GenerateFn | None,
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
        _mark_recovery_no_progress(rebind)
        return replace(
            initial_result,
            controller_trace=[*initial_result.controller_trace, rebind],
        ), [rebind]
    reverify = {"stage": "reverify", "attempt": 1, **shared}
    recovery_trace = [rebind, reverify]
    rebound_bundle, candidate_answer, stopped = _regenerate_qasper_candidate(
        request,
        initial_result,
        initial_result.controller_decision,
        initial_result.retrieve_decision,
        rebound_bundle,
        candidate_answer,
        generate,
        recovery_trace,
        reverify,
        timings,
    )
    if stopped is not None:
        return stopped, recovery_trace
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
    *,
    generate: GenerateFn | None,
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
        _mark_recovery_no_progress(event)
        event["authority_changed"] = False
        return replace(
            initial_result,
            controller_trace=[*initial_result.controller_trace, event],
        )
    return _complete_controller_verifier_recovery(
        request,
        initial_result,
        rewrite,
        candidate_answer,
        trace_prefix,
        timings,
        verify,
        generate,
        decision,
        bundle,
        retrieve_decision,
        event,
        shared,
    )


def _complete_controller_verifier_recovery(
    request: Any,
    initial_result: RouteExecutionResult,
    rewrite: RewriteFn | None,
    candidate_answer: str,
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
    verify: VerifyFn,
    generate: GenerateFn | None,
    decision: ControllerDecision,
    bundle: EvidenceBundle,
    retrieve_decision: RetrieveDecision,
    event: dict[str, Any],
    shared: dict[str, Any],
) -> RouteExecutionResult:
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
    bundle, candidate_answer, stopped = _regenerate_qasper_candidate(
        request,
        initial_result,
        decision,
        retrieve_decision,
        bundle,
        candidate_answer,
        generate,
        [event, reverify],
        reverify,
        timings,
    )
    if stopped is not None:
        return stopped
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
    *,
    generate: GenerateFn | None,
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
        _mark_last_rebind_no_progress(initial_result)
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
        return _same_route_no_progress_result(
            initial_result,
            recovery_trace,
            terminal_event,
        )
    bundle, candidate_answer, stopped = _regenerate_qasper_candidate(
        request,
        initial_result,
        initial_result.controller_decision,
        retrieve_decision,
        bundle,
        candidate_answer,
        generate,
        recovery_trace,
        terminal_event,
        timings,
    )
    if stopped is not None:
        return stopped
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


def _mark_last_rebind_no_progress(initial_result: RouteExecutionResult) -> None:
    if not initial_result.controller_trace:
        return
    last_event = initial_result.controller_trace[-1]
    if (
        last_event.get("stage") == "evidence_rebind"
        and last_event.get("verifier_recovery_attempt") == 1
        and not _recovery_has_progress(last_event)
    ):
        _mark_recovery_no_progress(last_event)


def _same_route_no_progress_result(
    initial_result: RouteExecutionResult,
    recovery_trace: list[dict[str, Any]],
    terminal_event: dict[str, Any],
) -> RouteExecutionResult:
    _mark_recovery_no_progress(terminal_event)
    terminal_event["authority_changed"] = False
    trace_without_reverify = [
        event for event in recovery_trace if event.get("stage") != "reverify"
    ]
    _mark_recovery_no_progress(trace_without_reverify[-1])
    trace_without_reverify[-1]["authority_changed"] = False
    return replace(
        initial_result,
        controller_trace=[
            *initial_result.controller_trace,
            *trace_without_reverify,
        ],
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
