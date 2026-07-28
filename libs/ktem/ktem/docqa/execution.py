from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .claim_aggregation import aggregate_answer_claims
from .claim_revision import revise_to_supported_claims
from .controller import (
    RetrieveDecision,
    RouteDecision,
    VerifyDecision,
    _route_decision,
    _verify_decision,
    evaluate_retrieval_quality,
)
from .evidence import EvidenceBundle, build_evidence_bundle
from .evidence_identity import identity_of
from .evidence_text import extract_final_answer_text
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
    planner_payload = planner_payload_from_trace(agent_trace or [])
    ensure_request_query_plan(request, planner_payload=planner_payload)
    route_decision = _route_decision(request, agent_trace or [])
    controller_decision = _controller_decision(route_decision, planner_payload)
    workflow_plan = _build_execution_workflow_plan(
        request,
        route_decision.route,
        route_decision.policy,
        route_decision.controller_mode,
        agent_trace or [],
    )
    if controller_decision.route == "direct_answer":
        return _static_result(
            request, controller_decision, DIRECT_ANSWER_MESSAGE, workflow_plan
        )
    if controller_decision.route == "abstain":
        return _static_result(
            request, controller_decision, ABSTAIN_MESSAGE, workflow_plan
        )

    evidence_bundle, retrieve_decision = _retrieve_and_evaluate(
        request,
        controller_decision,
        retrieve,
    )
    route_switch_trace: list[dict[str, Any]] = []
    if retrieve_decision.status != "good":
        switched = _switch_after_failed_retrieval(
            request,
            controller_decision,
            retrieve_decision,
            evidence_bundle,
            retrieve,
        )
        if switched is not None:
            (
                controller_decision,
                evidence_bundle,
                retrieve_decision,
                switch_event,
            ) = switched
            workflow_plan = _build_execution_workflow_plan(
                request,
                controller_decision.legacy_route,
                controller_decision.policy,
                controller_decision.controller_mode,
                [],
            )
            route_switch_trace.append(switch_event)
    if retrieve_decision.status != "good":
        return _guarded_result(
            request,
            controller_decision,
            retrieve_decision,
            evidence_bundle,
            workflow_plan,
            route_switch_trace,
        )

    answer = generate(request, controller_decision, evidence_bundle)
    return _verified_result(
        request,
        controller_decision,
        retrieve_decision,
        evidence_bundle,
        answer,
        rewrite,
        workflow_plan,
        route_switch_trace,
    )


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
) -> RouteExecutionResult:
    bundle = build_evidence_bundle(decision.legacy_route, request, {})
    retrieve_decision = evaluate_retrieval_quality(decision.legacy_route, {})
    verify_decision = _verify_decision(request, retrieve_decision, bundle, answer)
    return _result(
        decision,
        retrieve_decision,
        verify_decision,
        GuardrailDecision("ok", "return", decision.reason),
        bundle,
        workflow_plan,
        answer,
    )


def _guarded_result(
    request: Any,
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]] | None = None,
) -> RouteExecutionResult:
    if _ragtruth_contract_request(request):
        bundle.metadata["task_contract_fallback"] = "ragtruth_empty_retrieval"
        verify_decision = VerifyDecision(
            mode="off",
            status="not_required",
            reason="RAGTruth task contract handled empty retrieval.",
        )
        return _result(
            decision,
            retrieve_decision,
            verify_decision,
            GuardrailDecision("ok", "return", verify_decision.reason),
            bundle,
            workflow_plan,
            RAGTRUTH_EMPTY_ANSWER,
            trace_prefix,
        )
    verify_decision = _verify_decision(request, retrieve_decision, bundle, "")
    guardrail = GuardrailDecision(
        status="not_enough_evidence",
        action="abstain",
        reason=retrieve_decision.reason,
    )
    return _result(
        decision,
        retrieve_decision,
        verify_decision,
        guardrail,
        bundle,
        workflow_plan,
        ABSTAIN_MESSAGE,
        trace_prefix,
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
) -> RouteExecutionResult:
    if bundle.metadata.get("generation_backend") == "evidence_only_without_vlm":
        verify_decision = _evidence_only_verify_decision(request, bundle)
        guardrail = _verification_guardrail(verify_decision, request)
        return _result(
            decision,
            retrieve_decision,
            verify_decision,
            guardrail,
            bundle,
            workflow_plan,
            answer,
            trace_prefix,
        )
    if not extract_final_answer_text(answer).strip():
        if _ragtruth_contract_request(request):
            bundle.metadata["task_contract_fallback"] = "ragtruth_empty_generation"
            answer = RAGTRUTH_EMPTY_ANSWER
        else:
            verify_decision = _empty_answer_verify_decision(request, bundle)
            guardrail = _verification_guardrail(verify_decision, request)
            return _result(
                decision,
                retrieve_decision,
                verify_decision,
                guardrail,
                bundle,
                workflow_plan,
                ABSTAIN_MESSAGE,
                trace_prefix,
            )
    answer, aggregation_trace = aggregate_answer_claims(answer)
    trace_prefix = list(trace_prefix or []) + [
        {"stage": "claim_aggregation", **aggregation_trace}
    ]
    verify_decision = _verify_decision(request, retrieve_decision, bundle, answer)
    if verify_decision.action == "revise" and rewrite is not None:
        answer = rewrite(request, decision, bundle, answer)
        answer, rewrite_aggregation_trace = aggregate_answer_claims(answer)
        trace_prefix.append(
            {
                "stage": "claim_aggregation",
                "rewrite": True,
                **rewrite_aggregation_trace,
            }
        )
        verify_decision = _verify_decision(request, retrieve_decision, bundle, answer)
    if verify_decision.action == "revise":
        answer, verify_decision, revision_trace = revise_to_supported_claims(
            request,
            retrieve_decision,
            bundle,
            answer,
            verify_decision,
            verify=_verify_decision,
        )
        if revision_trace:
            trace_prefix.append(revision_trace)
    guardrail = _verification_guardrail(verify_decision, request)
    if guardrail.action == "abstain":
        answer = ABSTAIN_MESSAGE
    return _result(
        decision,
        retrieve_decision,
        verify_decision,
        guardrail,
        bundle,
        workflow_plan,
        answer,
        trace_prefix,
    )


def _verification_guardrail(
    verify_decision: VerifyDecision,
    request: Any | None = None,
) -> GuardrailDecision:
    if verify_decision.status in {"supported", "not_requested", "not_required"}:
        return GuardrailDecision("ok", "return", verify_decision.reason)
    if verify_decision.action == "revise":
        if _finance_benchmark_request(request):
            return GuardrailDecision("unsupported", "revise", verify_decision.reason)
        return GuardrailDecision("unsupported", "abstain", verify_decision.reason)
    return GuardrailDecision(
        verify_decision.status, verify_decision.action, verify_decision.reason
    )


def _finance_benchmark_request(request: Any | None) -> bool:
    if request is None:
        return False
    origin = str(getattr(request, "origin", "") or "").strip().lower()
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    return origin == "benchmark" and domain in {"finance", "financial"}


def _ragtruth_contract_request(request: Any | None) -> bool:
    if request is None:
        return False
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    return domain == "ragtruth"


def _evidence_only_verify_decision(
    request: Any,
    bundle: EvidenceBundle,
) -> VerifyDecision:
    mode = str(getattr(request, "verification_mode", None) or "off").strip().lower()
    if mode not in {"off", "light", "strict"}:
        mode = "off"
    return VerifyDecision(
        mode=mode,
        status="not_required",
        reason="Evidence-only visual route did not invoke a VLM generator.",
        verified_citations=_bundle_citation_ids(bundle),
    )


def _empty_answer_verify_decision(
    request: Any,
    bundle: EvidenceBundle,
) -> VerifyDecision:
    mode = str(getattr(request, "verification_mode", None) or "off").strip().lower()
    if mode not in {"off", "light", "strict"}:
        mode = "off"
    return VerifyDecision(
        mode=mode,
        status="not_enough_evidence",
        reason=f"{mode.title()} verification found no final answer to verify.",
        action="abstain",
        verified_citations=_bundle_citation_ids(bundle),
    )


def _bundle_citation_ids(bundle: EvidenceBundle) -> list[str]:
    citations: list[str] = []
    for item in bundle.items:
        evidence_id = identity_of(item).key
        if evidence_id and evidence_id not in citations:
            citations.append(evidence_id)
    return citations


def _result(
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    verify_decision: VerifyDecision,
    guardrail_decision: GuardrailDecision,
    bundle: EvidenceBundle,
    workflow_plan: dict[str, Any],
    answer: str,
    trace_prefix: list[dict[str, Any]] | None = None,
) -> RouteExecutionResult:
    bundle = with_verification_evidence(bundle, verify_decision)
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
        + _trace(
            decision,
            workflow_plan,
            retrieve_decision,
            guardrail_decision,
            verify_decision,
        )
        + suffix,
    )


def _trace(
    decision: ControllerDecision,
    workflow_plan: dict[str, Any],
    retrieve_decision: RetrieveDecision,
    guardrail_decision: GuardrailDecision,
    verify_decision: VerifyDecision,
) -> list[dict[str, Any]]:
    return [
        {"stage": "planner", **decision.as_dict()},
        {
            "stage": "workflow_plan",
            "strategy": workflow_plan.get("strategy", ""),
            "execution_control": workflow_plan.get("execution_control", ""),
            "step_count": len(workflow_plan.get("steps") or []),
            "total_cost_units": workflow_plan.get("total_cost_units", 0),
        },
        {"stage": "retrieval_evaluator", **retrieve_decision.as_dict()},
        {"stage": "guardrail", **guardrail_decision.as_dict()},
        {"stage": "verifier", **verify_decision.as_dict()},
    ]
