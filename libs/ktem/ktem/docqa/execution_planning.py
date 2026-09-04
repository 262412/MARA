from __future__ import annotations

from typing import Any

from .controller import RouteDecision, _route_decision
from .execution_contracts import CANONICAL_ROUTES
from .query_planning import ensure_request_query_plan
from .route_selection import ControllerDecision, controller_decision_from_route
from .workflow import build_workflow_plan, planner_payload_from_trace


def planned_execution(
    request: Any,
    agent_trace: list[dict[str, Any]],
) -> tuple[ControllerDecision, dict[str, Any]]:
    planner_payload = planner_payload_from_trace(agent_trace)
    ensure_request_query_plan(request, planner_payload=planner_payload)
    route_decision = _route_decision(request, agent_trace)
    decision = controller_decision(route_decision, planner_payload)
    workflow_plan = build_execution_workflow_plan(
        request,
        route_decision.route,
        route_decision.policy,
        route_decision.controller_mode,
        agent_trace,
    )
    return decision, workflow_plan


def build_execution_workflow_plan(
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


def controller_decision(
    route_decision: RouteDecision,
    planner_payload: Any = None,
) -> ControllerDecision:
    return controller_decision_from_route(
        route_decision,
        canonical_routes=CANONICAL_ROUTES,
        planner_payload=planner_payload,
    )
