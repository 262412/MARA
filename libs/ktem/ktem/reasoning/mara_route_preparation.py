from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ktem.docqa.execution import (
    RouteExecutionResult,
    deadline_exhausted_controller_result,
)
from ktem.docqa.route_budget import RouteDeadlineExhausted, run_blocking_route_stage
from ktem.docqa.typed_retrieval_recovery import typed_qasper_initial_query

from .mara_controller import planner_trace_payload
from .mara_route_probe import (
    controller_latency_budget,
    controller_route_probe,
    dataset_family,
)


@dataclass(frozen=True, slots=True)
class RoutePreparation:
    planner_payload: dict[str, Any] | None = None
    deadline_execution: RouteExecutionResult | None = None


def route_trace_payload(
    understanding: dict[str, Any],
    agent_mode: str | None,
    plan: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "event": "route",
        "task_type": understanding["task_type"],
        "modalities": understanding["modalities"],
        "scope": understanding["scope"],
        "agent_mode": agent_mode or "auto",
        "plan": plan,
    }


def prepare_controller_route(
    pipeline: Any,
    execution_request: Any,
    routing_message: str,
    history: list[Any],
    understanding: dict[str, Any],
    initial_trace: dict[str, Any],
) -> RoutePreparation:
    try:
        probe_query = typed_qasper_initial_query(execution_request, routing_message)
        route_probe = run_blocking_route_stage(
            execution_request,
            "route_probe",
            controller_route_probe,
            pipeline,
            probe_query,
            history,
            understanding,
        )
        planner_payload = run_blocking_route_stage(
            execution_request,
            "planner_model",
            planner_trace_payload,
            understanding,
            planner=getattr(pipeline, "planner", None),
            planner_model=getattr(pipeline, "planner_model", None),
            question=routing_message,
            allowed_routes=getattr(pipeline, "allowed_routes", None),
            route_probe=route_probe,
            dataset_family=dataset_family(pipeline),
            latency_budget=controller_latency_budget(pipeline),
        )
    except RouteDeadlineExhausted as error:
        return RoutePreparation(
            deadline_execution=deadline_exhausted_controller_result(
                execution_request,
                error,
                agent_trace=[initial_trace],
            )
        )
    return RoutePreparation(planner_payload=planner_payload)
