from __future__ import annotations

from typing import Any


def build_controller_output_trace(
    route_decision: Any,
    workflow_plan: dict[str, Any],
    retrieve_decision: Any,
    verify_decision: Any,
    agent_trace: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build the ordered trace emitted with a controller turn."""
    return [
        {
            "stage": "planner",
            "controller_mode": route_decision.controller_mode,
            "route": route_decision.route,
            "policy": route_decision.policy,
        },
        {
            "stage": "workflow_plan",
            "strategy": workflow_plan["strategy"],
            "agent_mode": workflow_plan["agent_mode"],
            "verification_mode": workflow_plan["verification_mode"],
            "execution_control": workflow_plan["execution_control"],
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
