import json
from pathlib import Path
from typing import cast
from unittest.mock import patch

from openai.types.create_embedding_response import CreateEmbeddingResponse

from kotaemon.base import Document, RetrievedDocument
from kotaemon.embeddings import AzureOpenAIEmbeddings
from kotaemon.indices import VectorIndexing, VectorRetrieval
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
