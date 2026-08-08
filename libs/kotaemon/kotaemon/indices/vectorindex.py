from __future__ import annotations

import logging
import os
import uuid
from time import perf_counter
from typing import Optional, Sequence, cast

from theflow.settings import settings as flowsettings

from kotaemon.artifact_namespace import write_chunk_artifacts
from kotaemon.base import (
    BaseComponent,
    Document,
    DocumentWithEmbedding,
    RetrievedDocument,
)
from kotaemon.embeddings import BaseEmbeddings
from kotaemon.storages import BaseDocumentStore, BaseVectorStore

from .base import BaseIndexing, BaseRetrieval
from .elements import annotate_document_with_element_metadata
from .indexing_status import IndexingStatusTracker, refresh_vector_store
from .performance_cache import JsonDiskCache, content_hash, stable_cache_key
from .rankings import BaseReranking
from .reranker_execution_trace import execute_rerankers
from .retrieval_identity import (
    deterministic_ranking_contract,
    reciprocal_rank_fuse,
    stable_scored_documents,
)
from .retrieval_quality import QueryRoute, route_query
from .retrieval_trace import RetrievalCostStats, RetrievalTrace
from .vectorindex_helpers import (
    embedding_contract,
    normalized_chunk_text,
    retrieve_candidates,
)

VECTOR_STORE_FNAME = "vectorstore"
DOC_STORE_FNAME = "docstore"
logger = logging.getLogger(__name__)


class VectorIndexing(BaseIndexing):
    """Ingest the document, run through the embedding, and store the embedding in a
    vector store.

    This pipeline supports the following set of inputs:
        - List of documents
        - List of texts
    """

    cache_dir: Optional[str] = getattr(flowsettings, "KH_CHUNKS_OUTPUT_DIR", None)
    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    count_: int = 0
    artifact_count_namespace_: tuple[object, object] | None = None
    embedding_cache_dir: Optional[str] = getattr(
        flowsettings, "KH_EMBEDDING_CACHE_DIR", None
    )
    index_contract: str = ""
    embedding_contract: Optional[dict[str, object]] = None
    refresh_after_batch: bool = getattr(
        flowsettings, "KH_REFRESH_VECTOR_STORE_AFTER_BATCH", True
    )
    last_embedding_cache_stats: dict[str, int] = {"hits": 0, "misses": 0, "writes": 0}
    last_indexing_status: dict | None = None

    def __init__(self, *args, **kwargs):
        embedding = kwargs.get("embedding")
        if embedding is not None and kwargs.get("embedding_contract") is None:
            kwargs["embedding_contract"] = embedding_contract(embedding)
        super().__init__(*args, **kwargs)

    def to_retrieval_pipeline(self, *args, **kwargs):
        """Convert the indexing pipeline to a retrieval pipeline"""
        return VectorRetrieval(
            vector_store=self.vector_store,
            doc_store=self.doc_store,
            embedding=self.embedding,
            index_contract=self._resolved_index_contract(),
            embedding_contract=dict(self.embedding_contract or {}),
            **kwargs,
        )

    def write_chunk_to_file(
        self,
        docs: list[Document],
        file_id: object | None = None,
        artifact_generation: object | None = None,
    ):
        # save the chunks content into markdown format
        if docs:
            file_id = file_id or docs[0].metadata.get("file_id")
            artifact_generation = artifact_generation or docs[0].metadata.get(
                "artifact_generation"
            )
        namespace = (file_id, artifact_generation)
        if getattr(self, "artifact_count_namespace_", None) != namespace:
            self.count_ = 0
            self.artifact_count_namespace_ = namespace
        if self.cache_dir:
            write_chunk_artifacts(
                self.cache_dir,
                docs,
                self.count_,
                file_id=file_id,
                artifact_generation=artifact_generation,
            )
        self.count_ += len(docs)

    def add_to_docstore(self, docs: list[Document]):
        if self.doc_store:
            logger.debug("Adding documents to doc store")
            self.doc_store.add(docs)

    def add_to_vectorstore(self, docs: list[Document]):
        # in case we want to skip embedding
        if self.vector_store:
            logger.debug("Getting embeddings for %s nodes", len(docs))
            embeddings = self._embed_documents(docs)
            logger.debug("Adding embeddings to vector store")
            self.vector_store.add(
                embeddings=embeddings,
                ids=[t.doc_id for t in docs],
            )

    def _embed_documents(self, docs: list[Document]) -> list[DocumentWithEmbedding]:
        if not self.embedding_cache_dir:
            embedded_docs = self.embedding(docs)
            self.last_embedding_cache_stats = {
                "hits": 0,
                "misses": len(docs),
                "writes": 0,
            }
            return cast(list[DocumentWithEmbedding], embedded_docs)

        cache = JsonDiskCache(self.embedding_cache_dir, "embedding")
        embedding_contract = self._resolved_embedding_contract()
        index_contract = self._resolved_index_contract()
        embeddings: list[DocumentWithEmbedding | None] = [None] * len(docs)
        missing_docs: list[Document] = []
        missing_positions: list[int] = []
        missing_keys: list[str] = []

        for index, doc in enumerate(docs):
            key = stable_cache_key(
                "embedding",
                {
                    "chunk_hash": content_hash(self._embedding_cache_payload(doc)),
                    "embedding_contract": embedding_contract,
                    "index_contract": index_contract,
                    "source_revision": os.environ.get(
                        "MARA_BENCHMARK_GIT_COMMIT", "not_declared"
                    ),
                },
            )
            cached_embedding = cache.get(key)
            if cached_embedding is None:
                missing_docs.append(doc)
                missing_positions.append(index)
                missing_keys.append(key)
                continue

            embeddings[index] = DocumentWithEmbedding(
                embedding=cast(list[float], cached_embedding),
                text=doc.text,
                metadata=dict(doc.metadata or {}),
            )

        if missing_docs:
            computed = cast(list[DocumentWithEmbedding], self.embedding(missing_docs))
            for position, key, embedding_doc, original_doc in zip(
                missing_positions, missing_keys, computed, missing_docs
            ):
                vector = list(embedding_doc.embedding)
                cache.set(key, vector)
                embeddings[position] = DocumentWithEmbedding(
                    embedding=vector,
                    text=original_doc.text,
                    metadata=dict(original_doc.metadata or {}),
                )

        self.last_embedding_cache_stats = cache.stats.to_dict()
        return [cast(DocumentWithEmbedding, embedding) for embedding in embeddings]

    def _embedding_cache_payload(self, doc: Document) -> dict:
        metadata = doc.metadata or {}
        return {
            "normalized_text": normalized_chunk_text(doc.text),
            "element_type": metadata.get("element_type") or metadata.get("type"),
        }

    def _resolved_index_contract(self) -> str:
        return str(
            self.index_contract
            or os.environ.get("MARA_BENCHMARK_INDEX_CONTRACT")
            or "not_declared"
        )

    def _resolved_embedding_contract(self) -> dict[str, object]:
        declared = os.environ.get("MARA_BENCHMARK_EMBEDDING_CONTRACT")
        if declared:
            return {"declared_contract": declared}
        return dict(self.embedding_contract or embedding_contract(self.embedding))

    def run(self, text: str | list[str] | Document | list[Document]):
        input_: list[Document] = []
        if not isinstance(text, list):
            text = [text]

        for item in cast(list, text):
            if isinstance(item, str):
                input_.append(
                    annotate_document_with_element_metadata(
                        Document(text=item, id_=str(uuid.uuid4()))
                    )
                )
            elif isinstance(item, Document):
                input_.append(annotate_document_with_element_metadata(Document(item)))
            else:
                raise ValueError(
                    f"Invalid input type {type(item)}, should be str or Document"
                )

        tracker = IndexingStatusTracker()
        try:
            tracker.start("parse", count=len(input_))
            tracker.finish("parse", count=len(input_))
            tracker.start("chunk", count=len(input_))
            tracker.finish("chunk", count=len(input_))

            if self.vector_store:
                tracker.start("embed", count=len(input_))
                embeddings = self._embed_documents(input_)
                tracker.finish("embed", count=len(input_))

                tracker.start("vector_write", count=len(input_))
                self.vector_store.add(
                    embeddings=embeddings,
                    ids=[t.doc_id for t in input_],
                )
                tracker.finish("vector_write", count=len(input_))
            else:
                tracker.start("embed", count=0)
                tracker.finish("embed", count=0)
                tracker.start("vector_write", count=0)
                tracker.finish("vector_write", count=0)

            tracker.start("docstore_write", count=len(input_))
            self.add_to_docstore(input_)
            tracker.finish("docstore_write", count=len(input_))

            tracker.start("refresh", count=1 if self.vector_store else 0)
            if self.vector_store and self.refresh_after_batch:
                refresh_vector_store(self.vector_store)
            tracker.finish("refresh", count=1 if self.vector_store else 0)

            self.write_chunk_to_file(input_)
        except Exception as exc:
            for stage_name, stage in tracker.stages.items():
                if stage.status == "running":
                    tracker.fail(stage_name, exc, count=stage.count)
                    break
            else:
                tracker.fail("refresh", exc)
            self.last_indexing_status = tracker.to_dict()
            raise
        finally:
            if tracker.status != "failed":
                self.last_indexing_status = tracker.to_dict()


class VectorRetrieval(BaseRetrieval):
    """Retrieve list of documents from vector store"""

    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    rerankers: Sequence[BaseReranking] = []
    top_k: int = 5
    first_round_top_k_mult: int = 10
    dense_top_k: int = 50
    sparse_top_k: int = 50
    rerank_top_k: int = 80
    rrf_k: int = 60
    modality_boost: float = 0.05
    retrieval_mode: str = "hybrid"  # vector, text, hybrid
    index_contract: str = "not_declared"
    embedding_contract: Optional[dict[str, object]] = None
    last_trace: dict | None = None
    _reciprocal_rank_fuse = staticmethod(reciprocal_rank_fuse)

    def _filter_docs(
        self, documents: list[RetrievedDocument], top_k: int | None = None
    ):
        if top_k:
            documents = documents[:top_k]
        return documents

    def _apply_query_route_boost(
        self, documents: list[RetrievedDocument], route: QueryRoute
    ) -> list[RetrievedDocument]:
        boost_element_types = set(route.retrieval_hints.get("boost_element_types", []))
        if not boost_element_types or boost_element_types == {"text"}:
            for document in documents:
                document.retrieval_metadata = {
                    **document.retrieval_metadata,
                    "query_modality": route.modality,
                }
            return stable_scored_documents(documents)

        boosted = []
        for document in documents:
            element_type = self._normalize_element_type(
                document.metadata.get("element_type", document.metadata.get("type"))
            )
            score = document.score
            if element_type in boost_element_types:
                score += self.modality_boost * route.modality_weights.get(
                    element_type, 1.0
                )

            document_dict = document.to_dict()
            document_dict["score"] = score
            boosted_document = RetrievedDocument(**document_dict)
            boosted_document.retrieval_metadata = {
                **document.retrieval_metadata,
                "query_modality": route.modality,
                "query_modality_weights": route.modality_weights,
                "query_boost_element_types": list(boost_element_types),
            }
            boosted.append(boosted_document)

        return stable_scored_documents(boosted)

    @staticmethod
    def _normalize_element_type(value: object) -> str:
        element_type = str(value or "text").strip().lower()
        if element_type in {"image", "fig", "chart", "plot"}:
            return "figure"
        return element_type

    def run(
        self, text: str | Document, top_k: Optional[int] = None, **kwargs
    ) -> list[RetrievedDocument]:
        """Retrieve a list of documents from vector store

        Args:
            text: the text to retrieve similar documents
            top_k: number of top similar documents to return

        Returns:
            list[RetrievedDocument]: list of retrieved documents
        """
        if top_k is None:
            top_k = self.top_k

        do_extend = kwargs.pop("do_extend", False)
        thumbnail_count = kwargs.pop("thumbnail_count", 3)
        retrieval_started_at = perf_counter()
        rerank_latency_ms = 0.0

        if do_extend:
            top_k_first_round = top_k * self.first_round_top_k_mult
        else:
            top_k_first_round = top_k
        dense_top_k = kwargs.pop(
            "dense_top_k", self.dense_top_k if do_extend else top_k_first_round
        )
        sparse_top_k = kwargs.pop(
            "sparse_top_k", self.sparse_top_k if do_extend else top_k_first_round
        )
        rerank_top_k = kwargs.pop(
            "rerank_top_k", self.rerank_top_k if do_extend else top_k_first_round
        )
        rrf_k = kwargs.pop("rrf_k", self.rrf_k)

        if self.doc_store is None:
            raise ValueError(
                "doc_store is not provided. Please provide a doc_store to "
                "retrieve the documents"
            )

        result: list[RetrievedDocument] = []
        # TODO: should declare scope directly in the run params
        scope = kwargs.pop("scope", None)
        query = text.text if isinstance(text, Document) else text
        query_route = route_query(query)

        result = retrieve_candidates(
            self,
            text=text,
            query=query,
            scope=scope,
            dense_top_k=dense_top_k,
            sparse_top_k=sparse_top_k,
            rrf_k=rrf_k,
            query_kwargs=kwargs,
        )

        result = self._apply_query_route_boost(result, query_route)
        retrieval_latency_ms = round((perf_counter() - retrieval_started_at) * 1000, 3)

        result, reranker_trace, rerank_latency_ms = execute_rerankers(
            self.rerankers,
            result,
            text,
            rerank_top_k=rerank_top_k,
            output_top_k=top_k,
            filter_docs=lambda docs, limit: self._filter_docs(docs, top_k=limit),
        )

        if not self.rerankers:
            result = stable_scored_documents(result)

        result = self._filter_docs(result, top_k=top_k)
        logger.debug("Got raw %s retrieved documents", len(result))

        # add page thumbnails to the result if exists
        thumbnail_doc_ids: set[str] = set()
        # we should copy the text from retrieved text chunk
        # to the thumbnail to get relevant LLM score correctly
        text_thumbnail_docs: dict[str, RetrievedDocument] = {}

        non_thumbnail_docs = []
        raw_thumbnail_docs = []
        for doc in result:
            if doc.metadata.get("type") == "thumbnail":
                # change type to image to display on UI
                doc.metadata["type"] = "image"
                raw_thumbnail_docs.append(doc)
                continue
            if (
                "thumbnail_doc_id" in doc.metadata
                and len(thumbnail_doc_ids) < thumbnail_count
            ):
                thumbnail_id = doc.metadata["thumbnail_doc_id"]
                thumbnail_doc_ids.add(thumbnail_id)
                text_thumbnail_docs[thumbnail_id] = doc
            else:
                non_thumbnail_docs.append(doc)

        linked_thumbnail_docs = self.doc_store.get(list(thumbnail_doc_ids))
        logger.debug(
            "thumbnail docs=%s non-thumbnail docs=%s raw-thumbnail docs=%s",
            len(linked_thumbnail_docs),
            len(non_thumbnail_docs),
            len(raw_thumbnail_docs),
        )
        additional_docs = []

        for thumbnail_doc in linked_thumbnail_docs:
            text_doc = text_thumbnail_docs[thumbnail_doc.doc_id]
            doc_dict = thumbnail_doc.to_dict()
            doc_dict["_id"] = text_doc.doc_id
            doc_dict["content"] = text_doc.content
            doc_dict["metadata"]["type"] = "image"
            for key in text_doc.metadata:
                if key not in doc_dict["metadata"]:
                    doc_dict["metadata"][key] = text_doc.metadata[key]

            additional_docs.append(RetrievedDocument(**doc_dict, score=text_doc.score))

        result = additional_docs + non_thumbnail_docs

        if not result:
            # return output from raw retrieved thumbnails
            result = self._filter_docs(raw_thumbnail_docs, top_k=thumbnail_count)

        retrieval_path = [self.retrieval_mode]
        if self.rerankers:
            retrieval_path.append("rerank")
        if additional_docs or raw_thumbnail_docs:
            retrieval_path.append("thumbnail")

        self.last_trace = RetrievalTrace.from_retrieved_docs(
            result,
            query=query,
            query_modality=query_route.modality,
            retrieval_path=retrieval_path,
            cost=RetrievalCostStats(
                retrieval_latency_ms=retrieval_latency_ms,
                rerank_latency_ms=rerank_latency_ms,
                metadata={
                    "retrieval_mode": self.retrieval_mode,
                    "top_k": top_k,
                    "dense_top_k": dense_top_k,
                    "sparse_top_k": sparse_top_k,
                    "rerank_top_k": rerank_top_k,
                    "scope_count": len(scope) if scope is not None else None,
                },
            ),
            metadata={
                "reranker_execution": reranker_trace,
                "deterministic_ranking": deterministic_ranking_contract(),
                "embedding_contract": {
                    **dict(
                        self.embedding_contract or embedding_contract(self.embedding)
                    ),
                    "index_contract": self.index_contract,
                    "source_revision": os.environ.get(
                        "MARA_BENCHMARK_GIT_COMMIT", "not_declared"
                    ),
                },
            },
        ).to_dict()

        return result


class TextVectorQA(BaseComponent):
    retrieving_pipeline: BaseRetrieval
    qa_pipeline: BaseComponent

    def run(self, question, **kwargs):
        retrieved_documents = self.retrieving_pipeline(question, **kwargs)
        return self.qa_pipeline(question, retrieved_documents, **kwargs)
