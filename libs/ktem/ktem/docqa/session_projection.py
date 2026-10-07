"""Interpret loaded conversation records without database or runtime services."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.utils.conversation import sync_retrieval_n_message

from . import _runtime_selection as _selection
from ._runtime_models import DocQASession, DocQASessionSummary


def session_summary(row: Any) -> DocQASessionSummary:
    data_source = dict(row.data_source or {})
    messages = data_source.get("messages", []) or []
    graph_source_ids = _selection.normalize_selected_file_ids(
        data_source.get("graph_source_ids", [])
    )
    return DocQASessionSummary(
        conversation_id=row.id,
        name=row.name,
        message_count=len(messages),
        graph_source_count=len(graph_source_ids),
        origin=str(data_source.get("origin", "") or ""),
        is_public=bool(row.is_public),
        date_created=row.date_created,
        date_updated=row.date_updated,
    )


def loaded_session(row: Any, *, default_state: dict[str, Any]) -> DocQASession:
    data_source = dict(row.data_source or {})
    messages = [tuple(item) for item in (data_source.get("messages", []) or [])]
    retrieval_messages = list(data_source.get("retrieval_messages", []) or [])
    plot_history = list(data_source.get("plot_history", []) or [])
    state = deepcopy(data_source.get("state", default_state) or default_state)
    selected_mapping = dict(data_source.get("selected", {}) or {})
    graph_source_ids = _selection.normalize_selected_file_ids(
        data_source.get("graph_source_ids", [])
    )
    if not graph_source_ids:
        graph_source_ids = _selection.extract_selected_ids_from_data_source(data_source)

    return DocQASession(
        conversation_id=row.id,
        name=row.name,
        user_id=row.user,
        is_public=bool(row.is_public),
        data_source=data_source,
        messages=messages,
        retrieval_messages=sync_retrieval_n_message(
            [list(item) for item in messages], retrieval_messages
        ),
        plot_history=plot_history,
        state=state,
        selected_mapping=selected_mapping,
        graph_source_ids=graph_source_ids,
        origin=str(data_source.get("origin", "") or ""),
        date_created=row.date_created,
        date_updated=row.date_updated,
    )
