from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .controller import (
    RetrieveDecision,
    RouteDecision,
    VerifyDecision,
    _route_decision,
    _verify_decision,
    evaluate_retrieval_quality,
)
from .evidence import EvidenceBundle, build_evidence_bundle
from .execution_trace import execution_trace
from .execution_verification import ragtruth_contract_request, verify_generated_answer
from .pipeline_stage_timings import PipelineStageTimings
from .query_planning import ensure_request_query_plan
from .retrieval_rounds import retrieve_with_rounds
from .route_budget import optional_stage_allowed, route_budget_metadata
from .route_capabilities import (
    route_switch_candidate_evaluation as _route_switch_candidate_evaluation,
)
from .route_capabilities import route_switch_candidates as _route_switch_candidates
from .route_selection import (
    ControllerDecision,
    controller_decision_from_route,
    mark_route_switch_recovery,
)
from .verification import with_verification_evidence
from .workflow import build_workflow_plan, planner_payload_from_trace

DIRECT_ANSWER_MESSAGE = (
    "MARA can answer general questions, but document-specific answers require "
    "retrieved evidence."
)
ABSTAIN_MESSAGE = (
    "MARA could not retrieve enough evidence to answer reliably. Select a "
    "relevant source or page, or ask with more source-specific context."
)
RAGTRUTH_EMPTY_ANSWER = '{"hallucination list": []}'

RetrieveFn = Callable[[Any, "ControllerDecision"], dict[str, Any]]
GenerateFn = Callable[[Any, "ControllerDecision", EvidenceBundle], str]
RewriteFn = Callable[[Any, "ControllerDecision", EvidenceBundle, str], str]

_CANONICAL_ROUTES = {
    "direct": "direct_answer",
    "doc_text": "text_rag",
    "doc_page_image": "page_image_rag",
    "doc_element": "element_rag",
    "graph_global": "graph_rag",
    "hybrid": "hybrid_rag",
    "abstain": "abstain",
}


@dataclass(frozen=True)
class GuardrailDecision:
    status: str
    action: str
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RouteExecutionResult:
    controller_decision: ControllerDecision
    retrieve_decision: RetrieveDecision
    verify_decision: VerifyDecision
    guardrail_decision: GuardrailDecision
    evidence_bundle: EvidenceBundle
    workflow_plan: dict[str, Any] = field(default_factory=dict)
    answer: str = ""
    controller_trace: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "controller_decision": self.controller_decision.as_dict(),
            "retrieve_decision": self.retrieve_decision.as_dict(),
            "verify_decision": self.verify_decision.as_dict(),
            "guardrail_decision": self.guardrail_decision.as_dict(),
            "evidence_bundle": self.evidence_bundle.as_dict(),
            "workflow_plan": dict(self.workflow_plan),
            "answer": self.answer,
            "controller_trace": list(self.controller_trace),
        }


def execute_controller_turn(
    request: Any,
    *,
    retrieve: RetrieveFn,
    generate: GenerateFn,
    rewrite: RewriteFn | None = None,
    agent_trace: list[dict[str, Any]] | None = None,
) -> RouteExecutionResult:
    timings = PipelineStageTimings()
    controller_decision, workflow_plan = timings.measure(
        "planning_seconds",
        _planned_execution,
        request,
        agent_trace or [],
    )
    if controller_decision.route in {"direct_answer", "abstain"}:
        answer = (
            DIRECT_ANSWER_MESSAGE
            if controller_decision.route == "direct_answer"
            else ABSTAIN_MESSAGE
        )
        return _static_result(
            request,
            controller_decision,
            answer,
            workflow_plan,
            timings,
        )
    evidence_bundle, retrieve_decision = timings.measure(
        "retrieval_seconds",
        _retrieve_and_evaluate,
        request,
        controller_decision,
        retrieve,
    )
    (
        controller_decision,
        evidence_bundle,
        retrieve_decision,
        workflow_plan,
        route_switch_trace,
    ) = _recover_after_failed_retrieval(
        request,
        controller_decision,
        retrieve_decision,
        evidence_bundle,
        workflow_plan,
        retrieve,
        timings,
    )
    if retrieve_decision.status != "good":
        return _guarded_result(
            request,
            controller_decision,
            retrieve_decision,
            evidence_bundle,
            workflow_plan,
            route_switch_trace,
            timings,
        )
    answer = timings.measure(
        "generation_seconds",
        generate,
        request,
        controller_decision,
        evidence_bundle,
    )
    return _verified_result(
        request,
        controller_decision,
        retrieve_decision,
        evidence_bundle,
        answer,
        rewrite,
        workflow_plan,
        route_switch_trace,
        timings,
    )


def _recover_after_failed_retrieval(
    request: Any,
    controller_decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    evidence_bundle: EvidenceBundle,
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
        return (
            controller_decision,
            evidence_bundle,
            retrieve_decision,
            workflow_plan,
            [],
        )
    switched = timings.measure(
        "retry_seconds",
        _switch_after_failed_retrieval,
        request,
        controller_decision,
        retrieve_decision,
        evidence_bundle,
        retrieve,
    )
    if switched is None:
        return (
            controller_decision,
            evidence_bundle,
            retrieve_decision,
            workflow_plan,
            [],
        )
    controller_decision, evidence_bundle, retrieve_decision, event = switched
    workflow_plan = _build_execution_workflow_plan(
        request,
        controller_decision.legacy_route,
        controller_decision.policy,
        controller_decision.controller_mode,
        [],
    )
    return (
        controller_decision,
        evidence_bundle,
        retrieve_decision,
        workflow_plan,
        [event],
    )


def _planned_execution(
    request: Any,
    agent_trace: list[dict[str, Any]],
) -> tuple[ControllerDecision, dict[str, Any]]:
    planner_payload = planner_payload_from_trace(agent_trace)
    ensure_request_query_plan(request, planner_payload=planner_payload)
    route_decision = _route_decision(request, agent_trace)
    controller_decision = _controller_decision(route_decision, planner_payload)
    workflow_plan = _build_execution_workflow_plan(
        request,
        route_decision.route,
        route_decision.policy,
        route_decision.controller_mode,
        agent_trace,
    )
    return controller_decision, workflow_plan


def _build_execution_workflow_plan(
    request: Any,
    route: str,
    policy: str,
    controller_mode: str,
    agent_trace: list[dict[str, Any]],
) -> dict[str, Any]:
    return build_workflow_plan(
        route=route,
        request=request,
        planner_payload=planner_payload_from_trace(agent_trace),
        policy=policy,
        controller_mode=controller_mode,
    ).as_dict()


def _retrieve_and_evaluate(
    request: Any,
    decision: ControllerDecision,
    retrieve: RetrieveFn,
    *,
    max_rounds: int | None = None,
) -> tuple[EvidenceBundle, RetrieveDecision]:
    plan = ensure_request_query_plan(request)
    return retrieve_with_rounds(
        request,
        decision,
        retrieve,
        evaluate=evaluate_retrieval_quality,
        retry_poor=(
            decision.legacy_route == "doc_element"
            or not _route_switch_candidates(request, decision.legacy_route)
        ),
        max_rounds=plan.max_retrieval_rounds if max_rounds is None else max_rounds,
    )


def _controller_decision(
    route_decision: RouteDecision,
    planner_payload: Any = None,
) -> ControllerDecision:
    return _controller_decision_from_payload(route_decision, planner_payload)


def _controller_decision_from_payload(
    route_decision: RouteDecision,
    planner_payload: Any,
) -> ControllerDecision:
    return controller_decision_from_route(
        route_decision,
        canonical_routes=_CANONICAL_ROUTES,
        planner_payload=planner_payload,
    )


def _switch_after_failed_retrieval(
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
    candidates, rejected_candidates = _route_switch_candidate_evaluation(
        request,
        decision.legacy_route,
    )
    if rejected_candidates:
        failed_bundle.metadata["rejected_route_switch_candidates"] = list(
            rejected_candidates
        )
    for route in candidates:
        switched_decision = _controller_decision(
            RouteDecision(
                route=route,
                policy="route_switch",
                controller_mode=decision.controller_mode,
                requires_retrieval=True,
                reason=(
                    f"Switched from {decision.legacy_route} after "
                    f"{failed_decision.status} retrieval."
                ),
            )
        )
        switched_decision = mark_route_switch_recovery(
            switched_decision,
            initial_decision=decision,
            candidates=candidates,
        )
        bundle, retrieve_decision = _retrieve_and_evaluate(
            request,
            switched_decision,
            retrieve,
            max_rounds=1,
        )
        switch_event = {
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
            switch_event["rejected_route_switch_candidates"] = list(rejected_candidates)
        if retrieve_decision.status == "good":
            return switched_decision, bundle, retrieve_decision, switch_event
    return None


def _static_result(
    request: Any,
    decision: ControllerDecision,
    answer: str,
    workflow_plan: dict[str, Any],
    stage_timings: PipelineStageTimings,
) -> RouteExecutionResult:
    bundle = build_evidence_bundle(decision.legacy_route, request, {})
    retrieve_decision = evaluate_retrieval_quality(decision.legacy_route, {})
    verify_decision = _verify_decision(request, retrieve_decision, bundle, answer)
    return _result(
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


def _guarded_result(
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
        return _result(
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
    return _result(
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


def _verified_result(
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
    return _result(
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
    )


def _result(
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
) -> RouteExecutionResult:
    bundle = with_verification_evidence(bundle, verify_decision, request)
    (stage_timings or PipelineStageTimings()).record(bundle)
    prefix = [
        item
        for item in list(trace_prefix or [])
        if item.get("stage") != "claim_aggregation"
    ]
    suffix = [
        item
        for item in list(trace_prefix or [])
        if item.get("stage") == "claim_aggregation"
    ]
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
    )
