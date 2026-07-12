from __future__ import annotations

import html
from pathlib import Path
from typing import Any

import gradio as gr
from ktem.docqa.artifact_models import ARTIFACT_LABELS

from . import studio_artifact_results as _artifact_results
from .studio_callback_identity import DIRECT_CALL_REQUEST, resolve_page_user_id

_ARTIFACT_LABELS = ARTIFACT_LABELS
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


def render_studio_artifacts_html(artifact: dict[str, Any] | None = None) -> str:
    return _artifact_results.render_studio_artifacts_html(artifact)


def render_conversation_studio_results_html(
    conversation_id: str | None,
    fallback_artifact: dict[str, Any] | None = None,
    *,
    user_id: Any,
) -> str:
    return _artifact_results.render_conversation_studio_results_html(
        conversation_id,
        fallback_artifact,
        user_id=user_id,
    )


def render_studio_artifact_viewer_html(artifact: dict[str, Any] | None) -> str:
    return _artifact_results.render_studio_artifact_viewer_html(artifact)


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


def render_conversation_notebook_panel_html(
    conversation_id: str | None,
    *,
    user_id: Any,
    allow_public: bool = True,
) -> str:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()
    from ktem.docqa import _runtime_notebook as notebook_service

    try:
        notebook = notebook_service.get_notebook(
            conversation_id,
            user_id=user_id,
            allow_public=allow_public,
        )
    except notebook_service.NotebookAccessError:
        return render_notebook_panel_html()
    return render_notebook_panel_html(notebook)


def render_conversation_notebook_update(
    conversation_id: str | None,
    *,
    user_id: Any,
):
    import gradio as gr

    return (
        gr.update(visible=False),
        render_conversation_notebook_panel_html(conversation_id, user_id=user_id),
    )


def render_conversation_notebook_root(
    page: Any,
    conversation_id: str | None,
    request: gr.Request = DIRECT_CALL_REQUEST,
):
    user_id = resolve_page_user_id(page, request)
    return render_conversation_notebook_update(conversation_id, user_id=user_id)


def delete_latest_artifact_update(
    conversation_id: str | None,
    *,
    user_id: Any,
) -> str:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()

    from ktem.docqa import _runtime_notebook as notebook_service

    notebook = notebook_service.get_notebook(conversation_id, user_id=user_id)
    artifacts = [
        item for item in notebook.get("artifacts", []) if isinstance(item, dict)
    ]
    if not artifacts:
        return render_notebook_panel_html(notebook)

    artifact_id = str(artifacts[-1].get("artifact_id") or "").strip()
    if artifact_id:
        notebook_service.delete_artifact_from_conversation(
            conversation_id,
            artifact_id,
            user_id=user_id,
        )
    return render_conversation_notebook_panel_html(conversation_id, user_id=user_id)


def export_latest_artifact_update(
    conversation_id: str | None,
    export_format: str = "md",
    root_dir: str | Path | None = None,
    *,
    user_id: Any,
) -> str:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return render_notebook_panel_html()

    from ktem.docqa import _runtime_notebook as notebook_service
    from ktem.docqa.artifact_exports import export_artifact_to_path

    notebook = notebook_service.get_notebook(conversation_id, user_id=user_id)
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
        user_id=user_id,
        export_format=normalized_format,
        path=str(exported_path),
    )
    return render_conversation_notebook_panel_html(conversation_id, user_id=user_id)


def render_studio_trace_panel(
    reasoning_trace_html: str,
    artifact: dict[str, Any] | None = None,
) -> str:
    return render_studio_artifacts_html(artifact)


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


def _export_format(value: str | None) -> str:
    normalized = str(value or "md").lower().strip()
    return "md" if normalized == "markdown" else normalized


def _default_export_root() -> Path:
    from theflow.settings import settings as flowsettings

    return Path(getattr(flowsettings, "KH_APP_DATA_DIR", Path.cwd())) / (
        "mara_artifact_exports"
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


def _label(artifact_type: Any) -> str:
    value = str(artifact_type or "").strip()
    return _ARTIFACT_LABELS.get(value, value.replace("_", " ").title() or "Artifact")


def _snippet(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return html.escape(text)
    return html.escape(text[: limit - 1].rstrip() + "...")
