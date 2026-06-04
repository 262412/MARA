from __future__ import annotations

from typing import Any

from ktem.db.models import engine
from sqlalchemy import select
from sqlmodel import Session

from .multimodal_index import element_records_from_documents


def element_index_records_for_selected_files(
    file_index: Any,
    selected_file_ids: list[str],
) -> list[dict[str, Any]]:
    docs = documents_for_selected_files(file_index, selected_file_ids)
    return element_records_from_documents(docs)


def documents_for_selected_files(file_index: Any, selected_file_ids: list[str]):
    file_ids = _unique(selected_file_ids)
    if file_index is None or not file_ids:
        return []

    resources = dict(getattr(file_index, "_resources", {}) or {})
    index_table = resources.get("Index")
    docstore = resources.get("DocStore")
    if index_table is None or docstore is None:
        return []

    doc_ids = _document_ids_for_sources(index_table, file_ids)
    if not doc_ids:
        return []

    docs = docstore.get(doc_ids)
    if docs is None:
        return []
    if not isinstance(docs, list):
        docs = [docs]
    return [doc for doc in docs if doc]


def _document_ids_for_sources(index_table: Any, source_ids: list[str]) -> list[str]:
    with Session(engine) as session:
        stmt = select(index_table.target_id).where(
            index_table.source_id.in_(source_ids),
            index_table.relation_type == "document",
        )
        rows = session.execute(stmt).all()
    return _unique(row[0] for row in rows)


def _unique(values: Any) -> list[str]:
    output: list[str] = []
    for value in values or []:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output
