from __future__ import annotations

import logging
import re
import threading
import unicodedata
from typing import Any

from kotaemon.base import Document, RetrievedDocument

from .retrieval_identity import stable_scored_documents

logger = logging.getLogger("kotaemon.indices.vectorindex")


def embedding_contract(embedding: Any) -> dict[str, object]:
    def declared_value(*names: str) -> str:
        for name in names:
            value = getattr(embedding, name, None)
            if value not in (None, ""):
                return str(value)
        return "not_declared"

    return {
        "backend": f"{type(embedding).__module__}.{type(embedding).__qualname__}",
        "model": declared_value(
            "model", "model_name", "azure_deployment", "deployment_name", "engine"
        ),
        "revision": declared_value("revision", "model_revision"),
        "precision": declared_value("precision", "dtype", "torch_dtype"),
        "determinism": declared_value("determinism", "deterministic"),
    }


def normalized_chunk_text(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).strip()
    return re.sub(r"\s+", " ", normalized)


def sparse_retrieval_score(document: Document) -> float:
    value = dict(document.metadata or {}).get("_sparse_retrieval_score")
    try:
        return float(value) if value is not None else -1.0
    except (TypeError, ValueError):
        return -1.0


def retrieve_candidates(
    retriever: Any,
    *,
    text: str | Document,
    query: str,
    scope: list[str] | None,
    dense_top_k: int,
    sparse_top_k: int,
    rrf_k: int,
    query_kwargs: dict[str, Any],
) -> list[RetrievedDocument]:
    if retriever.retrieval_mode == "vector":
        return _retrieve_vector(retriever, text, scope, dense_top_k, query_kwargs)
    if retriever.retrieval_mode == "text":
        return _retrieve_text(retriever, query, scope, sparse_top_k)
    if retriever.retrieval_mode == "hybrid":
        return _retrieve_hybrid(
            retriever,
            text,
            query,
            scope,
            dense_top_k,
            sparse_top_k,
            rrf_k,
            query_kwargs,
        )
    return []


def _retrieve_vector(
    retriever: Any,
    text: str | Document,
    scope: list[str] | None,
    dense_top_k: int,
    query_kwargs: dict[str, Any],
) -> list[RetrievedDocument]:
    emb = retriever.embedding(text)[0].embedding
    _, scores, ids = retriever.vector_store.query(
        embedding=emb, top_k=dense_top_k, doc_ids=scope, **query_kwargs
    )
    docs = retriever.doc_store.get(ids)
    result = []
    for doc, score in zip(docs, scores):
        retrieved = RetrievedDocument(**doc.to_dict(), score=score)
        retrieved.retrieval_metadata = {
            **retrieved.retrieval_metadata,
            "retrieval_path": ["vector"],
            "vector_score": score,
        }
        result.append(retrieved)
    return stable_scored_documents(result)


def _retrieve_text(
    retriever: Any,
    query: str,
    scope: list[str] | None,
    sparse_top_k: int,
) -> list[RetrievedDocument]:
    docs = []
    if scope:
        docs = retriever.doc_store.query(query, top_k=sparse_top_k, doc_ids=scope)
    result = []
    for doc in docs:
        sparse_score = sparse_retrieval_score(doc)
        retrieved = RetrievedDocument(**doc.to_dict(), score=sparse_score)
        retrieved.retrieval_metadata = {
            **retrieved.retrieval_metadata,
            "retrieval_path": ["text"],
            "sparse_score": sparse_score,
        }
        result.append(retrieved)
    return stable_scored_documents(result)


def _retrieve_hybrid(
    retriever: Any,
    text: str | Document,
    query: str,
    scope: list[str] | None,
    dense_top_k: int,
    sparse_top_k: int,
    rrf_k: int,
    query_kwargs: dict[str, Any],
) -> list[RetrievedDocument]:
    emb = retriever.embedding(text)[0].embedding
    vs_docs: list[Document] = []
    vs_ids: list[str] = []
    vs_scores: list[float] = []

    def query_vectorstore():
        nonlocal vs_docs, vs_scores, vs_ids
        _, vs_scores, vs_ids = retriever.vector_store.query(
            embedding=emb, top_k=dense_top_k, doc_ids=scope, **query_kwargs
        )
        if vs_ids:
            vs_docs = retriever.doc_store.get(vs_ids)

    ds_docs: list[Document] = []

    def query_docstore():
        nonlocal ds_docs
        if scope:
            ds_docs = retriever.doc_store.query(
                query, top_k=sparse_top_k, doc_ids=scope
            )

    vs_query_thread = threading.Thread(target=query_vectorstore)
    ds_query_thread = threading.Thread(target=query_docstore)
    vs_query_thread.start()
    ds_query_thread.start()
    vs_query_thread.join()
    ds_query_thread.join()

    ds_result = []
    for doc in ds_docs:
        sparse_score = sparse_retrieval_score(doc)
        retrieved = RetrievedDocument(**doc.to_dict(), score=sparse_score)
        retrieved.retrieval_metadata = {
            **retrieved.retrieval_metadata,
            "retrieval_path": ["text"],
            "sparse_score": sparse_score,
        }
        ds_result.append(retrieved)

    vs_result = []
    for doc, score in zip(vs_docs, vs_scores):
        retrieved = RetrievedDocument(**doc.to_dict(), score=score)
        retrieved.retrieval_metadata = {
            **retrieved.retrieval_metadata,
            "retrieval_path": ["vector"],
            "vector_score": score,
        }
        vs_result.append(retrieved)

    result = retriever._reciprocal_rank_fuse(
        stable_scored_documents(vs_result),
        stable_scored_documents(ds_result),
        k=rrf_k,
    )
    logger.debug("Got %s from vectorstore", len(vs_docs))
    logger.debug("Got %s from docstore", len(ds_docs))
    return result
