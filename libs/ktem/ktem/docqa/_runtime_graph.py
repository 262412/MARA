from __future__ import annotations

from typing import Any

from ktem.preview.context import preview_access_for_user

from . import _runtime_elements
from ._runtime_elements import documents_for_selected_files
from .graph_builder import (
    GRAPH_INDEX_RELATION_TYPE,
    graph_index_from_index_documents,
    local_graph_index_from_documents,
)
from .knowledge_graph_lifetime import GraphCacheRequest


def read_conversation_cache(runtime, conversation_id, user_id, engine):
    graph = runtime.knowledge_graph
    if not conversation_id or not graph:
        return None
    principal = runtime._resolve_user_id(user_id)
    if runtime.load_session(conversation_id, user_id=principal) is None:
        raise PermissionError("Graph conversation is unavailable")
    state = graph._load_cached_state(conversation_id)
    if state.get("conversation_id") != conversation_id or not state.get("graph"):
        return None
    sources = graph._load_sources(list(state.get("manifest") or {}), user_id=principal)
    access = preview_access_for_user(graph._app, principal)
    request = GraphCacheRequest(
        graph._storage_dir,
        engine,
        graph._index,
        conversation_id,
        access.user_id,
        sources,
        owner_required=access.owner_required,
        register=False,
    )
    with request.current():
        latest = graph._load_cached_state(conversation_id)
        return latest if latest == state and request.cache_matches(latest) else None


def graph_context_for_selected_files(
    file_index: Any,
    selected_file_ids: list[str],
) -> dict[str, Any]:
    persisted_docs = _documents_for_relation(
        file_index,
        selected_file_ids,
        GRAPH_INDEX_RELATION_TYPE,
    )
    persisted_graph_index = graph_index_from_index_documents(persisted_docs)
    if _has_graph_index(persisted_graph_index):
        return {"graph_index": persisted_graph_index}

    docs = documents_for_selected_files(file_index, selected_file_ids)
    graph_index = local_graph_index_from_documents(docs)
    if not _has_graph_index(graph_index):
        return {}
    return {"graph_index": graph_index}


def _documents_for_relation(
    file_index: Any,
    selected_file_ids: list[str],
    relation_type: str,
):
    resources = _runtime_elements._file_index_resources(file_index)
    return _runtime_elements._documents_for_relation(
        resources,
        selected_file_ids,
        relation_type,
    )


def _has_graph_index(graph_index: dict[str, Any]) -> bool:
    return bool(graph_index.get("entities") or graph_index.get("relations"))
