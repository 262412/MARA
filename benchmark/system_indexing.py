from __future__ import annotations

import os
import time
from typing import Any

from kotaemon.indices import VectorIndexing
from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.storages import InMemoryDocumentStore, InMemoryVectorStore

from .schemas import BenchmarkDocument


def build_parsed_index(system: Any, document: BenchmarkDocument) -> Any:
    loaded, parse_seconds = _load_document(system, document)
    parsed_docs = loaded.documents
    index_docs = system._split_docs(parsed_docs)
    page_count, extracted_characters, non_text_count = _document_stats(parsed_docs)
    (
        doc_store,
        vector_store,
        embedding_cache_stats,
        indexing_status,
        index_seconds,
    ) = _build_stores(system, index_docs)
    from .system import ParsedIndex

    return ParsedIndex(
        document=document,
        parsed_documents=parsed_docs,
        index_documents=index_docs,
        page_count=page_count,
        extracted_characters=extracted_characters,
        non_text_count=non_text_count,
        parse_seconds=parse_seconds,
        index_seconds=index_seconds,
        doc_store=doc_store,
        vector_store=vector_store,
        parse_cache_stats=dict(loaded.stats),
        parse_cache_hit=loaded.cache_hit,
        embedding_cache_stats=embedding_cache_stats,
        indexing_status=indexing_status,
    )


def _load_document(system: Any, document: BenchmarkDocument) -> tuple[Any, float]:
    parse_start = time.perf_counter()
    loaded = load_data_with_parse_cache(
        system._get_reader(document.path),
        document.path,
        extra_info={
            "file_id": document.document_id,
            "collection_name": "benchmark",
        },
        cache_dir=system._parse_cache_dir(),
        reader_policy={
            "benchmark_reader_mode": system.config.reader_mode,
            "benchmark_cache_schema": 2,
            "benchmark_chunk_size": system.config.chunk_size,
            "benchmark_chunk_overlap": system.config.chunk_overlap,
            "benchmark_index_contract": os.environ.get(
                "MARA_BENCHMARK_INDEX_CONTRACT", "not_declared"
            ),
            "benchmark_embedding_contract": os.environ.get(
                "MARA_BENCHMARK_EMBEDDING_CONTRACT", "not_declared"
            ),
        },
    )
    return loaded, time.perf_counter() - parse_start


def _document_stats(parsed_docs: list[Any]) -> tuple[int, int, int]:
    unique_pages = {
        str(doc.metadata.get("page_label"))
        for doc in parsed_docs
        if doc.metadata.get("page_label") is not None
    }
    return (
        len(unique_pages) or 1,
        sum(len(doc.text or "") for doc in parsed_docs),
        sum(1 for doc in parsed_docs if doc.metadata.get("type", "text") != "text"),
    )


def _build_stores(
    system: Any,
    index_docs: list[Any],
) -> tuple[
    InMemoryDocumentStore,
    InMemoryVectorStore,
    dict[str, int],
    dict[str, Any] | None,
    float,
]:
    doc_store = InMemoryDocumentStore()
    vector_store = InMemoryVectorStore()
    index_start = time.perf_counter()
    embedding_cache_stats = {"hits": 0, "misses": 0, "writes": 0}
    indexing_status = None
    if system.embedding is not None:
        embedding_cache_dir = system._embedding_cache_dir()
        indexer = VectorIndexing(
            vector_store=vector_store,
            doc_store=doc_store,
            embedding=system.embedding,
            embedding_cache_dir=(
                str(embedding_cache_dir) if embedding_cache_dir else None
            ),
        )
        indexer.add_to_docstore(index_docs)
        if index_docs:
            indexer.add_to_vectorstore(index_docs)
        embedding_cache_stats = dict(indexer.last_embedding_cache_stats)
        indexing_status = indexer.last_indexing_status
    else:
        doc_store.add(index_docs)
        indexing_status = {
            "status": "completed",
            "stages": {
                "docstore_write": {"status": "completed", "count": len(index_docs)},
                "embed": {"status": "skipped", "count": 0},
                "vector_write": {"status": "skipped", "count": 0},
            },
        }
    return (
        doc_store,
        vector_store,
        embedding_cache_stats,
        indexing_status,
        time.perf_counter() - index_start,
    )
