from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

ROUTE_IDS = {
    "direct",
    "doc_text",
    "doc_page_image",
    "doc_element",
    "graph_global",
    "hybrid",
    "abstain",
}
ROUTE_ALIASES = {
    "doc": "doc_text",
    "document": "doc_text",
    "text": "doc_text",
    "visual": "doc_page_image",
    "page_image": "doc_page_image",
    "page-image": "doc_page_image",
    "element": "doc_element",
    "graph": "graph_global",
}
EXECUTOR_SPECS: dict[str, dict[str, Any]] = {
    "query_reformulator": {
        "role": "planner_support",
        "routes": [
            "doc_text",
            "doc_page_image",
            "doc_element",
            "graph_global",
            "hybrid",
        ],
        "cost_units": 1,
    },
    "document_selector": {
        "role": "planner_support",
        "routes": ["doc_text", "doc_page_image", "doc_element", "hybrid"],
        "cost_units": 1,
    },
    "retrieve_text": {
        "role": "retriever",
        "routes": ["doc_text", "hybrid"],
        "cost_units": 1,
    },
    "retrieve_page_image": {
        "role": "retriever",
        "routes": ["doc_page_image", "hybrid"],
        "cost_units": 2,
    },
    "retrieve_element": {
        "role": "retriever",
        "routes": ["doc_element", "hybrid"],
        "cost_units": 1,
    },
    "retrieve_graph": {
        "role": "retriever",
        "routes": ["graph_global", "hybrid"],
        "cost_units": 1,
    },
    "retrieve_hybrid": {
        "role": "retriever",
        "routes": ["hybrid"],
        "cost_units": 3,
    },
    "fuse_evidence": {
        "role": "evidence_fusion",
        "routes": ["hybrid"],
        "cost_units": 1,
    },
    "generate_docqa_answer": {
        "role": "generator",
        "routes": ["doc_text", "hybrid"],
        "cost_units": 2,
    },
    "generate_visual_answer": {
        "role": "generator",
        "routes": ["doc_page_image"],
        "cost_units": 3,
    },
    "generate_element_answer": {
        "role": "generator",
        "routes": ["doc_element"],
        "cost_units": 1,
    },
    "generate_graph_summary": {
        "role": "generator",
        "routes": ["graph_global"],
        "cost_units": 2,
    },
    "direct_answer": {
        "role": "generator",
        "routes": ["direct"],
        "cost_units": 0,
    },
    "verify_answer": {
        "role": "verifier",
        "routes": [
            "doc_text",
            "doc_page_image",
            "doc_element",
            "graph_global",
            "hybrid",
        ],
        "cost_units": 1,
    },
    "abstain": {
        "role": "guardrail",
        "routes": ["abstain"],
        "cost_units": 0,
    },
}
DEFAULT_ROUTE_EXECUTORS = {
    "direct": ["direct_answer"],
    "doc_text": ["retrieve_text", "generate_docqa_answer"],
    "doc_page_image": ["retrieve_page_image", "generate_visual_answer"],
    "doc_element": ["retrieve_element", "generate_element_answer"],
    "graph_global": ["retrieve_graph", "generate_graph_summary"],
    "hybrid": ["retrieve_hybrid", "fuse_evidence", "generate_docqa_answer"],
    "abstain": ["abstain"],
}


@dataclass(frozen=True)
class WorkflowStep:
    index: int
    executor: str
    route: str
    role: str
    status: str = "planned"
    cost_units: int = 0
    reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WorkflowPlan:
    route: str
    policy: str
    controller_mode: str
    strategy: str
    execution_control: str = "fixed_state_machine"
    steps: list[WorkflowStep] = field(default_factory=list)

    @property
    def total_cost_units(self) -> int:
        return sum(step.cost_units for step in self.steps)

    def as_dict(self) -> dict[str, Any]:
        total_cost = self.total_cost_units
        return {
            "route": self.route,
            "policy": self.policy,
            "controller_mode": self.controller_mode,
            "strategy": self.strategy,
            "execution_control": self.execution_control,
            "steps": [step.as_dict() for step in self.steps],
            "total_cost_units": total_cost,
            "reward_features": {
                "cost_units": total_cost,
                "quality_signal": "verification_status",
            },
        }


def executor_registry() -> dict[str, dict[str, Any]]:
    return {
        name: {
            "executor": name,
            "role": str(spec["role"]),
            "status": "registered",
            "routes": list(spec["routes"]),
            "cost_units": int(spec["cost_units"]),
        }
        for name, spec in EXECUTOR_SPECS.items()
    }


def planner_payload_from_trace(agent_trace: list[dict[str, Any]]) -> Any:
    for event in reversed(agent_trace):
        if not isinstance(event, dict) or event.get("event") != "planner_output":
            continue
        return event.get("decision") or event.get("payload") or event
    return None


def build_workflow_plan(
    *,
    route: str,
    request: Any,
    planner_payload: Any = None,
    policy: str = "auto",
    controller_mode: str = "off",
) -> WorkflowPlan:
    normalized_route = _normalize_route(route)
    planned = _planner_workflow_steps(
        normalized_route,
        planner_payload,
        verification_enabled=_verification_enabled(request),
    )
    if planned:
        return WorkflowPlan(
            route=normalized_route,
            policy=policy,
            controller_mode=controller_mode,
            strategy="planned_trace",
            steps=planned,
        )
    return WorkflowPlan(
        route=normalized_route,
        policy=policy,
        controller_mode=controller_mode,
        strategy="route_default",
        steps=_default_steps(normalized_route, _verification_enabled(request)),
    )


def _planner_workflow_steps(
    route: str,
    planner_payload: Any,
    *,
    verification_enabled: bool,
) -> list[WorkflowStep]:
    if not isinstance(planner_payload, dict):
        return []
    workflow = planner_payload.get("workflow")
    if not isinstance(workflow, list):
        return []

    steps: list[WorkflowStep] = []
    for raw_step in workflow:
        step = _coerce_planner_step(len(steps) + 1, route, raw_step)
        if step is not None:
            steps.append(step)
    if verification_enabled and not _has_executor(steps, "verify_answer"):
        verify_step = _workflow_step(len(steps) + 1, "verify_answer", route)
        if verify_step is not None:
            steps.append(verify_step)
    return steps


def _coerce_planner_step(
    index: int,
    route: str,
    raw_step: Any,
) -> WorkflowStep | None:
    if isinstance(raw_step, str):
        return _workflow_step(index, raw_step, route)
    if not isinstance(raw_step, dict):
        return None
    executor = str(raw_step.get("executor") or raw_step.get("agent") or "").strip()
    step_route = _normalize_route(raw_step.get("route") or route)
    reason = str(raw_step.get("reason") or "").strip()
    return _workflow_step(index, executor, step_route, reason=reason)


def _default_steps(route: str, verification_enabled: bool) -> list[WorkflowStep]:
    executors = list(DEFAULT_ROUTE_EXECUTORS[route])
    if verification_enabled and route not in {"direct", "abstain"}:
        executors.append("verify_answer")
    steps: list[WorkflowStep] = []
    for index, executor in enumerate(executors, start=1):
        step = _workflow_step(index, executor, route)
        if step is not None:
            steps.append(step)
    return steps


def _workflow_step(
    index: int,
    executor: str,
    route: str,
    *,
    reason: str = "",
) -> WorkflowStep | None:
    executor_id = str(executor or "").strip()
    spec = EXECUTOR_SPECS.get(executor_id)
    if spec is None:
        return None
    normalized_route = _normalize_route(route)
    return WorkflowStep(
        index=index,
        executor=executor_id,
        route=normalized_route,
        role=str(spec["role"]),
        cost_units=int(spec["cost_units"]),
        reason=reason,
    )


def _normalize_route(route: Any) -> str:
    route_id = str(route or "doc_text").strip().lower().replace("-", "_")
    route_id = ROUTE_ALIASES.get(route_id, route_id)
    return route_id if route_id in ROUTE_IDS else "doc_text"


def _verification_enabled(request: Any) -> bool:
    mode = str(getattr(request, "verification_mode", "") or "").strip().lower()
    return mode in {"light", "strict"}


def _has_executor(steps: list[WorkflowStep], executor: str) -> bool:
    return any(step.executor == executor for step in steps)
