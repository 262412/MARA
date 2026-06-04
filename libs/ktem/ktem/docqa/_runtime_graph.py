from __future__ import annotations

from typing import Any

from ._runtime_elements import documents_for_selected_files
from .graph_builder import local_graph_index_from_documents


def graph_context_for_selected_files(
    file_index: Any,
    selected_file_ids: list[str],
) -> dict[str, Any]:
    docs = documents_for_selected_files(file_index, selected_file_ids)
    graph_index = local_graph_index_from_documents(docs)
    if not graph_index.get("entities") and not graph_index.get("relations"):
        return {}
    return {"graph_index": graph_index}
