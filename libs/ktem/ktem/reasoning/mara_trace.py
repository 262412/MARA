from __future__ import annotations

from typing import Generator

from kotaemon.base import Document

from ktem.docqa.execution import RouteExecutionResult


def execution_trace_events(
    execution: RouteExecutionResult,
) -> Generator[Document, None, None]:
    for item in execution.controller_trace:
        stage = item.get("stage")
        if stage == "planner":
            continue
        payload = dict(item)
        payload["event"] = str(stage or "controller")
        payload["route"] = execution.controller_decision.route
        yield Document(
            channel="debug",
            content={"mara_channel": "agent_trace", "payload": payload},
        )


def visible_execution_answer(execution: RouteExecutionResult) -> str:
    route = execution.controller_decision.route
    if route == "direct_answer":
        return (
            "MARA is ready to answer questions about your selected documents. "
            "Ask a source-specific question to retrieve evidence."
        )
    if route == "abstain":
        return (
            "MARA could not identify a safe document-grounded route for this "
            "question. Select relevant sources or ask a source-specific question."
        )
    return execution.answer
