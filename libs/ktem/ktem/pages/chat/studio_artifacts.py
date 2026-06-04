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
_ROUTE_LABELS = {
    "direct": "Direct",
    "doc_text": "Document",
    "doc_page_image": "Visual Page",
    "doc_element": "Document Element",
    "graph_global": "Graph",
    "hybrid": "Hybrid",
    "abstain": "Abstain",
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


def render_controller_trace_html(
    *,
    route_decision: dict[str, Any] | None = None,
    retrieve_decision: dict[str, Any] | None = None,
    verify_decision: dict[str, Any] | None = None,
    evidence_bundle: dict[str, Any] | None = None,
) -> str:
    route_decision = route_decision if isinstance(route_decision, dict) else {}
    retrieve_decision = retrieve_decision if isinstance(retrieve_decision, dict) else {}
    verify_decision = verify_decision if isinstance(verify_decision, dict) else {}
    evidence_bundle = evidence_bundle if isinstance(evidence_bundle, dict) else {}
    route = str(route_decision.get("route") or "doc_text")
    route_label = _ROUTE_LABELS.get(route, route.replace("_", " ").title())
    retrieval_status = str(retrieve_decision.get("status") or "pending")
    verify_status = str(verify_decision.get("status") or "pending")
    action = str(verify_decision.get("action") or "generate")
    evidence_items = list(evidence_bundle.get("items") or [])
    modality_labels = _modality_labels(evidence_items)
    unsupported = _unsupported_claim_lines(verify_decision)
    evidence_preview = _evidence_preview_lines(evidence_items)
    verified_citations = _verified_citation_lines(verify_decision)
    graph_note = (
        "<p>Includes graph-level evidence with source backrefs.</p>"
        if any(item.get("evidence_level") == "graph" for item in evidence_items)
        else ""
    )
    return (
        "<div class='controller-trace-card'>"
        f"<div><strong>{html.escape(route_label)}</strong>"
        f"<span>{html.escape(action.title())}</span></div>"
        "<ol>"
        f"<li><strong>Route</strong><small>{html.escape(route_label)}</small></li>"
        f"<li><strong>Evidence</strong><small>{html.escape(retrieval_status)}"
        f" - {html.escape(', '.join(modality_labels) or 'Waiting')}</small></li>"
        f"<li><strong>Verification</strong><small>{html.escape(verify_status)}</small></li>"
        "</ol>"
        f"{unsupported}{evidence_preview}{verified_citations}{graph_note}</div>"
    )


def _modality_labels(evidence_items: list[dict[str, Any]]) -> list[str]:
    labels: list[str] = []
    for item in evidence_items:
        modality = str(item.get("modality") or "").strip()
        label = _ROUTE_LABELS.get(
            "doc_page_image" if modality == "page_image" else modality,
            modality.replace("_", " ").title(),
        )
        if label and label not in labels:
            labels.append(label)
    return labels


def _unsupported_claim_lines(verify_decision: dict[str, Any]) -> str:
    claims = [
        _snippet(claim, limit=120)
        for claim in verify_decision.get("unsupported_claims") or []
        if str(claim or "").strip()
    ]
    if not claims:
        return ""
    items = "".join(f"<li>{claim}</li>" for claim in claims)
    return f"<section><strong>Unsupported Claims</strong><ul>{items}</ul></section>"


def _evidence_preview_lines(evidence_items: list[dict[str, Any]]) -> str:
    lines = []
    for item in evidence_items[:3]:
        source = _evidence_source_label(item)
        summary = _snippet(
            item.get("caption") or item.get("text") or item.get("ocr_text"),
            limit=120,
        )
        if source or summary:
            lines.append(f"<li><small>{source}</small>{summary}</li>")
    if not lines:
        return ""
    return (
        "<section><strong>Evidence Preview</strong>"
        f"<ul>{''.join(lines)}</ul></section>"
    )


def _verified_citation_lines(verify_decision: dict[str, Any]) -> str:
    citations = [
        _snippet(citation, limit=80)
        for citation in verify_decision.get("verified_citations") or []
        if str(citation or "").strip()
    ]
    if not citations:
        return ""
    items = "".join(f"<li>{citation}</li>" for citation in citations[:5])
    return f"<section><strong>Verified Citations</strong><ul>{items}</ul></section>"


def _evidence_source_label(item: dict[str, Any]) -> str:
    source = str(item.get("source_name") or item.get("source_id") or "").strip()
    page = str(item.get("page_label") or "").strip()
    label = f"{source} p.{page}" if source and page else source
    return html.escape(label)
