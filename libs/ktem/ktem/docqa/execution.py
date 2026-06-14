from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from .claim_filtering import clean_answer_text
from .controller import (
    RetrieveDecision,
    RouteDecision,
    VerifyDecision,
    _route_decision,
    _verify_decision,
    evaluate_retrieval_quality,
)
from .evidence import EvidenceBundle, build_evidence_bundle
from .workflow import build_workflow_plan, planner_payload_from_trace

DIRECT_ANSWER_MESSAGE = (
    "MARA can answer general questions, but document-specific answers require "
    "retrieved evidence."
)
ABSTAIN_MESSAGE = (
    "MARA could not retrieve enough evidence to answer reliably. Select a "
    "relevant source or page, or ask with more source-specific context."
)

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
class ControllerDecision:
    route: str
    legacy_route: str
    policy: str
    controller_mode: str
    requires_retrieval: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


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
    route_decision = _route_decision(request, agent_trace or [])
    controller_decision = _controller_decision(route_decision)
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
) -> tuple[EvidenceBundle, RetrieveDecision]:
    evidence_metadata = retrieve(request, decision)
    evidence_bundle = build_evidence_bundle(
        decision.legacy_route, request, evidence_metadata
    )
    retrieve_decision = evaluate_retrieval_quality(
        decision.legacy_route,
        evidence_bundle.metadata,
        prompt=str(getattr(request, "prompt", "") or ""),
    )
    if retrieve_decision.status != "ambiguous" or not retrieve_decision.retry:
        return evidence_bundle, retrieve_decision

    evidence_metadata = retrieve(request, decision)
    evidence_bundle = build_evidence_bundle(
        decision.legacy_route, request, evidence_metadata
    )
    retrieve_decision = evaluate_retrieval_quality(
        decision.legacy_route,
        evidence_bundle.metadata,
        attempted_retry=True,
        prompt=str(getattr(request, "prompt", "") or ""),
    )
    return evidence_bundle, retrieve_decision


def _controller_decision(route_decision: RouteDecision) -> ControllerDecision:
    return ControllerDecision(
        route=_CANONICAL_ROUTES[route_decision.route],
        legacy_route=route_decision.route,
        policy=route_decision.policy,
        controller_mode=route_decision.controller_mode,
        requires_retrieval=route_decision.requires_retrieval,
        reason=route_decision.reason,
    )


def _switch_after_failed_retrieval(
    request: Any,
    decision: ControllerDecision,
    failed_decision: RetrieveDecision,
    retrieve: RetrieveFn,
) -> tuple[ControllerDecision, EvidenceBundle, RetrieveDecision, dict[str, Any]] | None:
    for route in _route_switch_candidates(request, decision.legacy_route):
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
        bundle, retrieve_decision = _retrieve_and_evaluate(
            request,
            switched_decision,
            retrieve,
        )
        switch_event = {
            "stage": "route_switch",
            "from_route": decision.legacy_route,
            "to_route": route,
            "reason": failed_decision.reason,
        }
        if retrieve_decision.status == "good":
            return switched_decision, bundle, retrieve_decision, switch_event
    return None


def _route_switch_candidates(request: Any, current_route: str) -> list[str]:
    return [
        route
        for route in getattr(request, "allowed_routes", []) or []
        if route in _CANONICAL_ROUTES
        and route not in {current_route, "direct", "abstain"}
    ]


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
        guardrail = _verification_guardrail(verify_decision)
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
    if not clean_answer_text(answer).strip():
        verify_decision = _empty_answer_verify_decision(request, bundle)
        guardrail = _verification_guardrail(verify_decision)
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
    verify_decision = _verify_decision(request, retrieve_decision, bundle, answer)
    if verify_decision.action == "revise" and rewrite is not None:
        answer = rewrite(request, decision, bundle, answer)
        verify_decision = _verify_decision(request, retrieve_decision, bundle, answer)
    guardrail = _verification_guardrail(verify_decision)
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


def _verification_guardrail(verify_decision: VerifyDecision) -> GuardrailDecision:
    if verify_decision.status in {"supported", "not_requested", "not_required"}:
        return GuardrailDecision("ok", "return", verify_decision.reason)
    if verify_decision.action == "revise":
        return GuardrailDecision("unsupported", "abstain", verify_decision.reason)
    return GuardrailDecision(
        verify_decision.status, verify_decision.action, verify_decision.reason
    )


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
        verified_citations=[
            str(item.get("evidence_id") or "")
            for item in bundle.items
            if str(item.get("evidence_id") or "")
        ],
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
        evidence_id = str(item.get("evidence_id") or "").strip()
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
    return RouteExecutionResult(
        controller_decision=decision,
        retrieve_decision=retrieve_decision,
        verify_decision=verify_decision,
        guardrail_decision=guardrail_decision,
        evidence_bundle=bundle,
        workflow_plan=workflow_plan,
        answer=answer,
        controller_trace=list(trace_prefix or [])
        + _trace(
            decision,
            workflow_plan,
            retrieve_decision,
            guardrail_decision,
            verify_decision,
        ),
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
            "step_count": len(workflow_plan.get("steps") or []),
            "total_cost_units": workflow_plan.get("total_cost_units", 0),
        },
        {"stage": "retrieval_evaluator", **retrieve_decision.as_dict()},
        {"stage": "guardrail", **guardrail_decision.as_dict()},
        {"stage": "verifier", **verify_decision.as_dict()},
    ]
