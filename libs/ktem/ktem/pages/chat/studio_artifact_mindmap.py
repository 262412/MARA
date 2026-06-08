from __future__ import annotations

from typing import Any, Callable

from .studio_artifact_generation import build_studio_artifact_prompt
from .studio_artifacts import (
    render_controller_trace_html,
    render_conversation_notebook_panel_html,
)


def generate_studio_mindmap_outputs(
    page: Any,
    values: dict[str, Any],
    *,
    save_artifact: Callable[..., dict[str, Any]],
) -> tuple[Any, ...]:
    conversation_id = str(values["conversation_id"] or "").strip()
    if not getattr(page, "knowledge_graph", None):
        raise ValueError("Knowledge graph service is unavailable.")

    source_ids = _source_ids_for_scope(
        values["qa_scope"],
        active_file_id=values["active_file_id"],
        selecteds=values.get("selecteds", ()),
    )
    if not source_ids:
        raise ValueError("Select at least one source before generating a mind map.")

    graph_view = _build_graph_view(page, values, conversation_id, source_ids)
    graph_source_ids = _unique_text(graph_view.get("graph_source_ids") or source_ids)
    prompt = _mindmap_prompt(values)
    artifact = _save_mindmap_artifact(
        save_artifact,
        conversation_id=conversation_id,
        graph_view=graph_view,
        graph_source_ids=graph_source_ids,
        prompt=prompt,
        values=values,
    )
    answer = "Interactive mind map generated."
    messages = [*list(values["chat_history"] or []), (prompt, answer)]
    answer_html = page._generate_answer_panel_html(
        messages[:-1],
        prompt,
        answer,
        is_thinking=False,
    )
    trace_html = _mindmap_trace_html(
        page,
        values=values,
        graph_view=graph_view,
        prompt=prompt,
        answer_html=answer_html,
        artifact=artifact,
    )
    html = str(graph_view.get("html") or "")
    return (
        conversation_id,
        messages,
        [],
        [],
        values["chat_state"],
        answer_html,
        page._render_citations_card_html(""),
        trace_html,
        render_conversation_notebook_panel_html(conversation_id),
        graph_source_ids,
        page._json_to_plot(graph_view),
        {"html": html},
    )


def _build_graph_view(
    page: Any,
    values: dict[str, Any],
    conversation_id: str,
    source_ids: list[str],
) -> dict[str, Any]:
    return page.knowledge_graph.get_graph_view(
        conversation_id=conversation_id,
        graph_source_ids=source_ids,
        focus_file_id=str(values["active_file_id"] or "").strip(),
        force_rebuild=True,
    )


def _mindmap_prompt(values: dict[str, Any]) -> str:
    return build_studio_artifact_prompt(
        "mindmap",
        prompt=values["prompt"],
        output_format=values["output_format"],
        difficulty=values["difficulty"],
        count=values["count"],
        language=values["language"],
    )


def _save_mindmap_artifact(
    save_artifact: Callable[..., dict[str, Any]],
    *,
    conversation_id: str,
    graph_view: dict[str, Any],
    graph_source_ids: list[str],
    prompt: str,
    values: dict[str, Any],
) -> dict[str, Any]:
    return save_artifact(
        conversation_id=conversation_id,
        payload=_mindmap_payload(graph_view, graph_source_ids),
        title="Interactive Mind Map",
        prompt=prompt,
        source_scope=_source_scope(
            values["qa_scope"],
            graph_source_ids,
            values["page_number"],
        ),
        generation={
            "adapter": "knowledge_graph_service",
            "parameters": {"force_rebuild": True},
        },
    )


def _mindmap_trace_html(
    page: Any,
    *,
    values: dict[str, Any],
    graph_view: dict[str, Any],
    prompt: str,
    answer_html: str,
    artifact: dict[str, Any],
) -> str:
    return page._render_reasoning_trace_html(
        prompt,
        "",
        answer_html,
        values["active_file_id"],
        values["page_number"],
        artifact,
    ) + render_controller_trace_html(
        route_decision={"route": "graph_global"},
        retrieve_decision={"status": graph_view.get("status") or "ready"},
        verify_decision={"status": "supported", "action": "generate"},
        evidence_bundle={"items": [{"evidence_level": "graph", "modality": "graph"}]},
    )


def save_studio_mindmap_artifact(
    *,
    conversation_id: str,
    payload: dict[str, Any],
    title: str,
    prompt: str,
    source_scope: dict[str, Any],
    generation: dict[str, Any],
) -> dict[str, Any]:
    from ktem.docqa import _runtime_notebook as notebook_service

    return notebook_service.save_artifact_to_conversation(
        conversation_id,
        artifact_type="mindmap",
        payload=payload,
        title=title,
        prompt=prompt,
        source_scope=source_scope,
        generation=generation,
    )


def _source_ids_for_scope(
    scope: Any,
    *,
    active_file_id: Any,
    selecteds: tuple[Any, ...],
) -> list[str]:
    selected_ids = _flatten_text(selecteds[-1] if selecteds else [])
    focus_id = str(active_file_id or "").strip()
    normalized_scope = _scope_mode(scope)
    if normalized_scope == "multi_document":
        return _unique_text([focus_id, *selected_ids])
    return _unique_text([focus_id, *(selected_ids[:1] if not focus_id else [])])


def _source_scope(
    scope: Any, source_ids: list[str], page_number: Any
) -> dict[str, Any]:
    output: dict[str, Any] = {
        "mode": _scope_mode(scope),
        "source_ids": list(source_ids),
    }
    if page_number not in (None, ""):
        output["page"] = page_number
    return output


def _mindmap_payload(
    graph_view: dict[str, Any],
    source_ids: list[str],
) -> dict[str, Any]:
    return {
        "interactive": True,
        "status": graph_view.get("status") or "ready",
        "status_message": graph_view.get("status_message") or "ready",
        "graph_source_ids": list(source_ids),
        "graph": graph_view.get("graph") or {},
        "support_pages": graph_view.get("support_pages") or {},
        "support_chunk_ids": graph_view.get("support_chunk_ids") or {},
    }


def _scope_mode(value: Any) -> str:
    normalized = str(value or "page").strip().lower().replace("-", "_")
    if normalized in {"multi", "multi_doc", "multi_docs"}:
        return "multi_document"
    if normalized in {"doc", "whole_document", "full_document"}:
        return "document"
    return normalized or "page"


def _flatten_text(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        output: list[str] = []
        for item in value:
            output.extend(_flatten_text(item))
        return output
    text = str(value or "").strip()
    return [text] if text else []


def _unique_text(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output
