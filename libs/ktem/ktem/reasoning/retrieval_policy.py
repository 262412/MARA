import os
from collections import OrderedDict
from copy import deepcopy
from typing import Any, Iterable

from kotaemon.base import RetrievedDocument


def apply_retrieval_policy(
    retrieved_docs: Iterable[RetrievedDocument],
    qa_scope: str = "document",
    active_file_id: str = "",
    active_file_name: str = "",
    page_number: Any = None,
    selected_text: str = "",
    graph_context: dict | None = None,
    top_k: int | None = None,
) -> list[RetrievedDocument]:
    docs = list(retrieved_docs)
    graph_context = graph_context if isinstance(graph_context, dict) else {}

    graph_related_file_ids = [
        str(item or "").strip()
        for item in list(graph_context.get("related_file_ids", []) or [])
        if str(item or "").strip()
    ]
    graph_support_pages = graph_context.get("support_pages", {}) or {}
    graph_support_chunk_ids = graph_context.get("support_chunk_ids", {}) or {}

    active_file_id = str(active_file_id or "")
    active_file_name = str(active_file_name or "")
    active_file_name_norm = _normalize_file_name(active_file_name)

    def is_active_file_doc(doc: RetrievedDocument) -> bool:
        if not active_file_name and not active_file_id:
            return True

        doc_file_id = str(doc.metadata.get("file_id", "") or "")
        if active_file_id and doc_file_id:
            return doc_file_id == active_file_id

        if not active_file_name:
            return True

        doc_file_name = _normalize_file_name(doc.metadata.get("file_name", ""))
        return bool(doc_file_name) and doc_file_name == active_file_name_norm

    def is_current_page_doc(doc: RetrievedDocument) -> bool:
        if page_number is None or page_number == "":
            return True

        page_label = doc.metadata.get("page_label", None)
        if page_label is None:
            return False

        try:
            return int(page_label) == int(page_number)
        except Exception:
            return False

    def is_graph_related_doc(doc: RetrievedDocument) -> bool:
        if not graph_related_file_ids:
            return False

        doc_file_id = str(doc.metadata.get("file_id", "") or "")
        if doc_file_id and doc_file_id not in graph_related_file_ids:
            return False

        if doc_file_id:
            allowed_pages = [
                str(item).strip()
                for item in list(graph_support_pages.get(doc_file_id, []) or [])
                if str(item).strip()
            ]
            allowed_chunks = [
                str(item).strip()
                for item in list(graph_support_chunk_ids.get(doc_file_id, []) or [])
                if str(item).strip()
            ]

            if allowed_pages:
                page_label = str(doc.metadata.get("page_label", "") or "").strip()
                if page_label and page_label not in allowed_pages:
                    return False

            if allowed_chunks:
                doc_id = str(getattr(doc, "doc_id", "") or "").strip()
                if doc_id and doc_id not in allowed_chunks:
                    return False

        return True

    if qa_scope == "multi_document":
        scoped_docs = _round_robin_by_file(docs)
    else:
        page_docs = []
        if qa_scope == "page" and page_number:
            page_docs = [
                doc
                for doc in docs
                if is_active_file_doc(doc) and is_current_page_doc(doc)
            ]

        active_file_docs = []
        if qa_scope in {"page", "document"}:
            active_file_docs = [doc for doc in docs if is_active_file_doc(doc)]

        graph_docs = []
        if graph_related_file_ids:
            graph_docs = [doc for doc in docs if is_graph_related_doc(doc)]

        if page_docs:
            scoped_docs = page_docs
        elif active_file_docs:
            scoped_docs = active_file_docs
        elif graph_docs:
            scoped_docs = graph_docs
        else:
            scoped_docs = docs

    if top_k is not None:
        scoped_docs = scoped_docs[:top_k]

    if selected_text:
        scoped_docs = _apply_selected_text(
            scoped_docs,
            selected_text=selected_text,
            active_file_id=active_file_id,
            active_file_name=active_file_name,
        )

    return scoped_docs


def _normalize_file_name(file_name: str) -> str:
    return os.path.basename(str(file_name or "")).lower()


def _round_robin_by_file(docs: list[RetrievedDocument]) -> list[RetrievedDocument]:
    per_file: OrderedDict[str, list[RetrievedDocument]] = OrderedDict()
    for doc in docs:
        file_key = str(doc.metadata.get("file_id", "") or "").strip()
        if not file_key:
            file_key = _normalize_file_name(doc.metadata.get("file_name", ""))
        if not file_key:
            file_key = f"__doc_{len(per_file)}"
        per_file.setdefault(file_key, []).append(doc)

    balanced = []
    while any(per_file.values()):
        for bucket in per_file.values():
            if bucket:
                balanced.append(bucket.pop(0))
    return balanced


def _apply_selected_text(
    scoped_docs: list[RetrievedDocument],
    selected_text: str,
    active_file_id: str,
    active_file_name: str,
) -> list[RetrievedDocument]:
    selected_text_norm = " ".join(selected_text.lower().split())
    selected_filtered_docs = []
    for doc in scoped_docs:
        doc_text = (doc.text or "") if hasattr(doc, "text") else ""
        doc_text_norm = " ".join(doc_text.lower().split())
        if selected_text_norm in doc_text_norm:
            selected_filtered_docs.append(doc)

    if selected_filtered_docs:
        return [_doc_with_only_selected_text(selected_filtered_docs[0], selected_text)]
    if scoped_docs:
        return [_doc_with_only_selected_text(scoped_docs[0], selected_text)]

    return [
        RetrievedDocument(
            text=selected_text,
            metadata={
                "file_id": active_file_id,
                "file_name": active_file_name,
            },
        )
    ]


def _doc_with_only_selected_text(
    doc: RetrievedDocument, selected_text: str
) -> RetrievedDocument:
    selected_doc = deepcopy(doc)
    try:
        selected_doc.text = selected_text
    except Exception:
        pass
    try:
        selected_doc.content = selected_text
    except Exception:
        pass
    return selected_doc
