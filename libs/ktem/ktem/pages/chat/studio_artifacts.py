from __future__ import annotations

import html
from typing import Any

_ARTIFACT_LABELS = {
    "study_guide": "Study Guide",
    "quiz": "Quiz",
    "flashcards": "Flashcards",
    "mindmap": "Mind Map",
    "slide_outline": "Slide Outline",
}


def extract_mara_artifact(response: Any) -> dict[str, Any] | None:
    if getattr(response, "channel", None) != "debug":
        return None
    content = getattr(response, "content", None)
    if not isinstance(content, dict):
        return None
    if content.get("mara_channel") != "artifact":
        return None
    payload = content.get("payload")
    return dict(payload) if isinstance(payload, dict) else None


def _label(artifact_type: Any) -> str:
    value = str(artifact_type or "").strip()
    return _ARTIFACT_LABELS.get(value, value.replace("_", " ").title() or "Artifact")


def _snippet(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return html.escape(text)
    return html.escape(text[: limit - 1].rstrip() + "...")


def _artifact_lines(artifact: dict[str, Any]) -> list[str]:
    if artifact.get("overview"):
        return [_snippet(artifact.get("overview"))]
    if artifact.get("cards"):
        return [_snippet(card.get("back")) for card in artifact["cards"][:3]]
    if artifact.get("multiple_choice"):
        return [
            _snippet(item.get("question")) for item in artifact["multiple_choice"][:3]
        ]
    if artifact.get("nodes"):
        return [_snippet(node.get("label")) for node in artifact["nodes"][:5]]
    lines: list[str] = []
    for section in artifact.get("sections", [])[:3]:
        for slide in section.get("slides", [])[:3]:
            title = _snippet(slide.get("title"))
            bullets = [_snippet(item) for item in slide.get("bullets", [])[:2]]
            lines.append(" - ".join(item for item in [title, *bullets] if item))
    return lines


def render_studio_artifacts_html(artifact: dict[str, Any] | None = None) -> str:
    if not artifact:
        labels = "".join(
            f"<span>{html.escape(label)}</span>" for label in _ARTIFACT_LABELS.values()
        )
        return (
            "<div class='studio-artifacts-card studio-artifacts-card--empty'>"
            "<div><strong>Studio Artifacts</strong><span>Waiting</span></div>"
            f"<p>{labels}</p>"
            "</div>"
        )
    artifact_type = _label(artifact.get("type"))
    title = str(artifact.get("title") or artifact_type)
    lines = "".join(f"<li>{line}</li>" for line in _artifact_lines(artifact) if line)
    evidence_count = len(artifact.get("cited_evidence", []) or [])
    return (
        "<div class='studio-artifacts-card studio-artifacts-card--ready'>"
        f"<div><strong>{html.escape(artifact_type)}</strong>"
        f"<span>{evidence_count} cited evidence</span></div>"
        f"<h4>{html.escape(title)}</h4>"
        f"<ul>{lines}</ul>"
        "</div>"
    )


def _notebook_entries(values: Any, key: str) -> list[str]:
    if not isinstance(values, list):
        return []
    entries: list[str] = []
    for value in values[:3]:
        if isinstance(value, dict):
            value = value.get(key) or value.get("type") or value.get("artifact_id")
        text = _snippet(value, limit=90)
        if text:
            entries.append(text)
    return entries


def render_notebook_panel_html(notebook: dict[str, Any] | None = None) -> str:
    notebook = notebook if isinstance(notebook, dict) else {}
    source_ids = _notebook_entries(notebook.get("selected_source_ids"), "")
    notes = _notebook_entries(notebook.get("notes"), "title")
    artifacts = [
        _label(item) for item in _notebook_entries(notebook.get("artifacts"), "type")
    ]
    source_label = f"{len(source_ids)} selected" if source_ids else "No selection"
    note_label = f"{len(notes)} saved" if notes else "No notes"
    artifact_label = f"{len(artifacts)} saved" if artifacts else "No artifacts"
    rows = [
        ("Sources", source_label, "Source Guide", source_ids),
        ("Notes", note_label, "Saved Answers", notes),
        ("Artifacts", artifact_label, "Studio", artifacts),
    ]
    items = "".join(
        "<section>"
        f"<div><strong>{title}</strong><span>{status}</span></div>"
        f"<small>{action}</small>"
        f"<p>{', '.join(entries) if entries else 'Waiting'}</p>"
        "</section>"
        for title, status, action, entries in rows
    )
    return (
        "<div class='notebook-panel-card'>"
        "<div><strong>Research Notebook</strong><span>MARA</span></div>"
        f"{items}</div>"
    )


def render_conversation_notebook_panel_html(conversation_id: str | None) -> str:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()
    from ktem.db.models import Conversation, engine
    from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
    from sqlmodel import Session, select

    with Session(engine) as session:
        row = session.exec(
            select(Conversation).where(Conversation.id == conversation_id)
        ).one_or_none()
    if row is None:
        return render_notebook_panel_html()
    data_source = row.data_source if isinstance(row.data_source, dict) else {}
    notebook = data_source.get(NOTEBOOK_KEY, {})
    return render_notebook_panel_html(notebook if isinstance(notebook, dict) else {})


def render_conversation_notebook_update(conversation_id: str | None):
    import gradio as gr

    return (
        gr.update(visible=False),
        render_conversation_notebook_panel_html(conversation_id),
    )


def render_studio_trace_panel(
    reasoning_trace_html: str,
    artifact: dict[str, Any] | None = None,
) -> str:
    return str(reasoning_trace_html or "") + render_studio_artifacts_html(artifact)
