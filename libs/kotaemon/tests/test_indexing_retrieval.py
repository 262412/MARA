import json
from pathlib import Path
from typing import cast
from unittest.mock import patch

from openai.types.create_embedding_response import CreateEmbeddingResponse

from kotaemon.base import Document, RetrievedDocument
from kotaemon.embeddings import AzureOpenAIEmbeddings
from kotaemon.indices import VectorIndexing, VectorRetrieval
from kotaemon.indices.rankings import BaseReranking
from kotaemon.storages import ChromaVectorStore, InMemoryDocumentStore

with open(Path(__file__).parent / "resources" / "embedding_openai.json") as f:
    openai_embedding = CreateEmbeddingResponse.model_validate(json.load(f))


@patch(
    "openai.resources.embeddings.Embeddings.create",
    side_effect=lambda *args, **kwargs: openai_embedding,
)
def test_indexing(_mock_create, tmp_path):
    db = ChromaVectorStore(path=str(tmp_path))
    doc_store = InMemoryDocumentStore()
    embedding = AzureOpenAIEmbeddings(
        azure_deployment="text-embedding-ada-002",
        azure_endpoint="https://test.openai.azure.com/",
        api_key="some-key",
        api_version="version",
    )

    pipeline = VectorIndexing(vector_store=db, embedding=embedding, doc_store=doc_store)
    pipeline.doc_store = cast(InMemoryDocumentStore, pipeline.doc_store)
    pipeline.vector_store = cast(ChromaVectorStore, pipeline.vector_store)
    assert pipeline.vector_store._collection.count() == 0, "Expected empty collection"
    assert len(pipeline.doc_store._store) == 0, "Expected empty doc store"
    pipeline(text=Document(text="Hello world"))
    assert pipeline.vector_store._collection.count() == 1, "Index 1 item"
    assert len(pipeline.doc_store._store) == 1, "Expected 1 document"
    stored_doc = pipeline.doc_store.get_all()[0]
    assert stored_doc.metadata["element_type"] == "text"
    assert stored_doc.metadata["element_id"]


@patch(
    "openai.resources.embeddings.Embeddings.create",
    side_effect=lambda *args, **kwargs: openai_embedding,
)
def test_indexing_normalizes_formula_element_metadata(_mock_create, tmp_path):
    db = ChromaVectorStore(path=str(tmp_path))
    doc_store = InMemoryDocumentStore()
    embedding = AzureOpenAIEmbeddings(
        azure_deployment="text-embedding-ada-002",
        azure_endpoint="https://test.openai.azure.com/",
        api_key="some-key",
        api_version="version",
    )

    pipeline = VectorIndexing(vector_store=db, embedding=embedding, doc_store=doc_store)
    formula = Document(
        text="  E   =   m c ^ 2  ",
        metadata={
            "type": "formula",
            "formula_format": "latex",
            "page_number": 2,
        },
    )

    pipeline(text=formula)

    stored_doc = doc_store.get_all()[0]
    assert stored_doc.text == "E = m c ^ 2"
    assert stored_doc.content == "E = m c ^ 2"
    assert stored_doc.metadata["type"] == "formula"
    assert stored_doc.metadata["element_type"] == "formula"
    assert stored_doc.metadata["formula_text"] == "E = m c ^ 2"
    assert stored_doc.metadata["page_label"] == "2"


@patch(
    "openai.resources.embeddings.Embeddings.create",
    side_effect=lambda *args, **kwargs: openai_embedding,
)
def test_retrieving(_mock_create, tmp_path):
    db = ChromaVectorStore(path=str(tmp_path))
    doc_store = InMemoryDocumentStore()
    embedding = AzureOpenAIEmbeddings(
        azure_deployment="text-embedding-ada-002",
        azure_endpoint="https://test.openai.azure.com/",
        api_key="some-key",
        api_version="version",
    )

    index_pipeline = VectorIndexing(
        vector_store=db, embedding=embedding, doc_store=doc_store
    )
    retrieval_pipeline = VectorRetrieval(
        vector_store=db, doc_store=doc_store, embedding=embedding
    )

    index_pipeline(text=Document(text="Hello world"))
    output = retrieval_pipeline(text="Hello world")
    output1 = retrieval_pipeline(text="Hello world")

    assert len(output) == 1, "Expect 1 results"
    assert output == output1, "Expect identical results"


def _retrieved_doc(doc_id: str, score: float = 0.0) -> RetrievedDocument:
    return RetrievedDocument(text=f"Document {doc_id}", id_=doc_id, score=score)


def _structured_retrieved_doc(
    doc_id: str,
    *,
    source_id: str = "report",
    page_label: str = "4",
) -> RetrievedDocument:
    return RetrievedDocument(
        text="Revenue was $10 million.",
        id_=doc_id,
        score=0.5,
        metadata={
            "file_id": source_id,
            "page_label": page_label,
            "element_id": "revenue-cell",
        },
    )


def test_rrf_fusion_deduplicates_and_sums_rank_signals():
    fused = VectorRetrieval._reciprocal_rank_fuse(
        vector_docs=[_retrieved_doc("shared", score=0.91)],
        text_docs=[_retrieved_doc("shared", score=-1.0)],
    )

    assert [doc.doc_id for doc in fused] == ["shared"]
    assert fused[0].score == (1 / 61) + (1 / 61)


def test_rrf_fusion_orders_by_combined_rank_not_append_order():
    fused = VectorRetrieval._reciprocal_rank_fuse(
        vector_docs=[
            _retrieved_doc("vector-rank-1"),
            _retrieved_doc("vector-rank-2"),
            _retrieved_doc("shared"),
        ],
        text_docs=[
            _retrieved_doc("shared"),
            _retrieved_doc("text-rank-2"),
        ],
    )

    assert [doc.doc_id for doc in fused[:2]] == ["shared", "vector-rank-1"]
    assert fused[0].score == (1 / 63) + (1 / 61)


def test_rrf_fusion_keeps_single_path_modes_unchanged():
    vector_docs = [_retrieved_doc("vector-only", score=0.42)]
    text_docs = [_retrieved_doc("text-only", score=-1.0)]

    assert VectorRetrieval._reciprocal_rank_fuse(vector_docs, []) == vector_docs
    assert VectorRetrieval._reciprocal_rank_fuse([], text_docs) == text_docs


def test_rrf_canonicalizes_structure_before_adding_rank_signals():
    fused = VectorRetrieval._reciprocal_rank_fuse(
        vector_docs=[
            _structured_retrieved_doc("dense-primary"),
            _structured_retrieved_doc("dense-overlap"),
        ],
        text_docs=[_structured_retrieved_doc("sparse-primary")],
    )

    assert len(fused) == 1
    assert fused[0].score == (1 / 61) + (1 / 61)
    assert fused[0].retrieval_metadata["canonical_id"].startswith("element:")
    assert fused[0].retrieval_metadata["duplicate_doc_ids"] == [
        "dense-overlap",
        "sparse-primary",
    ]


def test_rrf_canonical_text_merge_preserves_cross_source_backrefs():
    dense = _structured_retrieved_doc("dense-source-a", source_id="source-a")
    sparse = _structured_retrieved_doc("sparse-source-b", source_id="source-b")
    sparse.metadata["element_id"] = "different-cell-id"

    [fused] = VectorRetrieval._reciprocal_rank_fuse([dense], [sparse])

    assert fused.retrieval_metadata["source_backrefs"] == [
        "source-a#page:4",
        "source-b#page:4",
    ]


class _RecordingEmbedding:
    def __call__(self, _text):
        return [DocumentWithEmbeddingForTest()]


class DocumentWithEmbeddingForTest:
    embedding = [0.1, 0.2, 0.3]


class _RecordingVectorStore:
    def __init__(self, ids):
        self.ids = ids
        self.calls = []

    def query(self, embedding, top_k=1, doc_ids=None, **kwargs):
        self.calls.append({"top_k": top_k, "doc_ids": doc_ids, "kwargs": kwargs})
        ids = self.ids[:top_k]
        scores = [1.0 - (idx * 0.001) for idx, _ in enumerate(ids)]
        return [], scores, ids


class _RecordingDocStore:
    def __init__(self, ids, metadata_by_id=None):
        self.ids = ids
        self.calls = []
        metadata_by_id = metadata_by_id or {}
        self.docs = {
            doc_id: Document(
                text=f"Doc {doc_id}",
                id_=doc_id,
                metadata={"file_id": "file-1", **metadata_by_id.get(doc_id, {})},
            )
            for doc_id in ids
        }

    def get(self, ids):
        return [self.docs[doc_id] for doc_id in ids]

    def query(self, query, top_k=10, doc_ids=None):
        self.calls.append({"query": query, "top_k": top_k, "doc_ids": doc_ids})
        allowed = [doc_id for doc_id in self.ids if not doc_ids or doc_id in doc_ids]
        return [self.docs[doc_id] for doc_id in allowed[:top_k]]


class _RecordingReranker(BaseReranking):
    def __init__(self):
        super().__init__()
        self._received_doc_ids = []

    def run(self, documents, query):
        self._received_doc_ids = [doc.doc_id for doc in documents]
        for index, document in enumerate(documents):
            document.metadata["reranked_position"] = index
        return documents

    @property
    def received_doc_ids(self):
        return self._received_doc_ids


def test_hybrid_retrieval_defaults_match_wide_recall_contract():
    retrieval = VectorRetrieval(
        vector_store=_RecordingVectorStore([]),
        doc_store=_RecordingDocStore([]),
        embedding=_RecordingEmbedding(),
    )

    assert retrieval.dense_top_k == 50
    assert retrieval.sparse_top_k == 50
    assert retrieval.rerank_top_k == 80
    assert retrieval.rrf_k == 60


def test_hybrid_retrieval_uses_configured_dense_and_sparse_first_round_limits():
    vector_ids = [f"vector-{idx}" for idx in range(120)]
    text_ids = [f"text-{idx}" for idx in range(120)]
    vector_store = _RecordingVectorStore(vector_ids)
    doc_store = _RecordingDocStore([*vector_ids, *text_ids])
    retrieval = VectorRetrieval(
        vector_store=vector_store,
        doc_store=doc_store,
        embedding=_RecordingEmbedding(),
        retrieval_mode="hybrid",
        dense_top_k=100,
        sparse_top_k=100,
        top_k=10,
    )

    retrieval(text="revenue table", do_extend=True, scope=[*vector_ids, *text_ids])

    assert vector_store.calls[0]["top_k"] == 100
    assert doc_store.calls[0]["top_k"] == 100


def test_hybrid_retrieval_limits_documents_before_local_reranking():
    ids = [f"doc-{idx}" for idx in range(80)]
    reranker = _RecordingReranker()
    retrieval = VectorRetrieval(
        vector_store=_RecordingVectorStore(ids),
        doc_store=_RecordingDocStore(ids),
        embedding=_RecordingEmbedding(),
        retrieval_mode="hybrid",
        rerankers=[reranker],
        dense_top_k=80,
        sparse_top_k=80,
        rerank_top_k=50,
        top_k=5,
    )

    result = retrieval(text="query", do_extend=True, scope=ids)

    assert len(reranker.received_doc_ids) == 50
    assert len(result) == 5
    assert retrieval.last_trace is not None
    trace = retrieval.last_trace["metadata"]["reranker_execution"]
    assert trace["configured"] is True
    assert trace["loaded"] is True
    assert trace["executed"] is True
    assert trace["input_count"] == 50
    assert trace["output_count"] == 50
    assert trace["input_identities"] == reranker.received_doc_ids
    assert all(doc.metadata["reranker_input_identity"] for doc in result)
    assert all(doc.metadata["reranker_rank"] > 0 for doc in result)


def test_hybrid_retrieval_boosts_query_routed_element_types():
    ids = ["text-doc", "table-doc"]
    doc_store = _RecordingDocStore(
        ids,
        metadata_by_id={
            "text-doc": {"element_type": "text"},
            "table-doc": {"element_type": "table"},
        },
    )
    retrieval = VectorRetrieval(
        vector_store=_RecordingVectorStore(ids),
        doc_store=doc_store,
        embedding=_RecordingEmbedding(),
        retrieval_mode="hybrid",
        dense_top_k=2,
        sparse_top_k=2,
        top_k=1,
    )

    result = retrieval(text="show the revenue table", do_extend=True, scope=ids)

    assert [doc.doc_id for doc in result] == ["table-doc"]
    assert result[0].retrieval_metadata["query_modality"] == "table"
