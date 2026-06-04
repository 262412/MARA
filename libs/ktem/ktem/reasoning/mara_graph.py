from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ktem.docqa.graph_index import (
    graph_answer_from_evidence,
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

    evidence_metadata = _graph_evidence_metadata(graph_context, understanding)
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


def _graph_source_ids(graph_context: dict[str, Any]) -> list[str]:
    support_pages = graph_context.get("support_pages")
    if isinstance(support_pages, dict):
        return [str(file_id) for file_id in support_pages if str(file_id or "").strip()]
    focus_file_id = str(graph_context.get("focus_file_id") or "").strip()
    return [focus_file_id] if focus_file_id else []


def _graph_page_coverage(graph_context: dict[str, Any]) -> list[str]:
    support_pages = graph_context.get("support_pages")
    if not isinstance(support_pages, dict):
        return []
    pages: list[str] = []
    for values in support_pages.values():
        for value in values or []:
            page = str(value or "").strip()
            if page and page not in pages:
                pages.append(page)
    return pages


def _graph_context_evidence(graph_context: dict[str, Any]) -> dict[str, Any]:
    node_id = str(graph_context.get("node_id") or graph_context.get("id") or "root")
    label = str(graph_context.get("label") or graph_context.get("title") or node_id)
    summary = str(
        graph_context.get("summary") or graph_context.get("description") or ""
    )
    if not summary.strip():
        return {}
    evidence_id = f"graph:{node_id}"
    source_ids = _graph_source_ids(graph_context)
    graph_evidence = {
        "evidence_id": evidence_id,
        "id": node_id,
        "label": label,
        "summary": summary,
        "source_ids": source_ids,
        "support_pages": dict(graph_context.get("support_pages") or {}),
        "support_chunk_ids": dict(graph_context.get("support_chunk_ids") or {}),
    }
    return {
        "item": graph_evidence,
        "answer": summary,
        "source_ids": source_ids,
        "page_coverage": _graph_page_coverage(graph_context),
    }


def _graph_evidence_metadata(
    graph_context: dict[str, Any], understanding: dict[str, Any]
) -> dict[str, Any]:
    evidence = _graph_context_evidence(graph_context)
    if not evidence:
        return {}
    item = evidence["item"]
    return {
        "requested_modalities": list(understanding.get("modalities", [])),
        "modality_counts": {"graph": 1},
        "page_coverage": evidence["page_coverage"],
        "source_ids": evidence["source_ids"],
        "evidence_ids": [item["evidence_id"]],
        "evidence": [],
        "graph_evidence": [item],
    }
