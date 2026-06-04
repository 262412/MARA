from __future__ import annotations

from typing import Any

ELEMENT_INDEX_RELATION_TYPE = "element_index"
DOCSTORE_RELATION_TYPES = {"document", ELEMENT_INDEX_RELATION_TYPE}


def is_docstore_relation_type(relation_type: str) -> bool:
    return relation_type in DOCSTORE_RELATION_TYPES


def docstore_batches_and_index_rows(
    index_row_cls: Any,
    file_id: str,
    chunks: list[Any],
) -> tuple[list[list[Any]], list[Any]]:
    element_index_docs = _element_index_docs_for_chunks(file_id, chunks)
    batches = [list(chunks)]
    if element_index_docs:
        batches.append(element_index_docs)

    rows = [
        index_row_cls(
            source_id=file_id,
            target_id=chunk.doc_id,
            relation_type="document",
        )
        for chunk in chunks
    ]
    rows.extend(
        index_row_cls(
            source_id=file_id,
            target_id=doc.doc_id,
            relation_type=ELEMENT_INDEX_RELATION_TYPE,
        )
        for doc in element_index_docs
    )
    return batches, rows


def _element_index_docs_for_chunks(file_id: str, chunks: list[Any]) -> list[Any]:
    from ktem.docqa.multimodal_index import element_index_documents_from_documents

    return element_index_documents_from_documents(file_id, chunks)
