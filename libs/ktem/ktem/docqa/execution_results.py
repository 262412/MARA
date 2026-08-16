from __future__ import annotations

from copy import deepcopy
from typing import Any

from .controller import RetrieveDecision, _verify_decision, evaluate_retrieval_quality
from .engine_terminal_projection import engine_terminal_projection
from .evidence import EvidenceBundle, build_evidence_bundle
from .execution_contracts import ABSTAIN_MESSAGE, RAGTRUTH_EMPTY_ANSWER
from .execution_models import GuardrailDecision, RewriteFn, RouteExecutionResult
from .execution_trace import execution_trace
from .execution_verification import ragtruth_contract_request, verify_generated_answer
from .pipeline_stage_timings import PipelineStageTimings
from .route_budget import (
    RouteDeadlineExhausted,
    deadline_trace_event,
    route_budget_metadata,
    route_budget_trace,
)
from .route_selection import ControllerDecision
from .verification import VerifyDecision, with_verification_evidence


def static_result(
    request: Any,
    decision: ControllerDecision,
    answer: str,
    workflow_plan: dict[str, Any],
    stage_timings: PipelineStageTimings,
) -> RouteExecutionResult:
    bundle = build_evidence_bundle(decision.legacy_route, request, {})
    retrieve_decision = evaluate_retrieval_quality(decision.legacy_route, {})
    verify_decision = _verify_decision(request, retrieve_decision, bundle, answer)
    return result(
        request,
        decision,
        retrieve_decision,
        verify_decision,
        GuardrailDecision("ok", "return", decision.reason),
        bundle,
        workflow_plan,
        answer,
        stage_timings=stage_timings,
    )


def guarded_result(
    request: Any,
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]] | None = None,
    stage_timings: PipelineStageTimings | None = None,
) -> RouteExecutionResult:
    if ragtruth_contract_request(request):
        bundle.metadata["task_contract_fallback"] = "ragtruth_empty_retrieval"
        verify_decision = VerifyDecision(
            mode="off",
            status="not_required",
            reason="RAGTruth task contract handled empty retrieval.",
        )
        return result(
            request,
            decision,
            retrieve_decision,
            verify_decision,
            GuardrailDecision("ok", "return", verify_decision.reason),
            bundle,
            workflow_plan,
            RAGTRUTH_EMPTY_ANSWER,
            trace_prefix,
            stage_timings,
        )
    verify_decision = _verify_decision(request, retrieve_decision, bundle, "")
    guardrail = GuardrailDecision(
        status="not_enough_evidence",
        action="abstain",
        reason=retrieve_decision.reason,
    )
    return result(
        request,
        decision,
        retrieve_decision,
        verify_decision,
        guardrail,
        bundle,
        workflow_plan,
        ABSTAIN_MESSAGE,
        trace_prefix,
        stage_timings,
    )


def deadline_exhausted_result(
    request: Any,
    decision: ControllerDecision,
    workflow_plan: dict[str, Any],
    error: RouteDeadlineExhausted,
    stage_timings: PipelineStageTimings,
) -> RouteExecutionResult:
    bundle = getattr(request, "route_last_evidence_bundle", None)
    if not isinstance(bundle, EvidenceBundle):
        bundle = EvidenceBundle(route=decision.legacy_route, items=[], metadata={})
    metadata = dict(bundle.metadata)
    metadata.update(route_budget_metadata(request))
    metadata["route_deadline"] = deadline_trace_event(request, error)
    bundle = EvidenceBundle(
        route=bundle.route,
        items=list(bundle.items),
        metadata=metadata,
    )
    retrieve_decision = RetrieveDecision(
        status="poor",
        reason="route_deadline_exhausted",
        retry=False,
    )
    verify_decision = VerifyDecision(
        mode=str(getattr(request, "verification_mode", "") or "off"),
        status="not_enough_evidence",
        reason="route_deadline_exhausted",
        action="abstain",
        typed_authority={
            "state": "missing",
            "reason": "route_deadline_exhausted",
            "authority_atoms": [],
            "required_slot_ids": [],
            "verified_slot_ids": [],
            "slot_bindings": {},
        },
    )
    guardrail = GuardrailDecision(
        status="not_enough_evidence",
        action="abstain",
        reason="route_deadline_exhausted",
    )
    trace = [deadline_trace_event(request, error)]
    return result(
        request,
        decision,
        retrieve_decision,
        verify_decision,
        guardrail,
        bundle,
        workflow_plan,
        ABSTAIN_MESSAGE,
        trace,
        stage_timings,
        terminal_outcome="timeout",
        terminal_outcome_reason="route_deadline_exhausted",
    )


def operational_failure_result(
    request: Any,
    decision: ControllerDecision | None,
    workflow_plan: dict[str, Any],
    error: Exception,
    failure_stage: str,
    stage_timings: PipelineStageTimings,
) -> RouteExecutionResult:
    reason = f"{failure_stage}_failed"
    decision = decision or ControllerDecision(
        route="abstain",
        legacy_route="abstain",
        policy="operational_failure",
        controller_mode="runtime",
        requires_retrieval=False,
        reason=reason,
    )
    bundle = getattr(request, "route_last_evidence_bundle", None)
    if not isinstance(bundle, EvidenceBundle):
        bundle = EvidenceBundle(route=decision.legacy_route, items=[], metadata={})
    retrieve_decision = RetrieveDecision(status="error", reason=reason, retry=False)
    verify_decision = VerifyDecision(
        mode=str(getattr(request, "verification_mode", "") or "off"),
        status="execution_failed",
        reason=reason,
        action="error",
    )
    guardrail = GuardrailDecision(
        status="execution_failed",
        action="error",
        reason=reason,
    )
    trace = [
        {
            "stage": "terminal_outcome",
            "outcome": "execution_failed",
            "reason": reason,
            "error_type": type(error).__name__,
        }
    ]
    return result(
        request,
        decision,
        retrieve_decision,
        verify_decision,
        guardrail,
        bundle,
        workflow_plan,
        ABSTAIN_MESSAGE,
        trace,
        stage_timings,
        terminal_outcome="execution_failed",
        terminal_outcome_reason=reason,
    )


def verified_result(
    request: Any,
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    answer: str,
    rewrite: RewriteFn | None,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]] | None = None,
    stage_timings: PipelineStageTimings | None = None,
) -> RouteExecutionResult:
    stage_timings = stage_timings or PipelineStageTimings()
    raw_generated_answer = str(answer or "")
    answer, verify_decision, guardrail, trace = verify_generated_answer(
        request,
        decision,
        retrieve_decision,
        bundle,
        answer,
        rewrite,
        trace_prefix,
        stage_timings,
        verify=_verify_decision,
        guardrail_factory=GuardrailDecision,
        abstain_message=ABSTAIN_MESSAGE,
        ragtruth_empty_answer=RAGTRUTH_EMPTY_ANSWER,
    )
    return result(
        request,
        decision,
        retrieve_decision,
        verify_decision,
        guardrail,
        bundle,
        workflow_plan,
        answer,
        trace,
        stage_timings,
        raw_generated_answer=raw_generated_answer,
    )


def result(
    request: Any,
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    verify_decision: VerifyDecision,
    guardrail_decision: GuardrailDecision,
    bundle: EvidenceBundle,
    workflow_plan: dict[str, Any],
    answer: str,
    trace_prefix: list[dict[str, Any]] | None = None,
    stage_timings: PipelineStageTimings | None = None,
    *,
    raw_generated_answer: str | None = None,
    terminal_outcome: str | None = None,
    terminal_outcome_reason: str = "",
) -> RouteExecutionResult:
    trace_prefix = [*route_budget_trace(request), *list(trace_prefix or [])]
    bundle = with_verification_evidence(bundle, verify_decision, request)
    (stage_timings or PipelineStageTimings()).record(bundle)
    (
        terminal_answer,
        terminal_state,
        terminal_verify,
        terminal_guardrail,
        terminal_evidence,
        projection_hash,
    ) = engine_terminal_projection(
        answer,
        verify_decision,
        guardrail_decision,
        bundle,
        raw_generated_answer=raw_generated_answer,
        terminal_outcome=terminal_outcome,
        terminal_outcome_reason=terminal_outcome_reason,
    )
    prefix, suffix = _partition_trace(trace_prefix)
    return RouteExecutionResult(
        controller_decision=decision,
        retrieve_decision=retrieve_decision,
        verify_decision=verify_decision,
        guardrail_decision=guardrail_decision,
        evidence_bundle=bundle,
        workflow_plan=workflow_plan,
        answer=answer,
        controller_trace=prefix
        + execution_trace(
            decision,
            workflow_plan,
            retrieve_decision,
            guardrail_decision,
            verify_decision,
        )
        + suffix,
        engine_terminal_answer=terminal_answer,
        engine_terminal_state=terminal_state,
        engine_verify_decision=terminal_verify,
        engine_terminal_guardrail_decision=terminal_guardrail,
        engine_terminal_evidence_bundle=terminal_evidence,
        engine_terminal_projection_hash=projection_hash,
        engine_terminal_commit=deepcopy(
            terminal_state.get("terminal_semantic_commit") or {}
        ),
    )


def _partition_trace(
    trace_prefix: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    trace = list(trace_prefix or [])
    prefix = [item for item in trace if item.get("stage") != "claim_aggregation"]
    suffix = [item for item in trace if item.get("stage") == "claim_aggregation"]
    return prefix, suffix
