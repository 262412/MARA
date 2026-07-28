from __future__ import annotations

from typing import Any


def execution_trace(
    decision: Any,
    workflow_plan: dict[str, Any],
    retrieve_decision: Any,
    guardrail_decision: Any,
    verify_decision: Any,
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
