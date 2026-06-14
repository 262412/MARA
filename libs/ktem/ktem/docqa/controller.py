from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from .evidence import build_evidence_bundle
from .retrieval_adequacy import retrieval_adequacy_issue
from .verification import VerifyDecision, verify_decision
from .workflow import build_workflow_plan
from .workflow import executor_registry as workflow_executor_registry
from .workflow import planner_payload_from_trace

ROUTE_IDS = (
    "direct",
    "doc_text",
    "doc_page_image",
    "doc_element",
    "graph_global",
    "hybrid",
    "abstain",
)
ROUTE_ALIASES = {
    "auto": "doc_text",
    "doc": "doc_text",
    "document": "doc_text",
    "text": "doc_text",
    "visual": "doc_page_image",
    "page_image": "doc_page_image",
    "page-image": "doc_page_image",
    "element": "doc_element",
    "graph": "graph_global",
}
RETRIEVAL_ROUTES = {
    "doc_text",
    "doc_page_image",
    "doc_element",
    "graph_global",
    "hybrid",
}
ROUTE_EVIDENCE_TYPES: dict[str, list[str]] = {
    "direct": [],
    "doc_text": ["text"],
    "doc_page_image": ["page_image"],
    "doc_element": ["element"],
    "graph_global": ["graph"],
    "hybrid": ["text", "page_image", "element"],
    "abstain": [],
}
ROUTE_RETRIEVE_FNS: dict[str, str] = {
    "direct": "",
    "doc_text": "retrieve_text",
    "doc_page_image": "retrieve_page_image",
    "doc_element": "retrieve_element",
    "graph_global": "retrieve_graph",
    "hybrid": "retrieve_hybrid",
    "abstain": "",
}
ROUTE_GENERATE_FNS: dict[str, str] = {
    "direct": "direct_answer",
    "doc_text": "generate_docqa_answer",
    "doc_page_image": "generate_visual_answer",
    "doc_element": "generate_element_answer",
    "graph_global": "generate_graph_summary",
    "hybrid": "generate_docqa_answer",
    "abstain": "abstain",
}
ROUTE_BACKEND_METADATA: dict[str, dict[str, str]] = {
    "direct": {"generator_backend": "local_direct"},
    "doc_text": {
        "text_retriever": "docqa_text",
        "generator_backend": "local_docqa_generator",
    },
    "doc_page_image": {
        "visual_retriever": "local_late_interaction",
        "visual_backend_type": "deterministic_smoke",
    },
    "doc_element": {
        "text_retriever": "docqa_element_metadata",
        "generator_backend": "local_element_evidence",
    },
    "graph_global": {
        "graph_backend": "local_graph_index",
        "generator_backend": "local_graph_summary",
    },
    "hybrid": {
        "text_retriever": "docqa_text",
        "visual_retriever": "local_late_interaction",
        "generator_backend": "local_docqa_generator",
    },
    "abstain": {"generator_backend": "local_abstain"},
}


@dataclass(frozen=True)
class RouteDecision:
    route: str
    policy: str
    controller_mode: str
    requires_retrieval: bool
    reason: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RetrieveDecision:
    status: str
    reason: str
    retry: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ControllerTrace:
    events: list[dict[str, Any]] = field(default_factory=list)

    def as_list(self) -> list[dict[str, Any]]:
        return list(self.events)


def route_registry() -> dict[str, dict[str, Any]]:
    return {
        route: {
            "route": route,
            "requires_retrieval": route in RETRIEVAL_ROUTES,
            "executor": route,
            "evidence_types": list(ROUTE_EVIDENCE_TYPES[route]),
            "retrieve_fn": ROUTE_RETRIEVE_FNS[route],
            "generate_fn": ROUTE_GENERATE_FNS[route],
            "required_evidence_types": list(ROUTE_EVIDENCE_TYPES[route]),
            "backend_metadata": dict(ROUTE_BACKEND_METADATA[route]),
        }
        for route in ROUTE_IDS
    }


def executor_registry() -> dict[str, dict[str, Any]]:
    registry = {
        route: {
            "route": route,
            "status": "registered",
            "evidence_types": list(ROUTE_EVIDENCE_TYPES[route]),
        }
        for route in ROUTE_IDS
    }
    registry.update(workflow_executor_registry())
    return registry


def build_controller_outputs(
    request: Any,
    agent_trace: list[dict[str, Any]],
    evidence_metadata: dict[str, Any],
    answer: str = "",
) -> dict[str, Any]:
    route_decision = _route_decision(request, agent_trace)
    workflow_plan = build_workflow_plan(
        route=route_decision.route,
        request=request,
        planner_payload=planner_payload_from_trace(agent_trace or []),
        policy=route_decision.policy,
        controller_mode=route_decision.controller_mode,
    ).as_dict()
    evidence_bundle = build_evidence_bundle(
        route_decision.route,
        request,
        evidence_metadata,
    )
    retrieve_decision = evaluate_retrieval_quality(
        route_decision.route,
        evidence_bundle.metadata,
        prompt=str(getattr(request, "prompt", "") or ""),
    )
    verify_decision = _verify_decision(
        request,
        retrieve_decision,
        evidence_bundle,
        answer,
    )
    controller_trace = ControllerTrace(
        [
            {
                "stage": "planner",
                "controller_mode": route_decision.controller_mode,
                "route": route_decision.route,
                "policy": route_decision.policy,
            },
            {
                "stage": "workflow_plan",
                "strategy": workflow_plan["strategy"],
                "step_count": len(workflow_plan["steps"]),
                "total_cost_units": workflow_plan["total_cost_units"],
            },
            {
                "stage": "retrieval_evaluator",
                "status": retrieve_decision.status,
                "retry": retrieve_decision.retry,
            },
            {
                "stage": "verifier",
                "mode": verify_decision.mode,
                "status": verify_decision.status,
            },
            *list(agent_trace or []),
        ]
    )
    return {
        "controller_decision": _controller_decision_payload(route_decision),
        "route_decision": route_decision.as_dict(),
        "retrieve_decision": retrieve_decision.as_dict(),
        "verify_decision": verify_decision.as_dict(),
        "guardrail_decision": _guardrail_decision_payload(
            retrieve_decision, verify_decision
        ),
        "controller_trace": controller_trace.as_list(),
        "evidence_bundle": evidence_bundle.as_dict(),
        "workflow_plan": workflow_plan,
    }


def parse_planner_decision(
    raw_output: Any, allowed_routes: Any = None
) -> RouteDecision:
    payload = _coerce_planner_payload(raw_output)
    if not payload:
        return _invalid_planner_decision()

    policy = _normalize_policy(payload.get("policy"))
    route = _resolve_route(_normalize_policy(payload.get("route")))
    if route == "doc_text" and str(payload.get("route") or "").strip() not in {
        "doc",
        "document",
        "text",
        "doc_text",
    }:
        return _invalid_planner_decision()

    constrained_route = _constrain_route(route, allowed_routes)
    reason = str(payload.get("reason") or "").strip()
    return RouteDecision(
        route=constrained_route,
        policy=policy,
        controller_mode="llm",
        requires_retrieval=constrained_route in RETRIEVAL_ROUTES,
        reason=reason or _route_reason(policy, constrained_route),
    )


def evaluate_retrieval_quality(
    route: str,
    evidence_metadata: dict[str, Any],
    attempted_retry: bool = False,
    *,
    prompt: str = "",
) -> RetrieveDecision:
    if route == "direct":
        return RetrieveDecision(
            status="not_required",
            reason="Direct route does not require retrieval.",
        )
    if route == "abstain":
        return RetrieveDecision(
            status="poor",
            reason="Route abstained before retrieval.",
            retry=False,
        )
    if _evidence_count(evidence_metadata) > 0:
        adequacy_issue = retrieval_adequacy_issue(prompt, evidence_metadata)
        if adequacy_issue:
            return RetrieveDecision(
                status="ambiguous",
                reason=adequacy_issue,
                retry=not attempted_retry,
            )
        return RetrieveDecision(
            status="good",
            reason="Retrieved evidence is sufficient for generation.",
            retry=False,
        )
    if _has_retrieval_metadata(evidence_metadata):
        return RetrieveDecision(
            status="ambiguous",
            reason="Retrieved evidence metadata is present but lacks concrete evidence.",
            retry=not attempted_retry,
        )
    return RetrieveDecision(
        status="poor",
        reason="No retrieved evidence was captured for this turn.",
        retry=not attempted_retry,
    )


def _route_decision(
    request: Any, agent_trace: list[dict[str, Any]] | None = None
) -> RouteDecision:
    policy = _normalize_policy(getattr(request, "route_policy", None))
    controller_mode = _normalize_controller_mode(
        getattr(request, "controller_mode", None)
    )
    planner_output = _planner_output_from_trace(agent_trace or [])
    if controller_mode == "llm" and policy == "auto" and planner_output is not None:
        return parse_planner_decision(
            planner_output,
            allowed_routes=getattr(request, "allowed_routes", None),
        )

    route = _resolve_route(policy)
    route = _constrain_route(route, getattr(request, "allowed_routes", None))
    return RouteDecision(
        route=route,
        policy=policy,
        controller_mode=controller_mode,
        requires_retrieval=route in RETRIEVAL_ROUTES,
        reason=_route_reason(policy, route),
    )


_verify_decision = verify_decision


def _normalize_controller_mode(value: Any) -> str:
    mode = str(value or "off").strip().lower()
    return mode if mode in {"llm", "off"} else "off"


def _normalize_policy(value: Any) -> str:
    policy = str(value or "auto").strip().lower().replace("-", "_")
    return policy or "auto"


def _coerce_planner_payload(raw_output: Any) -> dict[str, Any]:
    if isinstance(raw_output, dict):
        return raw_output
    if isinstance(raw_output, str):
        try:
            payload = json.loads(raw_output)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def _invalid_planner_decision() -> RouteDecision:
    return RouteDecision(
        route="doc_text",
        policy="auto",
        controller_mode="llm",
        requires_retrieval=True,
        reason="Invalid planner output; using document text route.",
    )


def _planner_output_from_trace(agent_trace: list[dict[str, Any]]) -> Any:
    for event in reversed(agent_trace):
        if not isinstance(event, dict):
            continue
        if event.get("event") != "planner_output":
            continue
        return event.get("decision") or event.get("payload") or event
    return None


def _evidence_count(evidence_metadata: dict[str, Any]) -> int:
    evidence = evidence_metadata.get("evidence")
    if isinstance(evidence, list):
        return len(evidence)
    evidence_ids = evidence_metadata.get("evidence_ids")
    if isinstance(evidence_ids, list):
        return len(evidence_ids)
    counts = evidence_metadata.get("modality_counts")
    if isinstance(counts, dict):
        return sum(int(value or 0) for value in counts.values())
    return 0


def _has_retrieval_metadata(evidence_metadata: dict[str, Any]) -> bool:
    ignored_keys = {
        "requested_modalities",
        "retrieval_attempts",
        "retrieval_info_count",
    }
    ignored_empty_keys = {"evidence", "evidence_ids", "modality_counts"}
    for key, value in evidence_metadata.items():
        if key in ignored_keys:
            continue
        if key in ignored_empty_keys and not value:
            continue
        if isinstance(value, (list, dict, tuple, set)):
            if value:
                return True
            continue
        if value:
            return True
    return False


def _resolve_route(policy: str) -> str:
    route = ROUTE_ALIASES.get(policy, policy)
    return route if route in ROUTE_IDS else "doc_text"


def _constrain_route(route: str, allowed_routes: Any) -> str:
    allowed = [str(item).strip() for item in allowed_routes or [] if str(item).strip()]
    if not allowed or route in allowed:
        return route
    return allowed[0] if allowed[0] in ROUTE_IDS else "doc_text"


def _route_reason(policy: str, route: str) -> str:
    if policy == "auto":
        return "Automatic route policy selected the document text route."
    labels = {
        "direct": "direct",
        "doc_text": "document text",
        "doc_page_image": "visual page",
        "doc_element": "document element",
        "graph_global": "graph",
        "hybrid": "hybrid",
        "abstain": "abstain",
    }
    return f"Requested {labels.get(route, route)} route."


def _controller_decision_payload(route_decision: RouteDecision) -> dict[str, Any]:
    return {
        "route": _canonical_execution_route(route_decision.route),
        "legacy_route": route_decision.route,
        "policy": route_decision.policy,
        "controller_mode": route_decision.controller_mode,
        "requires_retrieval": route_decision.requires_retrieval,
        "reason": route_decision.reason,
    }


def _guardrail_decision_payload(
    retrieve_decision: RetrieveDecision,
    verify_decision: VerifyDecision,
) -> dict[str, Any]:
    if (
        retrieve_decision.status != "good"
        and retrieve_decision.status != "not_required"
    ):
        return {
            "status": "not_enough_evidence",
            "action": verify_decision.action,
            "reason": retrieve_decision.reason,
        }
    if verify_decision.status in {"supported", "not_requested", "not_required"}:
        return {
            "status": "ok",
            "action": "return",
            "reason": verify_decision.reason,
        }
    return {
        "status": verify_decision.status,
        "action": verify_decision.action,
        "reason": verify_decision.reason,
    }


def _canonical_execution_route(route: str) -> str:
    return {
        "direct": "direct_answer",
        "doc_text": "text_rag",
        "doc_page_image": "page_image_rag",
        "doc_element": "element_rag",
        "graph_global": "graph_rag",
        "hybrid": "hybrid_rag",
        "abstain": "abstain",
    }[route]
