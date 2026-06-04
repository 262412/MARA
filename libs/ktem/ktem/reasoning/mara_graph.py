from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ktem.docqa.graph_index import (
    graph_answer_from_evidence,
    graph_context_evidence_metadata,
    select_graph_index_evidence,
)


@dataclass(frozen=True)
class GraphRouteResult:
    answer: str
    evidence_metadata: dict[str, Any]
    trace_events: list[dict[str, Any]]


def build_graph_route_result(
    planner_payload: dict[str, Any],
    graph_context: Any,
    understanding: dict[str, Any],
) -> GraphRouteResult | None:
    if planner_payload.get("decision", {}).get("route") != "graph_global":
        return None
    if not isinstance(graph_context, dict) or not graph_context:
        return None

    indexed_metadata = select_graph_index_evidence(
        str(understanding.get("question") or ""),
        graph_context,
    )
    if indexed_metadata:
        return _graph_index_route_result(indexed_metadata)

    evidence_metadata = graph_context_evidence_metadata(
        graph_context,
        list(understanding.get("modalities", [])),
    )
    if not evidence_metadata:
        return None
    answer = evidence_metadata["graph_evidence"][0]["summary"]
    return GraphRouteResult(
        answer=answer,
        evidence_metadata=evidence_metadata,
        trace_events=[
            {
                "event": "tool_call",
                "tool": "graph_global",
                "evidence_ids": evidence_metadata["evidence_ids"],
                "evidence_count": 1,
            },
            {
                "event": "verify",
                "result": "supported",
                "evidence_count": 1,
            },
        ],
    )


def _graph_index_route_result(evidence_metadata: dict[str, Any]) -> GraphRouteResult:
    evidence_ids = list(evidence_metadata.get("evidence_ids") or [])
    answer = graph_answer_from_evidence(evidence_metadata.get("graph_evidence") or [])
    return GraphRouteResult(
        answer=answer,
        evidence_metadata=evidence_metadata,
        trace_events=[
            {
                "event": "tool_call",
                "tool": "graph_index",
                "backend": "local_graph_index",
                "evidence_ids": evidence_ids,
                "evidence_count": len(evidence_ids),
            },
            {
                "event": "verify",
                "result": "supported",
                "evidence_count": len(evidence_ids),
            },
        ],
    )
