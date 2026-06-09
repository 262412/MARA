from __future__ import annotations

from typing import Any

from .studio_artifacts import (
    render_conversation_notebook_panel_html,
    render_notebook_panel_html,
)


def save_latest_artifact_note_update(conversation_id: str | None) -> str:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()

    from ktem.docqa import _runtime_notebook as notebook_service
    from ktem.docqa.artifact_service import build_artifact_note_fields

    notebook = notebook_service.get_notebook(conversation_id)
    artifacts = [
        item for item in notebook.get("artifacts", []) if isinstance(item, dict)
    ]
    if not artifacts:
        return render_notebook_panel_html(notebook)

    fields = build_artifact_note_fields(artifacts[-1])
    notebook_service.save_answer_note_to_conversation(
        conversation_id,
        title=fields["title"],
        answer=fields["text"],
        citation_refs=fields["citation_refs"],
    )
    return render_conversation_notebook_panel_html(conversation_id)


def save_latest_answer_note_update(
    conversation_id: str | None,
    chat_history: Any,
    retrieval_history: Any,
) -> str:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()
    answer = _latest_chat_answer(chat_history)
    if not answer:
        return render_conversation_notebook_panel_html(conversation_id)

    from ktem.docqa import _runtime_notebook as notebook_service

    notebook_service.save_answer_note_to_conversation(
        conversation_id,
        title="Latest answer",
        answer=answer,
        citation_refs=_latest_retrieval_refs(retrieval_history),
    )
    return render_conversation_notebook_panel_html(conversation_id)


def save_manual_note_update(
    conversation_id: str | None,
    title: str | None,
    text: str | None,
) -> str:
    conversation_id = str(conversation_id or "").strip()
    note_text = str(text or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()
    if not note_text:
        return render_conversation_notebook_panel_html(conversation_id)

    from ktem.docqa import _runtime_notebook as notebook_service

    notebook_service.add_note_to_conversation(
        conversation_id,
        title=str(title or "").strip(),
        text=note_text,
    )
    return render_conversation_notebook_panel_html(conversation_id)


def convert_note_to_source_update(
    runtime: Any,
    conversation_id: str | None,
    note_id: str | None,
) -> str:
    conversation_id = str(conversation_id or "").strip()
    note_id = str(note_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()
    if not note_id:
        return render_conversation_notebook_panel_html(conversation_id)

    from ktem.docqa import _runtime_notebook as notebook_service

    notebook = notebook_service.get_notebook(conversation_id)
    note = _find_notebook_note(notebook, note_id)
    if note is None:
        return render_notebook_panel_html(notebook)
    source_path = notebook_service.materialize_note_source(conversation_id, note)
    result = runtime.index_paths([source_path], reindex=False)
    if getattr(result, "failures", []):
        return render_notebook_panel_html(notebook)
    notebook_service.record_note_indexed_source_to_conversation(
        conversation_id,
        note_id,
        source_ids=_indexed_source_ids(result),
        source_path=source_path,
    )
    return render_conversation_notebook_panel_html(conversation_id)


def _latest_chat_answer(chat_history: Any) -> str:
    if not isinstance(chat_history, list):
        return ""
    for item in reversed(chat_history):
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            answer = str(item[1] or "").strip()
            if answer:
                return answer
    return ""


def _latest_retrieval_refs(retrieval_history: Any) -> list[str]:
    if not isinstance(retrieval_history, list):
        return []
    for item in reversed(retrieval_history):
        text = str(item or "").strip()
        if text:
            return [text]
    return []


def _find_notebook_note(
    notebook: dict[str, Any],
    note_id: str,
) -> dict[str, Any] | None:
    for note in notebook.get("notes", []):
        if isinstance(note, dict) and str(note.get("note_id") or "") == note_id:
            return dict(note)
    return None


def _indexed_source_ids(result: Any) -> list[str]:
    source_ids: list[str] = []
    for item in getattr(result, "successes", []) or []:
        if isinstance(item, dict) and str(item.get("source_id") or "").strip():
            source_ids.append(str(item["source_id"]).strip())
    return source_ids
