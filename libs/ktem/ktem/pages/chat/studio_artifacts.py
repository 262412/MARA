from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from ktem.docqa.artifact_models import ARTIFACT_LABELS

_ARTIFACT_LABELS = ARTIFACT_LABELS
_ARTIFACT_GROUPS = (
    ("Quick Generate", ("study_guide", "quiz", "flashcards", "mindmap")),
    ("Reports", ("briefing_doc", "faq", "timeline", "custom_report")),
    ("Visual / Export", ("data_table", "infographic", "slide_outline", "slide_deck")),
    ("Media", ("audio_overview", "video_overview")),
)
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
        title = _snippet(section.get("title"))
        summary = _snippet(section.get("summary"))
        if title or summary:
            lines.append(" - ".join(item for item in [title, summary] if item))
        for slide in section.get("slides", [])[:3]:
            title = _snippet(slide.get("title"))
            bullets = [_snippet(item) for item in slide.get("bullets", [])[:2]]
            lines.append(" - ".join(item for item in [title, *bullets] if item))
    return lines


def render_studio_artifacts_html(artifact: dict[str, Any] | None = None) -> str:
    if not artifact:
        groups = "".join(
            "<section>"
            f"<strong>{html.escape(group)}</strong>"
            + "".join(
                f"<span>{html.escape(_label(item))}</span>" for item in artifact_types
            )
            + "</section>"
            for group, artifact_types in _ARTIFACT_GROUPS
        )
        return (
            "<div class='studio-artifacts-card studio-artifacts-card--empty'>"
            "<div><strong>Studio Artifacts</strong><span>Waiting</span></div>"
            f"{groups}"
            "</div>"
        )
    artifact_type = _label(artifact.get("type"))
    payload = _artifact_payload(artifact)
    status = str(artifact.get("status") or payload.get("status") or "ready")
    status_label = status.replace("_", " ").title()
    title = str(artifact.get("title") or artifact_type)
    lines = "".join(f"<li>{line}</li>" for line in _artifact_lines(payload) if line)
    evidence_count = _artifact_evidence_count(artifact, payload)
    detail_sections = _artifact_detail_sections(artifact)
    return (
        f"<div class='studio-artifacts-card studio-artifacts-card--{status}'>"
        f"<div><strong>{html.escape(artifact_type)}</strong>"
        f"<span>{html.escape(status_label)} - {evidence_count} cited evidence</span></div>"
        f"<h4>{html.escape(title)}</h4>"
        f"<ul>{lines}</ul>"
        f"{detail_sections}"
        "</div>"
    )


def _artifact_payload(artifact: dict[str, Any]) -> dict[str, Any]:
    payload = artifact.get("payload")
    return dict(payload) if isinstance(payload, dict) else artifact


def _artifact_evidence_count(
    artifact: dict[str, Any],
    payload: dict[str, Any],
) -> int:
    cited_evidence = artifact.get("cited_evidence") or payload.get("cited_evidence")
    citations = artifact.get("citations")
    if isinstance(cited_evidence, list):
        return len(cited_evidence)
    return len(citations) if isinstance(citations, list) else 0


def _artifact_detail_sections(artifact: dict[str, Any]) -> str:
    sections = [
        _artifact_content_section(artifact),
        _artifact_prompt_section(artifact),
        _artifact_scope_section(artifact),
        _artifact_citation_section(artifact),
        _artifact_export_section(artifact),
        _artifact_generation_section(artifact),
        _artifact_action_section(artifact),
    ]
    return "".join(section for section in sections if section)


def _artifact_content_section(artifact: dict[str, Any]) -> str:
    payload = _artifact_payload(artifact)
    if not payload:
        return ""
    content = html.escape(json.dumps(payload, ensure_ascii=False, indent=2))
    return f"<section><strong>Full Content</strong><pre>{content}</pre></section>"


def _artifact_prompt_section(artifact: dict[str, Any]) -> str:
    prompt = _snippet(artifact.get("prompt"), limit=180)
    return (
        f"<section><strong>Prompt</strong><p>{prompt}</p></section>" if prompt else ""
    )


def _artifact_scope_section(artifact: dict[str, Any]) -> str:
    scope = artifact.get("source_scope")
    if not isinstance(scope, dict):
        return ""
    parts = [
        str(scope.get("mode") or "").strip(),
        f"page {scope.get('page')}" if scope.get("page") else "",
        ", ".join(str(item) for item in scope.get("source_ids", []) if item),
    ]
    text = _snippet(" - ".join(item for item in parts if item), limit=180)
    return (
        f"<section><strong>Source Scope</strong><p>{text}</p></section>" if text else ""
    )


def _artifact_citation_section(artifact: dict[str, Any]) -> str:
    citations = artifact.get("citations")
    if not isinstance(citations, list) or not citations:
        return ""
    items = "".join(f"<li>{_citation_label(item)}</li>" for item in citations[:5])
    return f"<section><strong>Citations</strong><ul>{items}</ul></section>"


def _citation_label(citation: Any) -> str:
    if not isinstance(citation, dict):
        return _snippet(citation, limit=120)
    source = str(
        citation.get("source_name")
        or citation.get("source_id")
        or citation.get("citation_id")
        or ""
    ).strip()
    page = str(citation.get("page_label") or "").strip()
    return html.escape(f"{source} p.{page}" if source and page else source)


def _artifact_export_section(artifact: dict[str, Any]) -> str:
    exports = artifact.get("exports")
    if not isinstance(exports, list) or not exports:
        return ""
    items = "".join(f"<li>{_export_label(item)}</li>" for item in exports[:5])
    return f"<section><strong>Exports</strong><ul>{items}</ul></section>"


def _export_label(export: Any) -> str:
    if not isinstance(export, dict):
        return _snippet(export, limit=120)
    export_format = str(export.get("format") or "").strip()
    path = str(export.get("path") or "").strip()
    return html.escape(" - ".join(item for item in [export_format, path] if item))


def _artifact_generation_section(artifact: dict[str, Any]) -> str:
    generation = artifact.get("generation")
    if not isinstance(generation, dict):
        return ""
    error = _snippet(generation.get("error"), limit=180)
    return (
        f"<section><strong>Generation</strong><p>{error}</p></section>" if error else ""
    )


def _artifact_action_section(artifact: dict[str, Any]) -> str:
    copy_text = html.escape(
        json.dumps(_artifact_payload(artifact), ensure_ascii=False),
        quote=True,
    )
    buttons = (
        "<button type='button' data-copy-text='"
        f"{copy_text}' onclick='navigator.clipboard.writeText(this.dataset.copyText)'>"
        "Copy</button>"
    )
    actions = ["Save as Note", "Export", "Delete", "Regenerate"]
    buttons += "".join(f"<button>{html.escape(action)}</button>" for action in actions)
    return f"<section class='studio-artifacts-actions'>{buttons}</section>"


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
    artifacts = _artifact_panel_entries(notebook.get("artifacts"))
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


def _artifact_panel_entries(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    entries: list[str] = []
    for artifact in values[:3]:
        if not isinstance(artifact, dict):
            continue
        label = _label(artifact.get("type"))
        exports = artifact.get("exports")
        latest_export = exports[-1] if isinstance(exports, list) and exports else {}
        path = latest_export.get("path") if isinstance(latest_export, dict) else ""
        suffix = Path(str(path)).name if path else ""
        entries.append(" - ".join(item for item in [label, suffix] if item))
    return entries


def render_conversation_notebook_update(conversation_id: str | None):
    import gradio as gr

    return (
        gr.update(visible=False),
        render_conversation_notebook_panel_html(conversation_id),
    )


def delete_latest_artifact_update(conversation_id: str | None) -> str:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()

    from ktem.docqa import _runtime_notebook as notebook_service

    notebook = notebook_service.get_notebook(conversation_id)
    artifacts = [
        item for item in notebook.get("artifacts", []) if isinstance(item, dict)
    ]
    if not artifacts:
        return render_notebook_panel_html(notebook)

    artifact_id = str(artifacts[-1].get("artifact_id") or "").strip()
    if artifact_id:
        notebook_service.delete_artifact_from_conversation(conversation_id, artifact_id)
    return render_conversation_notebook_panel_html(conversation_id)


def export_latest_artifact_update(
    conversation_id: str | None,
    export_format: str = "md",
    root_dir: str | Path | None = None,
) -> str:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()

    from ktem.docqa import _runtime_notebook as notebook_service
    from ktem.docqa.artifact_exports import export_artifact_to_path

    notebook = notebook_service.get_notebook(conversation_id)
    artifacts = [
        item for item in notebook.get("artifacts", []) if isinstance(item, dict)
    ]
    if not artifacts:
        return render_notebook_panel_html(notebook)

    artifact = artifacts[-1]
    artifact_id = str(artifact.get("artifact_id") or "artifact").strip()
    normalized_format = _export_format(export_format)
    export_root = Path(root_dir) if root_dir is not None else _default_export_root()
    output_path = export_root / conversation_id / f"{artifact_id}.{normalized_format}"
    exported_path = export_artifact_to_path(
        artifact,
        export_format=normalized_format,
        output_path=output_path,
    )
    notebook_service.record_artifact_export_to_conversation(
        conversation_id,
        artifact_id,
        export_format=normalized_format,
        path=str(exported_path),
    )
    return render_conversation_notebook_panel_html(conversation_id)


def _export_format(value: str | None) -> str:
    normalized = str(value or "md").lower().strip()
    return "md" if normalized == "markdown" else normalized


def _default_export_root() -> Path:
    from theflow.settings import settings as flowsettings

    return Path(getattr(flowsettings, "KH_APP_DATA_DIR", Path.cwd())) / (
        "mara_artifact_exports"
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
