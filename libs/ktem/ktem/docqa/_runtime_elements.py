from __future__ import annotations

from typing import Any

from ktem.db.models import engine
from sqlalchemy import select
from sqlmodel import Session

from .multimodal_index import (
    ELEMENT_INDEX_RELATION_TYPE,
    element_records_from_documents,
    element_records_from_index_documents,
)


def element_index_records_for_selected_files(
    file_index: Any,
    selected_file_ids: list[str],
) -> list[dict[str, Any]]:
    file_ids = _unique(selected_file_ids)
    resources = _file_index_resources(file_index)
    persisted_docs = _documents_for_relation(
        resources,
        file_ids,
        ELEMENT_INDEX_RELATION_TYPE,
    )
    persisted_records = element_records_from_index_documents(persisted_docs)
    if persisted_records:
        return persisted_records
    docs = documents_for_selected_files(file_index, file_ids)
    return element_records_from_documents(docs)


def documents_for_selected_files(file_index: Any, selected_file_ids: list[str]):
    file_ids = _unique(selected_file_ids)
    resources = _file_index_resources(file_index)
    return _documents_for_relation(resources, file_ids, "document")


def _file_index_resources(file_index: Any) -> dict[str, Any]:
    if file_index is None:
        return {}
    return dict(getattr(file_index, "_resources", {}) or {})


def _documents_for_relation(
    resources: dict[str, Any],
    file_ids: list[str],
    relation_type: str,
):
    if not resources or not file_ids:
        return []

    index_table = resources.get("Index")
    docstore = resources.get("DocStore")
    if index_table is None or docstore is None:
        return []

    doc_ids = _relation_doc_ids_for_sources(index_table, file_ids, relation_type)
    if not doc_ids:
        return []

    docs = docstore.get(doc_ids)
    if docs is None:
        return []
    if not isinstance(docs, list):
        docs = [docs]
    return [doc for doc in docs if doc]


def _document_ids_for_sources(index_table: Any, source_ids: list[str]) -> list[str]:
    return _relation_doc_ids_for_sources(index_table, source_ids, "document")


def _relation_doc_ids_for_sources(
    index_table: Any,
    source_ids: list[str],
    relation_type: str,
) -> list[str]:
    with Session(engine) as session:
        stmt = select(index_table.target_id).where(
            index_table.source_id.in_(source_ids),
            index_table.relation_type == relation_type,
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
