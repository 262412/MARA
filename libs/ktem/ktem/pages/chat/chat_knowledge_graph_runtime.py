from __future__ import annotations

import logging
from typing import Any

import gradio as gr
from ktem.preview.errors import PreviewAccessError

logger = logging.getLogger(__name__)


def refresh_graph(
    page: Any,
    conversation_id,
    graph_source_ids,
    focus_file_id,
    selected_file_ids,
    request,
):
    if not page.knowledge_graph:
        return gr.update(value=""), None, "Status: knowledge graph unavailable.", []
    source_scope = _source_scope(
        page, graph_source_ids, selected_file_ids, focus_file_id
    )
    user_id = page._resolve_persist_user_id("default", request)
    try:
        graph_view = _graph_view(
            page, conversation_id, source_scope, focus_file_id, user_id, False
        )
        if graph_view.get("status") == "stale":
            graph_view = _graph_view(
                page, conversation_id, source_scope, focus_file_id, user_id, True
            )
        return _graph_outputs(page, graph_view)
    except PreviewAccessError:
        raise
    except Exception as exc:
        logger.warning("Failed to refresh knowledge graph: %s", exc)
        return (
            gr.update(value=""),
            None,
            "Status: failed to load knowledge graph.",
            page._normalize_selected_file_ids(source_scope),
        )


def generate_graph(
    page: Any,
    conversation_id,
    graph_source_ids,
    focus_file_id,
    selected_file_ids,
    request,
):
    if not page.knowledge_graph:
        return gr.update(value=""), None, "Status: knowledge graph unavailable.", []
    source_scope = _source_scope(
        page, graph_source_ids, selected_file_ids, focus_file_id
    )
    user_id = page._resolve_persist_user_id("default", request)
    try:
        graph_view = _graph_view(
            page, conversation_id, source_scope, focus_file_id, user_id, True
        )
        return _graph_outputs(page, graph_view)
    except PreviewAccessError:
        raise
    except Exception as exc:
        logger.warning("Failed to generate knowledge graph: %s", exc)
        return (
            gr.update(value=""),
            None,
            "Status: failed to generate knowledge graph.",
            page._normalize_selected_file_ids(source_scope),
        )


def _source_scope(page, graph_source_ids, selected_file_ids, focus_file_id):
    return page._merge_unique_file_ids(
        page._normalize_selected_file_ids(graph_source_ids),
        page._normalize_selected_file_ids(selected_file_ids),
        [focus_file_id] if focus_file_id else [],
    )


def _graph_view(page, conversation_id, source_scope, focus_file_id, user_id, force):
    return page.knowledge_graph.get_graph_view(
        conversation_id=conversation_id,
        graph_source_ids=source_scope,
        focus_file_id=focus_file_id,
        force_rebuild=force,
        user_id=user_id,
    )


def _graph_outputs(page, graph_view):
    return (
        page._json_to_plot(graph_view),
        graph_view,
        f"Status: {graph_view.get('status_message', 'ready')}",
        graph_view.get("graph_source_ids", []),
    )
