from __future__ import annotations

from typing import Any

import gradio as gr

from .studio_artifacts import (
    render_controller_trace_html,
    render_conversation_notebook_panel_html,
    render_conversation_studio_results_html,
    render_studio_artifact_viewer_html,
)


def generation_panel_outputs(
    page: Any,
    response: Any,
    *,
    chat_state: dict,
    fallback_conversation_id: str,
    fallback_active_file_id: str,
    fallback_page_number: int,
):
    messages = list(getattr(response, "messages", []) or [])
    latest_prompt, latest_answer = _latest_exchange(messages, response)
    answer_html = page._generate_answer_panel_html(
        messages[:-1],
        latest_prompt,
        latest_answer,
        is_thinking=False,
    )
    references_html = str(getattr(response, "references_html", "") or "")
    trace_html = page._render_reasoning_trace_html(
        latest_prompt,
        references_html,
        answer_html,
        getattr(response, "active_file_id", "") or fallback_active_file_id or "",
        getattr(response, "page_number", None) or fallback_page_number,
        getattr(response, "artifact", None),
    ) + render_controller_trace_html(
        route_decision=getattr(response, "route_decision", {}),
        retrieve_decision=getattr(response, "retrieve_decision", {}),
        verify_decision=getattr(response, "verify_decision", {}),
        evidence_bundle=getattr(response, "evidence_bundle", {}),
    )
    conversation_id = getattr(response, "conversation_id", fallback_conversation_id)
    artifact = getattr(response, "artifact", None)
    plot_html = render_conversation_studio_results_html(conversation_id, artifact)
    viewer_html = render_studio_artifact_viewer_html(artifact)
    return (
        conversation_id,
        messages,
        list(getattr(response, "retrieval_messages", []) or []),
        list(getattr(response, "plot_history", []) or []),
        getattr(response, "state", None) or chat_state,
        answer_html,
        page._render_citations_card_html(references_html),
        trace_html,
        render_conversation_notebook_panel_html(conversation_id),
        list(getattr(response, "graph_source_ids", []) or []),
        gr.update(visible=True, value=plot_html),
        {"html": viewer_html},
    )


def latest_notebook_artifact(conversation_id: str) -> dict[str, Any] | None:
    from ktem.docqa import _runtime_notebook as notebook_service

    notebook = notebook_service.get_notebook(conversation_id)
    artifacts = [
        item for item in notebook.get("artifacts", []) if isinstance(item, dict)
    ]
    return dict(artifacts[-1]) if artifacts else None


def unique_text(values: Any) -> list[str]:
    output: list[str] = []
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output


def _latest_exchange(messages: list[Any], response: Any) -> tuple[str, str]:
    if messages:
        latest = messages[-1]
        if isinstance(latest, (list, tuple)) and len(latest) >= 2:
            return str(latest[0] or ""), str(latest[1] or "")
    return "", str(getattr(response, "answer", "") or "")
