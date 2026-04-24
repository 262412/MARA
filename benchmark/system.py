from __future__ import annotations

import re
import time
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ktem.embeddings.manager import embedding_models_manager
from ktem.llms.manager import llms
from ktem.rerankings.manager import reranking_models_manager

from kotaemon.base import Document, RetrievedDocument
from kotaemon.embeddings import FastEmbedEmbeddings
from kotaemon.indices import VectorIndexing, VectorRetrieval
from kotaemon.indices.parse_cache import load_data_with_parse_cache
from kotaemon.indices.ingests.files import (
    KH_DEFAULT_FILE_EXTRACTORS,
    adobe_reader,
    azure_reader,
    docling_reader,
    unstructured,
)
from kotaemon.indices.qa.citation_qa import DEFAULT_QA_TEXT_PROMPT
from kotaemon.indices.qa.format_context import PrepareEvidencePipeline
from kotaemon.indices.splitters import TokenSplitter
from kotaemon.llms import PromptTemplate
from kotaemon.storages import InMemoryDocumentStore, InMemoryVectorStore

from .schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample

TOKEN_RE = re.compile(r"[\w\u4e00-\u9fff]+", flags=re.UNICODE)


def _empty_cache_stats() -> dict[str, int]:
    return {"hits": 0, "misses": 0, "writes": 0}


def _safe_cache_component(value: object) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", str(value or "").strip())
    return safe.strip("-") or "default"


def _sum_cache_stats(items: list[dict[str, int]]) -> dict[str, int]:
    total = _empty_cache_stats()
    for item in items:
        for key in total:
            total[key] += int(item.get(key, 0) or 0)
    return total


def _metadata_kind(metadata: dict[str, Any]) -> str:
    for key in ("element_type", "type", "kind", "category", "content_type"):
        value = str(metadata.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _evidence_metadata(
    evidence_mode: str,
    images: list[Any] | tuple[Any, ...] | None,
    hits: list[RetrievedDocument],
) -> dict[str, Any]:
    image_items = [image for image in images or [] if image is not None]
    kinds = sorted(
        {
            kind
            for hit in hits
            for kind in [_metadata_kind(dict(getattr(hit, "metadata", {}) or {}))]
            if kind
        }
    )
    figure_markers = {
        "chart",
        "diagram",
        "drawing",
        "figure",
        "image",
        "page_image",
        "picture",
        "shape",
        "table_image",
        "thumbnail",
        "visual",
    }
    formula_markers = {"equation", "formula", "formula_image", "latex", "math"}
    visual_keys = {
        "image_path",
        "image_origin",
        "page_image",
        "page_image_path",
        "thumbnail",
        "thumbnail_path",
        "visual_path",
    }
    formula_keys = {"formula", "formula_text", "latex", "math_text", "tex"}

    has_figure = bool(image_items) or any(
        any(marker in kind for marker in figure_markers) for kind in kinds
    )
    has_formula = any(
        any(marker in kind for marker in formula_markers) for kind in kinds
    )
    has_page_visual = bool(image_items)
    for hit in hits:
        metadata = dict(getattr(hit, "metadata", {}) or {})
        if any(metadata.get(key) for key in visual_keys):
            has_figure = True
            has_page_visual = True
        if any(metadata.get(key) for key in formula_keys):
            has_formula = True

    return {
        "evidence_mode": evidence_mode,
        "image_count": len(image_items),
        "has_images": bool(image_items),
        "has_figure_evidence": has_figure,
        "has_formula_evidence": has_formula,
        "has_page_visual_context": has_page_visual,
        "source_kinds": kinds,
    }


@dataclass(slots=True)
class ParsedIndex:
    document: BenchmarkDocument
    parsed_documents: list[Document]
    index_documents: list[Document]
    page_count: int
    extracted_characters: int
    non_text_count: int
    parse_seconds: float
    index_seconds: float
    doc_store: InMemoryDocumentStore
    vector_store: InMemoryVectorStore
    parse_cache_stats: dict[str, int] = field(default_factory=_empty_cache_stats)
    parse_cache_hit: bool = False
    embedding_cache_stats: dict[str, int] = field(default_factory=_empty_cache_stats)
    indexing_status: dict[str, Any] | None = None

    def to_report_dict(self) -> dict[str, Any]:
        return {
            "document_id": self.document.document_id,
            "path": str(self.document.path),
            "format_type": self.document.format_type,
            "page_count": self.page_count,
            "chunk_count": len(self.index_documents),
            "non_text_count": self.non_text_count,
            "extracted_characters": self.extracted_characters,
            "parse_seconds": round(self.parse_seconds, 4),
            "index_seconds": round(self.index_seconds, 4),
            "cache": {
                "parse": {
                    **self.parse_cache_stats,
                    "hit": self.parse_cache_hit,
                },
                "embedding": self.embedding_cache_stats,
            },
            "indexing_status": self.indexing_status,
        }


class KotaemonTextRAGSystem:
    def __init__(self, config: BenchmarkConfig):
        self.config = config
        self.embedding = (
            self._resolve_embedding(config.embedding_name)
            if config.retrieval_mode in {"vector", "hybrid"}
            else None
        )
        self.llm = self._resolve_llm(config.llm_name) if config.use_generation else None
        self.reranker = self._resolve_reranker(config.reranker_name)
        self.evidence_pipeline = PrepareEvidencePipeline(
            max_context_length=config.max_context_length
        )
        self.prompt_template = PromptTemplate(
            config.prompt_template or DEFAULT_QA_TEXT_PROMPT
        )
        self._cache: dict[str, ParsedIndex] = {}
        self._cold_cache_token = str(time.time_ns())

    def _resolve_embedding(self, embedding_name: str | None):
        if embedding_name:
            return embedding_models_manager[embedding_name]
        try:
            return embedding_models_manager.get_default()
        except Exception:
            return FastEmbedEmbeddings()

    def _resolve_llm(self, llm_name: str | None):
        if llm_name:
            return llms[llm_name]
        return llms.get_default()

    def _resolve_reranker(self, reranker_name: str | None):
        if not reranker_name:
            return None
        return reranking_models_manager.get(reranker_name)

    def _get_reader(self, path: Path):
        readers = deepcopy(KH_DEFAULT_FILE_EXTRACTORS)
        if self.config.reader_mode == "adobe":
            readers[".pdf"] = adobe_reader
        elif self.config.reader_mode == "azure-di":
            readers[".pdf"] = azure_reader
        elif self.config.reader_mode == "docling":
            readers[".pdf"] = docling_reader
        return readers.get(path.suffix.lower(), unstructured)

    def _split_docs(self, docs: list[Document]) -> list[Document]:
        text_docs: list[Document] = []
        non_text_docs: list[Document] = []
        for doc in docs:
            if doc.metadata.get("type", "text") == "text":
                text_docs.append(doc)
            else:
                non_text_docs.append(doc)

        splitter = TokenSplitter(
            chunk_size=self.config.chunk_size,
            chunk_overlap=self.config.chunk_overlap,
            separator="\n\n",
            backup_separators=["\n", ".", " ", "\u200b"],
        )
        chunks = splitter(text_docs) if text_docs else []
        return chunks + non_text_docs

    def _benchmark_cache_root(self) -> Path | None:
        if self.config.cache_mode == "bypass":
            return None

        root = (
            Path(self.config.output_dir)
            / ".benchmark_cache"
            / _safe_cache_component(self.config.suite_name)
            / _safe_cache_component(self.config.route)
        )
        if self.config.cache_mode == "cold":
            root = root / f"cold-{self._cold_cache_token}"
        return root

    def _parse_cache_dir(self) -> Path | None:
        root = self._benchmark_cache_root()
        if root is None:
            return None
        return root / "parse"

    def _embedding_cache_dir(self) -> Path | None:
        root = self._benchmark_cache_root()
        if root is None:
            return None
        return root / "embedding"

    def _build_index(self, document: BenchmarkDocument) -> ParsedIndex:
        if document.document_id in self._cache:
            return self._cache[document.document_id]

        parse_start = time.perf_counter()
        reader = self._get_reader(document.path)
        loaded = load_data_with_parse_cache(
            reader,
            document.path,
            extra_info={
                "file_id": document.document_id,
                "collection_name": "benchmark",
            },
            cache_dir=self._parse_cache_dir(),
            reader_policy={
                "benchmark_reader_mode": self.config.reader_mode,
                "benchmark_cache_schema": 1,
            },
        )
        parsed_docs = loaded.documents
        parse_seconds = time.perf_counter() - parse_start

        index_docs = self._split_docs(parsed_docs)
        unique_pages = {
            str(doc.metadata.get("page_label"))
            for doc in parsed_docs
            if doc.metadata.get("page_label") is not None
        }
        page_count = len(unique_pages) or 1
        extracted_characters = sum(len(doc.text or "") for doc in parsed_docs)
        non_text_count = sum(
            1 for doc in parsed_docs if doc.metadata.get("type", "text") != "text"
        )

        doc_store = InMemoryDocumentStore()
        vector_store = InMemoryVectorStore()

        index_start = time.perf_counter()
        embedding_cache_stats = _empty_cache_stats()
        indexing_status = None
        if self.embedding is not None:
            embedding_cache_dir = self._embedding_cache_dir()
            indexer = VectorIndexing(
                vector_store=vector_store,
                doc_store=doc_store,
                embedding=self.embedding,
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
                    "docstore_write": {
                        "status": "completed",
                        "count": len(index_docs),
                    },
                    "embed": {"status": "skipped", "count": 0},
                    "vector_write": {"status": "skipped", "count": 0},
                },
            }
        index_seconds = time.perf_counter() - index_start

        parsed_index = ParsedIndex(
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
        self._cache[document.document_id] = parsed_index
        return parsed_index

    def _tokenize(self, text: str) -> list[str]:
        return [match.group(0).lower() for match in TOKEN_RE.finditer(text or "")]

    def _lexical_hits(
        self,
        query: str,
        docs: list[Document],
        limit: int,
    ) -> list[RetrievedDocument]:
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        query_set = set(query_tokens)
        hits: list[RetrievedDocument] = []
        for doc in docs:
            doc_tokens = self._tokenize(doc.text or "")
            if not doc_tokens:
                continue
            overlap = len(query_set.intersection(doc_tokens))
            if overlap == 0:
                continue
            score = overlap / max(len(query_set), 1)
            hits.append(RetrievedDocument(**doc.to_dict(), score=score))

        hits.sort(key=lambda item: item.score, reverse=True)
        return hits[:limit]

    def _combine_hits(
        self,
        query: str,
        vector_hits: list[RetrievedDocument],
        lexical_hits: list[RetrievedDocument],
    ) -> list[RetrievedDocument]:
        if self.config.retrieval_mode == "vector":
            combined = vector_hits
        elif self.config.retrieval_mode == "text":
            combined = lexical_hits
        else:
            merged: dict[str, RetrievedDocument] = {}
            scores: dict[str, float] = {}

            for rank, hit in enumerate(vector_hits, start=1):
                merged[hit.doc_id] = hit
                scores[hit.doc_id] = scores.get(hit.doc_id, 0.0) + (1.0 / rank)

            for rank, hit in enumerate(lexical_hits, start=1):
                if hit.doc_id not in merged:
                    merged[hit.doc_id] = hit
                scores[hit.doc_id] = scores.get(hit.doc_id, 0.0) + (1.0 / rank)

            combined = []
            for doc_id, hit in merged.items():
                hit.score = scores[doc_id]
                combined.append(hit)
            combined.sort(key=lambda item: item.score, reverse=True)

        if self.reranker and combined:
            combined = self.reranker.run(combined, query=query)

        return combined[: self.config.top_k]

    def _retrieve(
        self,
        query: str,
        parsed_index: ParsedIndex,
    ) -> tuple[list[RetrievedDocument], float, list[dict[str, Any]]]:
        start = time.perf_counter()
        trace: list[dict[str, Any]] = []
        vector_hits: list[RetrievedDocument] = []
        if (
            self.config.retrieval_mode in {"vector", "hybrid"}
            and parsed_index.index_documents
            and self.embedding is not None
        ):
            retriever = VectorRetrieval(
                vector_store=parsed_index.vector_store,
                doc_store=parsed_index.doc_store,
                embedding=self.embedding,
                top_k=max(self.config.top_k * 2, self.config.top_k),
                retrieval_mode="vector",
            )
            vector_hits = retriever(query)
            if retriever.last_trace:
                trace.append(
                    {
                        "stage": "vector_retrieval",
                        "document_id": parsed_index.document.document_id,
                        "trace": retriever.last_trace,
                    }
                )

        lexical_hits: list[RetrievedDocument] = []
        if self.config.retrieval_mode in {"text", "hybrid"}:
            lexical_hits = self._lexical_hits(
                query,
                parsed_index.index_documents,
                max(self.config.top_k * 2, self.config.top_k),
            )
            trace.append(
                {
                    "stage": "benchmark_lexical_retrieval",
                    "document_id": parsed_index.document.document_id,
                    "candidate_count": len(lexical_hits),
                    "top_doc_ids": [
                        hit.doc_id for hit in lexical_hits[: self.config.top_k]
                    ],
                }
            )

        hits = self._combine_hits(query, vector_hits, lexical_hits)
        trace.append(
            {
                "stage": "benchmark_fusion",
                "document_id": parsed_index.document.document_id,
                "retrieval_mode": self.config.retrieval_mode,
                "vector_candidate_count": len(vector_hits),
                "lexical_candidate_count": len(lexical_hits),
                "returned_count": len(hits),
                "top_doc_ids": [hit.doc_id for hit in hits],
            }
        )
        return hits, time.perf_counter() - start, trace

    def _generate_answer(
        self,
        example: BenchmarkExample,
        hits: list[RetrievedDocument],
    ) -> tuple[str, str, float, dict[str, Any]]:
        start = time.perf_counter()
        evidence_mode, evidence, images = self.evidence_pipeline(hits).content
        evidence_metadata = _evidence_metadata(evidence_mode, images, hits)

        if not self.config.use_generation:
            answer = hits[0].text if hits else ""
            return answer, evidence, time.perf_counter() - start, evidence_metadata

        if self.llm is None:
            raise ValueError(
                "Generation is enabled but no benchmark LLM is configured."
            )

        prompt = self.prompt_template.populate(
            context=evidence,
            question=example.question,
            lang="English",
        )
        response = self.llm(prompt)
        answer = getattr(response, "text", "") or str(response)
        return answer.strip(), evidence, time.perf_counter() - start, evidence_metadata

    def run_example(
        self,
        document: BenchmarkDocument,
        example: BenchmarkExample,
    ) -> dict[str, Any]:
        return self.run_example_documents([document], example)

    def run_example_documents(
        self,
        documents: list[BenchmarkDocument],
        example: BenchmarkExample,
    ) -> dict[str, Any]:
        parsed_indexes = [self._build_index(document) for document in documents]
        retrieval_hits: list[RetrievedDocument] = []
        retrieval_seconds = 0.0
        retrieval_trace: list[dict[str, Any]] = []
        for parsed_index in parsed_indexes:
            hits, seconds, trace = self._retrieve(example.question, parsed_index)
            retrieval_hits.extend(hits)
            retrieval_seconds += seconds
            retrieval_trace.append(
                {
                    "stage": "benchmark_index",
                    "document_id": parsed_index.document.document_id,
                    "chunk_count": len(parsed_index.index_documents),
                    "page_count": parsed_index.page_count,
                    "parse_cache": {
                        **parsed_index.parse_cache_stats,
                        "hit": parsed_index.parse_cache_hit,
                    },
                    "embedding_cache": parsed_index.embedding_cache_stats,
                    "indexing_status": parsed_index.indexing_status,
                }
            )
            retrieval_trace.extend(trace)
        retrieval_hits.sort(
            key=lambda hit: float(hit.score) if hit.score is not None else 0.0,
            reverse=True,
        )
        retrieval_hits = retrieval_hits[: self.config.top_k]

        answer, evidence, generation_seconds, evidence_metadata = self._generate_answer(
            example, retrieval_hits
        )

        predicted_pages = [
            hit.metadata.get("page_label")
            for hit in retrieval_hits
            if hit.metadata.get("page_label") is not None
        ]
        predicted_sources = [
            f"{hit.metadata.get('file_name', documents[0].path.name)}#page:{hit.metadata.get('page_label', '-')}"
            for hit in retrieval_hits
        ]
        predicted_element_ids = [
            str(hit.metadata["element_id"])
            for hit in retrieval_hits
            if str(hit.metadata.get("element_id") or "").strip()
        ]

        timings = {
            "parse_seconds": round(
                sum(item.parse_seconds for item in parsed_indexes), 4
            ),
            "index_seconds": round(
                sum(item.index_seconds for item in parsed_indexes), 4
            ),
            "retrieval_seconds": round(retrieval_seconds, 4),
            "generation_seconds": round(generation_seconds, 4),
        }
        cache = {
            "parse": _sum_cache_stats(
                [item.parse_cache_stats for item in parsed_indexes]
            ),
            "embedding": _sum_cache_stats(
                [item.embedding_cache_stats for item in parsed_indexes]
            ),
        }
        performance = {
            **timings,
            "total_seconds": round(sum(timings.values()), 4),
            "num_documents": len(parsed_indexes),
            "num_chunks": sum(len(item.index_documents) for item in parsed_indexes),
        }

        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": answer,
            "predicted_pages": predicted_pages,
            "predicted_sources": predicted_sources,
            "predicted_element_ids": predicted_element_ids,
            "retrieved_hits": [
                {
                    "doc_id": hit.doc_id,
                    "document_id": hit.metadata.get("file_id")
                    or hit.metadata.get("source_id")
                    or hit.metadata.get("file_name"),
                    "score": (
                        round(float(hit.score), 4) if hit.score is not None else None
                    ),
                    "page_label": hit.metadata.get("page_label"),
                    "element_id": hit.metadata.get("element_id"),
                    "element_type": hit.metadata.get("element_type")
                    or hit.metadata.get("type"),
                    "file_name": hit.metadata.get("file_name", documents[0].path.name),
                    "text_preview": (hit.text or "")[:400],
                }
                for hit in retrieval_hits
            ],
            "retrieval_trace": retrieval_trace,
            "evidence_metadata": evidence_metadata,
            "timings": timings,
            "performance": performance,
            "cache": cache,
            "cost": {},
            "context_preview": evidence[:1200],
        }

    def document_reports(self) -> list[dict[str, Any]]:
        return [item.to_report_dict() for item in self._cache.values()]
