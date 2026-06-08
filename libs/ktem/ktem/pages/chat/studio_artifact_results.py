from __future__ import annotations

import html
from typing import Any

from ktem.docqa.artifact_models import ARTIFACT_LABELS

_ARTIFACT_LABELS = ARTIFACT_LABELS
_ARTIFACT_GROUPS = (
    ("Quick Generate", ("study_guide", "quiz", "flashcards", "mindmap")),
    ("Reports", ("briefing_doc", "faq", "timeline", "custom_report")),
    ("Visual / Export", ("data_table", "infographic", "slide_outline", "slide_deck")),
    ("Media", ("audio_overview", "video_overview")),
)


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
    artifacts = artifact.get("artifacts")
    if isinstance(artifacts, list):
        normalized_artifacts = [item for item in artifacts if isinstance(item, dict)]
        return _artifact_list_html(
            normalized_artifacts,
            status=_artifact_list_status(normalized_artifacts),
        )
    artifact_type = _label(artifact.get("type"))
    payload = _artifact_payload(artifact)
    status = str(artifact.get("status") or payload.get("status") or "ready")
    title = str(artifact.get("title") or artifact_type)
    source_count = _artifact_source_count(artifact, payload)
    if status == "running":
        return _running_artifact_html(artifact_type, title, source_count)
    return _artifact_list_html([artifact], source_count, status)


def render_conversation_studio_results_html(
    conversation_id: str | None,
    fallback_artifact: dict[str, Any] | None = None,
) -> str:
    artifacts = _conversation_artifacts(conversation_id)
    if not artifacts and isinstance(fallback_artifact, dict):
        artifacts = [fallback_artifact]
    return render_studio_artifacts_html({"artifacts": artifacts})


def render_studio_artifact_viewer_html(artifact: dict[str, Any] | None) -> str:
    artifact = artifact if isinstance(artifact, dict) else {}
    artifact_type = _label(artifact.get("type"))
    payload = _artifact_payload(artifact)
    title = str(artifact.get("title") or artifact_type)
    graph_html = str(payload.get("html") or payload.get("viewer_html") or "").strip()
    if str(artifact.get("type") or "") == "mindmap" and graph_html:
        return (
            "<div class='studio-artifact-viewer studio-artifact-viewer--mindmap' hidden>"
            f"{_open_graph_viewer_html(graph_html)}"
            "</div>"
        )
    body = _artifact_viewer_body(artifact, payload)
    return (
        "<div class='studio-artifact-viewer' hidden>"
        "<div class='studio-artifact-viewer__dialog'>"
        "<div class='studio-artifact-viewer__toolbar'>"
        f"<strong data-studio-artifact-title='true'>{html.escape(title)}</strong>"
        "<button type='button' "
        "onclick=\"this.closest('.studio-artifact-viewer').hidden = true\">"
        "Close</button>"
        "</div>"
        f"<div class='studio-artifact-viewer__body'>{body}</div>"
        "</div></div>"
    )


def _artifact_list_html(
    artifacts: list[dict[str, Any]],
    source_count: int | None = None,
    status: str = "ready",
) -> str:
    if not artifacts:
        return render_studio_artifacts_html(None)
    items = []
    for artifact in artifacts:
        payload = _artifact_payload(artifact)
        artifact_type = _label(artifact.get("type"))
        title = str(artifact.get("title") or artifact_type)
        item_status = str(artifact.get("status") or payload.get("status") or status)
        item_evidence_count = _artifact_evidence_count(artifact, payload)
        items.append(
            _artifact_result_row(
                artifact,
                artifact_type,
                title,
                item_status,
                item_evidence_count,
            )
        )
        items.append(render_studio_artifact_viewer_html(artifact))
    header_count = source_count
    if header_count is None:
        header_count = max(
            _artifact_source_count(item, _artifact_payload(item)) for item in artifacts
        )
    return (
        "<div class='studio-artifacts-card studio-artifacts-card--"
        f"{html.escape(status, quote=True)} studio-artifact-result-list'>"
        "<div><strong>Studio Results</strong>"
        f"<span>{html.escape(_artifact_result_count_label(len(artifacts), header_count))}</span></div>"
        f"{''.join(items)}"
        "</div>"
    )


def _artifact_result_count_label(result_count: int, source_count: int) -> str:
    result_word = "result" if result_count == 1 else "results"
    return f"{result_count} {result_word} - {_artifact_source_label(source_count)}"


def _artifact_list_status(artifacts: list[dict[str, Any]]) -> str:
    statuses = [
        str(item.get("status") or _artifact_payload(item).get("status") or "ready")
        for item in artifacts
    ]
    if any(status == "running" for status in statuses):
        return "running"
    if statuses and all(status == "failed" for status in statuses):
        return "failed"
    return "ready"


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


def _artifact_result_row(
    artifact: dict[str, Any],
    artifact_type: str,
    title: str,
    status: str,
    evidence_count: int,
) -> str:
    source_count = _artifact_source_count(artifact, _artifact_payload(artifact))
    meta = _artifact_result_meta(source_count, status, evidence_count)
    share_text = html.escape(_artifact_copy_text(artifact), quote=True)
    return (
        "<div class='studio-artifact-result-row' "
        'onclick="this.nextElementSibling.hidden = false">'
        f"{_artifact_result_icon(artifact_type)}"
        "<div>"
        f"<strong data-studio-artifact-title='true'>{html.escape(title)}</strong>"
        f"<small>{html.escape(meta)}</small>"
        "</div>"
        "<button type='button' class='studio-artifact-result-menu' "
        'onclick="event.stopPropagation(); '
        'this.nextElementSibling.hidden = !this.nextElementSibling.hidden">'
        "More</button>"
        "<div class='studio-artifact-result-actions' hidden "
        "onclick='event.stopPropagation()'>"
        f"{_row_action_button('rename', 'Rename')}"
        f"{_row_action_button('share', 'Share', share_text)}"
        f"{_row_action_button('prompt-sources', 'View Prompt and Sources')}"
        f"{_row_action_button('delete', 'Delete')}"
        "</div>"
        f"<span class='studio-artifact-result-type'>{html.escape(artifact_type)}</span>"
        "</div>"
    )


def _artifact_result_icon(artifact_type: str) -> str:
    return (
        "<span class='studio-artifact-result-icon' "
        f"data-artifact-type='{html.escape(artifact_type, quote=True)}' "
        "aria-hidden='true'>"
        "<svg class='studio-artifact-result-icon__svg' viewBox='0 0 24 24'>"
        "<path d='M5 4.5h10l4 4V19a1.5 1.5 0 0 1-1.5 1.5h-12A1.5 1.5 0 0 1 4 19V6a1.5 1.5 0 0 1 1.5-1.5Z'/>"
        "<path d='M15 4.5V9h4'/>"
        "<path d='M8 13h8M8 16h5'/>"
        "</svg></span>"
    )


def _row_action_button(
    action: str,
    label: str,
    share_text: str = "",
) -> str:
    data_share = f" data-share-text='{share_text}'" if share_text else ""
    return (
        "<button type='button' "
        f"data-studio-action='{html.escape(action, quote=True)}'{data_share} "
        f'onclick="{_row_action_js(action)}">'
        f"{html.escape(label)}</button>"
    )


def _row_action_js(action: str) -> str:
    if action == "rename":
        return (
            "event.stopPropagation(); "
            "const row=this.closest('.studio-artifact-result-row'); "
            "const title=row.querySelector('[data-studio-artifact-title]'); "
            "const next=window.prompt('Rename artifact', title ? title.textContent.trim() : ''); "
            "if(next){ title.textContent=next; "
            "const viewer=row.nextElementSibling; "
            "const viewerTitle=viewer ? viewer.querySelector('[data-studio-artifact-title]') : null; "
            "if(viewerTitle) viewerTitle.textContent=next; }"
        )
    if action == "share":
        return (
            "event.stopPropagation(); "
            "navigator.clipboard.writeText(this.dataset.shareText || window.location.href);"
        )
    if action == "prompt-sources":
        return (
            "event.stopPropagation(); "
            "const row=this.closest('.studio-artifact-result-row'); "
            "const viewer=row.nextElementSibling; "
            "if(viewer){ viewer.hidden=false; "
            "const target=viewer.querySelector('[data-studio-prompt-sources]') || viewer.querySelector('section'); "
            "if(target) target.scrollIntoView({block:'start'}); }"
        )
    return (
        "event.stopPropagation(); "
        "const row=this.closest('.studio-artifact-result-row'); "
        "const viewer=row.nextElementSibling; "
        "if(viewer) viewer.remove(); row.remove();"
    )


def _artifact_result_meta(
    source_count: int,
    status: str,
    evidence_count: int,
) -> str:
    parts = [_artifact_source_label(source_count)]
    if evidence_count:
        parts.append(f"{evidence_count} cited evidence")
    if status and status != "ready":
        parts.append(status.replace("_", " ").title())
    return " - ".join(parts)


def _running_artifact_html(
    artifact_type: str,
    title: str,
    source_count: int,
) -> str:
    return (
        "<div class='studio-artifacts-card studio-artifacts-card--running'>"
        "<div class='studio-artifact-running-row'>"
        "<span class='studio-artifact-spinner' aria-hidden='true'></span>"
        "<div>"
        f"<strong>Generating {html.escape(artifact_type)}...</strong>"
        f"<p>{html.escape(_artifact_source_label(source_count))}</p>"
        "</div></div>"
        f"<span>{html.escape(title)}</span>"
        "</div>"
    )


def _artifact_source_count(
    artifact: dict[str, Any],
    payload: dict[str, Any],
) -> int:
    explicit = artifact.get("source_count") or payload.get("source_count")
    if explicit not in (None, ""):
        try:
            return max(0, int(str(explicit)))
        except (TypeError, ValueError):
            return 0
    source_scope = artifact.get("source_scope")
    if isinstance(source_scope, dict):
        return len(list(source_scope.get("source_ids") or []))
    graph_source_ids = payload.get("graph_source_ids")
    return (
        len(list(graph_source_ids or [])) if isinstance(graph_source_ids, list) else 0
    )


def _artifact_source_label(source_count: int) -> str:
    if source_count == 1:
        return "Based on 1 source"
    return f"Based on {source_count} sources"


def _artifact_viewer_body(
    artifact: dict[str, Any],
    payload: dict[str, Any],
) -> str:
    graph_html = str(payload.get("html") or payload.get("viewer_html") or "").strip()
    if str(artifact.get("type") or "") == "mindmap" and graph_html:
        return _open_graph_viewer_html(graph_html)
    preview = _artifact_preview_section(payload)
    details = _artifact_detail_sections(artifact)
    if details:
        return f"<div class='studio-artifact-viewer__sections'>{preview}{details}</div>"
    return preview or "<p>No result details available.</p>"


def _artifact_preview_section(payload: dict[str, Any]) -> str:
    lines = "".join(f"<li>{line}</li>" for line in _artifact_lines(payload) if line)
    return (
        f"<section><strong>Result Preview</strong><ul>{lines}</ul></section>"
        if lines
        else ""
    )


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


def _artifact_detail_sections(artifact: dict[str, Any]) -> str:
    sections = [
        _artifact_prompt_section(artifact),
        _artifact_scope_section(artifact),
        _artifact_citation_section(artifact),
        _artifact_export_section(artifact),
        _artifact_generation_section(artifact),
        _artifact_action_section(artifact),
    ]
    return "".join(section for section in sections if section)


def _artifact_prompt_section(artifact: dict[str, Any]) -> str:
    prompt = _snippet(artifact.get("prompt"), limit=180)
    return (
        f"<section data-studio-prompt-sources='true'><strong>Prompt</strong><p>{prompt}</p></section>"
        if prompt
        else ""
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
        f"<section data-studio-prompt-sources='true'><strong>Source Scope</strong><p>{text}</p></section>"
        if text
        else ""
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
    copy_text = html.escape(_artifact_copy_text(artifact), quote=True)
    buttons = _viewer_action_button("copy", "Copy", copy_text)
    buttons += _viewer_action_button("rename", "Rename")
    buttons += _viewer_action_button("share", "Share", copy_text)
    buttons += _viewer_action_button("prompt-sources", "View Prompt and Sources")
    buttons += _viewer_action_button("delete", "Delete")
    return f"<section class='studio-artifacts-actions'>{buttons}</section>"


def _viewer_action_button(
    action: str,
    label: str,
    copy_text: str = "",
) -> str:
    data_copy = f" data-copy-text='{copy_text}'" if copy_text else ""
    return (
        "<button type='button' "
        f"data-studio-action='{html.escape(action, quote=True)}'{data_copy} "
        f'onclick="{_viewer_action_js(action)}">'
        f"{html.escape(label)}</button>"
    )


def _viewer_action_js(action: str) -> str:
    if action == "copy":
        return (
            "event.stopPropagation(); "
            "navigator.clipboard.writeText(this.dataset.copyText || '');"
        )
    if action == "rename":
        return (
            "event.stopPropagation(); "
            "const viewer=this.closest('.studio-artifact-viewer'); "
            "const title=viewer.querySelector('[data-studio-artifact-title]'); "
            "const next=window.prompt('Rename artifact', title ? title.textContent.trim() : ''); "
            "if(next){ title.textContent=next; "
            "const row=viewer.previousElementSibling; "
            "const rowTitle=row ? row.querySelector('[data-studio-artifact-title]') : null; "
            "if(rowTitle) rowTitle.textContent=next; }"
        )
    if action == "share":
        return (
            "event.stopPropagation(); "
            "navigator.clipboard.writeText(this.dataset.copyText || window.location.href);"
        )
    if action == "prompt-sources":
        return (
            "event.stopPropagation(); "
            "const viewer=this.closest('.studio-artifact-viewer'); "
            "const target=viewer.querySelector('[data-studio-prompt-sources]') || viewer.querySelector('section'); "
            "if(target) target.scrollIntoView({block:'start'});"
        )
    return (
        "event.stopPropagation(); "
        "const viewer=this.closest('.studio-artifact-viewer'); "
        "const row=viewer.previousElementSibling; "
        "if(row) row.remove(); viewer.remove();"
    )


def _artifact_copy_text(artifact: dict[str, Any]) -> str:
    title = str(artifact.get("title") or _label(artifact.get("type")))
    prompt = str(artifact.get("prompt") or "").strip()
    return "\n".join(item for item in [title, prompt] if item)


def _open_graph_viewer_html(graph_html: str) -> str:
    visible_graph = graph_html.replace(
        " data-kg-viewer-overlay='true' hidden",
        " data-kg-viewer-overlay='true'",
    )
    return f"<div class='studio-kg-viewer-scope'>{visible_graph}</div>"


def _conversation_artifacts(conversation_id: str | None) -> list[dict[str, Any]]:
    conversation_id = str(conversation_id or "").strip()
    if not conversation_id:
        return []
    from ktem.db.models import Conversation, engine
    from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
    from sqlmodel import Session, select

    with Session(engine) as session:
        row = session.exec(
            select(Conversation).where(Conversation.id == conversation_id)
        ).one_or_none()
    if row is None:
        return []
    data_source = row.data_source if isinstance(row.data_source, dict) else {}
    notebook = data_source.get(NOTEBOOK_KEY, {})
    artifacts = notebook.get("artifacts") if isinstance(notebook, dict) else []
    return [item for item in artifacts or [] if isinstance(item, dict)]


def _label(artifact_type: Any) -> str:
    value = str(artifact_type or "").strip()
    return _ARTIFACT_LABELS.get(value, value.replace("_", " ").title() or "Artifact")


def _snippet(value: Any, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return html.escape(text)
    return html.escape(text[: limit - 1].rstrip() + "...")
