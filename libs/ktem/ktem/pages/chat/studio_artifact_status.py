from __future__ import annotations

from typing import Any

import gradio as gr
from ktem.docqa.artifact_models import ARTIFACT_LABELS

from .studio_artifacts import (
    render_conversation_notebook_panel_html,
    render_conversation_studio_results_html,
    render_studio_artifact_viewer_html,
    render_studio_artifacts_html,
)


def render_studio_artifact_running_update(
    artifact_type: str,
    graph_source_ids: Any = None,
) -> tuple[Any, Any, Any, Any]:
    source_count = len(list(graph_source_ids or [])) if graph_source_ids else 0
    html = render_studio_artifacts_html(
        {
            "type": str(artifact_type or "study_guide"),
            "status": "running",
            "source_count": source_count,
        }
    )
    return (
        html,
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
    )


def render_studio_artifact_regenerating_update(conversation_id: str) -> str:
    normalized_id = str(conversation_id or "").strip()
    artifact = _latest_notebook_artifact(normalized_id) if normalized_id else None
    artifact_type = artifact.get("type") if artifact else "study_guide"
    return render_studio_artifacts_html(
        {
            "type": str(artifact_type or "study_guide"),
            "status": "running",
        }
    )


def save_failed_studio_artifact(
    *,
    conversation_id: str,
    artifact_type: str,
    prompt: str,
    qa_scope: str,
    page_number: Any,
    active_file_id: str,
    note_ids: Any,
    error: str,
) -> dict[str, Any]:
    normalized_id = str(conversation_id or "").strip()
    normalized_type = str(artifact_type or "study_guide").strip() or "study_guide"
    title = f"{ARTIFACT_LABELS.get(normalized_type, normalized_type)} Failed"
    payload = {"error": error}
    generation = {"adapter": "studio", "error": error}
    artifact: dict[str, Any] = {
        "type": normalized_type,
        "status": "failed",
        "title": title,
        "payload": payload,
        "generation": generation,
    }
    if not normalized_id:
        return artifact

    from ktem.docqa import _runtime_notebook as notebook_service

    return notebook_service.save_artifact_to_conversation(
        normalized_id,
        artifact_type=normalized_type,
        payload=payload,
        title=title,
        status="failed",
        prompt=str(prompt or "").strip(),
        source_scope=_failed_source_scope(
            qa_scope=qa_scope,
            page_number=page_number,
            active_file_id=active_file_id,
            note_ids=note_ids,
        ),
        generation=generation,
    )


def failed_studio_artifact_panel_outputs(
    page: Any,
    *,
    failed_artifact: dict[str, Any],
    conversation_id: str,
    chat_history: list,
    chat_state: dict,
) -> tuple[Any, ...]:
    plot_html = render_conversation_studio_results_html(
        conversation_id, failed_artifact
    )
    viewer_html = render_studio_artifact_viewer_html(failed_artifact)
    return (
        conversation_id,
        list(chat_history or []),
        [],
        [],
        chat_state,
        "",
        page._render_citations_card_html(""),
        plot_html,
        render_conversation_notebook_panel_html(conversation_id),
        [],
        gr.update(visible=True, value=plot_html),
        {"html": viewer_html},
    )


def failed_generation_studio_artifact_outputs(
    page: Any,
    *,
    conversation_id: str,
    artifact_type: str,
    prompt: str,
    qa_scope: str,
    page_number: Any,
    active_file_id: str,
    note_ids: Any,
    error: str,
    chat_history: list,
    chat_state: dict,
) -> tuple[Any, ...]:
    failed_artifact = save_failed_studio_artifact(
        conversation_id=conversation_id,
        artifact_type=artifact_type,
        prompt=prompt,
        qa_scope=qa_scope,
        page_number=page_number,
        active_file_id=active_file_id,
        note_ids=note_ids,
        error=error,
    )
    return failed_studio_artifact_panel_outputs(
        page,
        failed_artifact=failed_artifact,
        conversation_id=conversation_id,
        chat_history=chat_history,
        chat_state=chat_state,
    )


def failed_regeneration_studio_artifact_outputs(
    page: Any,
    *,
    conversation_id: str,
    artifact: dict[str, Any],
    active_file_id: str,
    error: str,
    chat_history: list,
    chat_state: dict,
) -> tuple[Any, ...]:
    source_scope = artifact.get("source_scope") if isinstance(artifact, dict) else {}
    source_scope = source_scope if isinstance(source_scope, dict) else {}
    return failed_generation_studio_artifact_outputs(
        page,
        conversation_id=conversation_id,
        artifact_type=str(artifact.get("type") or "study_guide"),
        prompt=str(artifact.get("prompt") or ""),
        qa_scope=str(source_scope.get("mode") or "document"),
        page_number=source_scope.get("page") or 1,
        active_file_id=active_file_id,
        note_ids=source_scope.get("note_ids", []),
        error=error,
        chat_history=chat_history,
        chat_state=chat_state,
    )


def _failed_source_scope(
    *,
    qa_scope: str,
    page_number: Any,
    active_file_id: str,
    note_ids: Any,
) -> dict[str, Any]:
    mode = str(qa_scope or "document").replace("-", "_")
    scope: dict[str, Any] = {"mode": mode, "source_ids": _unique_text([active_file_id])}
    if mode == "page" and page_number not in (None, ""):
        scope["page"] = page_number
    selected_notes = _unique_text(
        note_ids if isinstance(note_ids, list) else str(note_ids or "").split(",")
    )
    if selected_notes:
        scope["note_ids"] = selected_notes
    return scope


def _latest_notebook_artifact(conversation_id: str) -> dict[str, Any] | None:
    from ktem.docqa import _runtime_notebook as notebook_service

    notebook = notebook_service.get_notebook(conversation_id)
    artifacts = [
        item for item in notebook.get("artifacts", []) if isinstance(item, dict)
    ]
    return dict(artifacts[-1]) if artifacts else None


def _unique_text(values: Any) -> list[str]:
    output: list[str] = []
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output
