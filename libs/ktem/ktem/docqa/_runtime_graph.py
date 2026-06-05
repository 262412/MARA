from __future__ import annotations

from typing import Any

from . import _runtime_elements
from ._runtime_elements import documents_for_selected_files
from .graph_builder import (
    GRAPH_INDEX_RELATION_TYPE,
    graph_index_from_index_documents,
    local_graph_index_from_documents,
)


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
