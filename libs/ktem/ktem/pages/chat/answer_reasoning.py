"""Reasoning block renderer for the page-level answer panel."""

from __future__ import annotations

import html
from typing import Any

_ROUTE_LABELS = {
    "direct": "Direct answer",
    "direct_answer": "Direct answer",
    "doc_text": "Text evidence",
    "text_rag": "Text evidence",
    "doc_page_image": "Page image evidence",
    "page_image_rag": "Page image evidence",
    "doc_element": "Element evidence",
    "element_rag": "Element evidence",
    "graph_global": "Knowledge graph",
    "graph_rag": "Knowledge graph",
    "hybrid": "Hybrid evidence",
    "hybrid_rag": "Hybrid evidence",
    "abstain": "Abstain",
}

_MODALITY_LABELS = {
    "text": "Text evidence",
    "page_image": "Page image evidence",
    "image": "Image evidence",
    "graph": "Graph evidence",
    "element": "Element evidence",
    "table": "Table evidence",
}


def render_answer_reasoning_block(
    *,
    is_streaming: bool = False,
    route_decision: dict[str, Any] | None = None,
    retrieve_decision: dict[str, Any] | None = None,
    verify_decision: dict[str, Any] | None = None,
    evidence_bundle: dict[str, Any] | None = None,
    stream_events: list[dict[str, Any]] | None = None,
) -> str:
    """Render a collapsible, user-safe controller summary inside Answer."""
    if is_streaming:
        return _render_streaming_block(stream_events or [])
    if not _has_reasoning_summary(
        route_decision,
        retrieve_decision,
        verify_decision,
        evidence_bundle,
        stream_events,
    ):
        return ""
    return _render_completed_block(
        route_decision or {},
        retrieve_decision or {},
        verify_decision or {},
        evidence_bundle or {},
        stream_events or [],
    )


def _render_streaming_block(stream_events: list[dict[str, Any]]) -> str:
    event_count = len(stream_events)
    has_route = _has_mara_channel(stream_events, "agent_trace")
    has_evidence = _has_mara_channel(
        stream_events, "evidence_metadata"
    ) or _has_channel(stream_events, "info")
    has_answer = _has_channel(stream_events, "chat")
    route_status = "done" if has_route else ("active" if event_count else "pending")
    evidence_status = "done" if has_evidence else ("active" if has_route else "pending")
    steps = [
        (
            "Scope",
            "Checking selected source scope",
            "done" if event_count else "active",
        ),
        (
            "Route",
            (
                "Controller route event received"
                if has_route
                else "Choosing the retrieval path"
            ),
            route_status,
        ),
        (
            "Evidence",
            (
                "Retrieval metadata received"
                if has_evidence
                else "Preparing source-backed evidence"
            ),
            evidence_status,
        ),
        (
            "Answer",
            (
                "Streaming answer text"
                if has_answer
                else "Waiting to synthesize the response"
            ),
            "active" if has_answer else "pending",
        ),
    ]
    summary = _streaming_summary(has_route, has_evidence, has_answer)
    return (
        "<details class='answer-reasoning-block "
        "answer-reasoning-block--streaming' open aria-busy='true'>"
        "<summary><span class='answer-reasoning-icon' aria-hidden='true'></span>"
        "<span class='answer-reasoning-title answer-reasoning-shimmer'>Thinking</span>"
        f"<small>{html.escape(summary)}</small></summary>"
        f"{_steps_html(steps)}</details>"
    )


def _render_completed_block(
    route_decision: dict[str, Any],
    retrieve_decision: dict[str, Any],
    verify_decision: dict[str, Any],
    evidence_bundle: dict[str, Any],
    stream_events: list[dict[str, Any]],
) -> str:
    route = _route_label(route_decision)
    evidence_items = _evidence_items(evidence_bundle)
    evidence_label = _evidence_count_label(evidence_items)
    retrieval = str(retrieve_decision.get("status") or "complete")
    verification = str(verify_decision.get("status") or "complete")
    action = str(verify_decision.get("action") or "answer")
    event_count = _agent_event_count(stream_events)
    meta = " - ".join(item for item in [route, verification, evidence_label] if item)
    steps = [
        ("Route", route, "done"),
        ("Retrieval", f"{retrieval} - {_modality_summary(evidence_items)}", "done"),
        ("Verification", f"{verification} / {action}", "done"),
    ]
    if event_count:
        steps.append(
            ("Controller", f"{event_count} execution events summarized", "done")
        )
    return (
        "<details class='answer-reasoning-block'>"
        "<summary><span class='answer-reasoning-icon' aria-hidden='true'></span>"
        "<span class='answer-reasoning-title'>Reasoning</span>"
        f"<small>{html.escape(meta)}</small></summary>"
        "<div class='answer-reasoning-content' aria-busy='false'>"
        f"{_steps_html(steps)}"
        "</div></details>"
    )


def _has_reasoning_summary(
    route_decision: dict[str, Any] | None,
    retrieve_decision: dict[str, Any] | None,
    verify_decision: dict[str, Any] | None,
    evidence_bundle: dict[str, Any] | None,
    stream_events: list[dict[str, Any]] | None,
) -> bool:
    evidence_items = _evidence_items(evidence_bundle or {})
    return any(
        [
            bool(route_decision),
            bool(retrieve_decision),
            bool(verify_decision),
            bool(evidence_items),
            bool(stream_events),
        ]
    )


def _steps_html(steps: list[tuple[str, str, str]]) -> str:
    items = "".join(
        "<li>"
        f"<span class='answer-reasoning-dot is-{html.escape(status)}'></span>"
        "<div>"
        f"<strong>{html.escape(title)}</strong>"
        f"<small>{html.escape(detail)}</small>"
        "</div></li>"
        for title, detail, status in steps
    )
    return f"<ol class='answer-reasoning-steps'>{items}</ol>"


def _route_label(route_decision: dict[str, Any]) -> str:
    route = str(route_decision.get("route") or route_decision.get("legacy_route") or "")
    route = route.strip()
    return _ROUTE_LABELS.get(route, route.replace("_", " ").title() or "Route ready")


def _evidence_items(evidence_bundle: dict[str, Any]) -> list[dict[str, Any]]:
    items = evidence_bundle.get("items") if isinstance(evidence_bundle, dict) else []
    return [item for item in items or [] if isinstance(item, dict)]


def _evidence_count_label(items: list[dict[str, Any]]) -> str:
    count = len(items)
    if count == 1:
        return "1 evidence item"
    return f"{count} evidence items"


def _modality_summary(items: list[dict[str, Any]]) -> str:
    labels = []
    for item in items:
        modality = str(item.get("modality") or "").strip()
        label = _MODALITY_LABELS.get(modality, modality.replace("_", " ").title())
        if label and label not in labels:
            labels.append(label)
    return ", ".join(labels) or "Evidence pending"


def _agent_event_count(stream_events: list[dict[str, Any]]) -> int:
    count = 0
    for event in stream_events:
        content = event.get("content") if isinstance(event, dict) else None
        if isinstance(content, dict) and str(content.get("mara_channel") or ""):
            count += 1
    return count


def _streaming_summary(has_route: bool, has_evidence: bool, has_answer: bool) -> str:
    if has_answer:
        return "Writing answer"
    if has_evidence:
        return "Reviewing sources"
    if has_route:
        return "Retrieving evidence"
    return "Working through sources"


def _has_channel(stream_events: list[dict[str, Any]], channel: str) -> bool:
    return any(
        isinstance(event, dict) and event.get("channel") == channel
        for event in stream_events
    )


def _has_mara_channel(stream_events: list[dict[str, Any]], channel: str) -> bool:
    for event in stream_events:
        if not isinstance(event, dict):
            continue
        content = event.get("content")
        if isinstance(content, dict) and content.get("mara_channel") == channel:
            return True
    return False
