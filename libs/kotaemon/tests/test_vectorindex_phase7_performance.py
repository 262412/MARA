from kotaemon.base import Document, DocumentWithEmbedding
from kotaemon.indices import VectorIndexing, VectorRetrieval


class _CountingEmbedding:
    model = "counting-embedding"
    model_revision = "revision-1"
    precision = "float32"
    determinism = "deterministic"

    def __init__(self):
        self.calls = 0
        self.batch_sizes = []

    def __call__(self, docs):
        if isinstance(docs, str):
            docs = [Document(text=docs)]
        self.calls += 1
        self.batch_sizes.append(len(docs))
        return [
            DocumentWithEmbedding(
                embedding=[float(index), float(len(doc.text or ""))],
                text=doc.text,
                metadata=dict(doc.metadata or {}),
            )
            for index, doc in enumerate(docs)
        ]


class _RecordingVectorStore:
    def __init__(self, ids=None):
        self.ids = ids or []
        self.add_calls = []
        self.query_calls = []
        self.refresh_calls = 0

    def add(self, embeddings, ids):
        self.add_calls.append({"embeddings": embeddings, "ids": ids})

    def query(self, embedding, top_k=1, doc_ids=None, **kwargs):
        self.query_calls.append({"top_k": top_k, "doc_ids": doc_ids, "kwargs": kwargs})
        ids = [doc_id for doc_id in self.ids if not doc_ids or doc_id in doc_ids]
        ids = ids[:top_k]
        scores = [0.9 - (index * 0.01) for index, _ in enumerate(ids)]
        return [], scores, ids

    def refresh(self):
        self.refresh_calls += 1


class _RecordingDocStore:
    def __init__(self, docs=None):
        self.add_calls = []
        self.docs = {doc.doc_id: doc for doc in docs or []}

    def add(self, docs):
        self.add_calls.append(list(docs))
        self.docs.update({doc.doc_id: doc for doc in docs})

    def get(self, ids):
        return [self.docs[doc_id] for doc_id in ids]

    def query(self, query, top_k=10, doc_ids=None):
        docs = list(self.docs.values())
        if doc_ids:
            docs = [doc for doc in docs if doc.doc_id in doc_ids]
        return docs[:top_k]


def test_vector_indexing_reuses_embedding_cache_across_runs(tmp_path):
    embedding = _CountingEmbedding()
    vector_store = _RecordingVectorStore()
    pipeline = VectorIndexing(
        vector_store=vector_store,
        doc_store=_RecordingDocStore(),
        embedding=embedding,
        embedding_cache_dir=str(tmp_path),
    )
    first = Document(text="same chunk", id_="doc-1")
    second = Document(text="same chunk", id_="doc-2")

    pipeline(text=first)
    assert embedding.calls == 1
    assert pipeline.last_embedding_cache_stats == {
        "hits": 0,
        "misses": 1,
        "writes": 1,
    }

    pipeline(text=second)

    assert embedding.calls == 1
    assert [call["ids"] for call in vector_store.add_calls] == [["doc-1"], ["doc-2"]]
    assert pipeline.last_embedding_cache_stats == {
        "hits": 1,
        "misses": 0,
        "writes": 0,
    }


def test_vector_indexing_cache_uses_normalized_chunk_text(tmp_path):
    embedding = _CountingEmbedding()
    pipeline = VectorIndexing(
        vector_store=_RecordingVectorStore(),
        doc_store=_RecordingDocStore(),
        embedding=embedding,
        embedding_cache_dir=str(tmp_path),
        index_contract="index-v1",
    )

    pipeline(text=Document(text="same\tchunk\ntext", id_="doc-1"))
    pipeline(text=Document(text="same chunk text", id_="doc-2"))

    assert embedding.calls == 1
    assert pipeline.last_embedding_cache_stats == {
        "hits": 1,
        "misses": 0,
        "writes": 0,
    }


def test_vector_indexing_cache_partitions_exact_embedding_and_index_contracts(
    tmp_path,
):
    class _RevisionTwoEmbedding(_CountingEmbedding):
        model_revision = "revision-2"

    first_embedding = _CountingEmbedding()
    first = VectorIndexing(
        vector_store=_RecordingVectorStore(),
        doc_store=_RecordingDocStore(),
        embedding=first_embedding,
        embedding_cache_dir=str(tmp_path),
        index_contract="index-v1",
    )
    first(text=Document(text="contract chunk", id_="doc-1"))

    revised_embedding = _RevisionTwoEmbedding()
    revised = VectorIndexing(
        vector_store=_RecordingVectorStore(),
        doc_store=_RecordingDocStore(),
        embedding=revised_embedding,
        embedding_cache_dir=str(tmp_path),
        index_contract="index-v1",
    )
    revised(text=Document(text="contract chunk", id_="doc-2"))

    revised_index_embedding = _RevisionTwoEmbedding()
    revised_index = VectorIndexing(
        vector_store=_RecordingVectorStore(),
        doc_store=_RecordingDocStore(),
        embedding=revised_index_embedding,
        embedding_cache_dir=str(tmp_path),
        index_contract="index-v2",
    )
    revised_index(text=Document(text="contract chunk", id_="doc-3"))

    assert first_embedding.calls == 1
    assert revised_embedding.calls == 1
    assert revised_index_embedding.calls == 1


def test_sparse_tie_order_is_independent_of_docstore_return_order():
    docs = [
        Document(
            text="Alpha result",
            id_="alpha",
            metadata={"_sparse_retrieval_score": 0.75},
        ),
        Document(
            text="Beta result",
            id_="beta",
            metadata={"_sparse_retrieval_score": 0.75},
        ),
    ]

    def run(values):
        retrieval = VectorRetrieval(
            vector_store=_RecordingVectorStore(),
            doc_store=_RecordingDocStore(values),
            embedding=_CountingEmbedding(),
            retrieval_mode="text",
            top_k=1,
        )
        return retrieval(text="result", scope=["alpha", "beta"], sparse_top_k=2)

    forward = run(docs)
    reversed_result = run(list(reversed(docs)))

    assert [doc.doc_id for doc in forward] == [doc.doc_id for doc in reversed_result]
    assert forward[0].retrieval_metadata["sparse_score"] == 0.75


def test_hybrid_sparse_tie_order_is_independent_of_docstore_return_order():
    docs = [
        Document(
            text="Alpha result",
            id_="alpha",
            metadata={"_sparse_retrieval_score": 0.75},
        ),
        Document(
            text="Beta result",
            id_="beta",
            metadata={"_sparse_retrieval_score": 0.75},
        ),
    ]

    def run(values):
        retrieval = VectorRetrieval(
            vector_store=_RecordingVectorStore(),
            doc_store=_RecordingDocStore(values),
            embedding=_CountingEmbedding(),
            retrieval_mode="hybrid",
            top_k=1,
        )
        return retrieval(text="result", scope=["alpha", "beta"], sparse_top_k=2)

    forward = run(docs)
    reversed_result = run(list(reversed(docs)))

    assert [doc.doc_id for doc in forward] == [doc.doc_id for doc in reversed_result]


def test_vector_indexing_refreshes_after_batch_and_records_status(tmp_path):
    vector_store = _RecordingVectorStore()
    pipeline = VectorIndexing(
        vector_store=vector_store,
        doc_store=_RecordingDocStore(),
        embedding=_CountingEmbedding(),
        embedding_cache_dir=str(tmp_path),
    )

    pipeline(text=[Document(text="alpha", id_="a"), Document(text="beta", id_="b")])

    assert vector_store.refresh_calls == 1
    indexing_status = pipeline.last_indexing_status
    assert indexing_status is not None
    assert indexing_status["status"] == "completed"
    assert indexing_status["stages"]["embed"]["count"] == 2
    assert indexing_status["stages"]["vector_write"]["count"] == 2
    assert indexing_status["stages"]["docstore_write"]["count"] == 2
    assert indexing_status["stages"]["refresh"]["count"] == 1


def test_vector_retrieval_exposes_trace_for_multi_document_results():
    docs = [
        Document(
            text="Alpha",
            id_="alpha",
            metadata={
                "source_id": "source-a",
                "file_name": "a.pdf",
                "page_number": 1,
                "element_type": "text",
            },
        ),
        Document(
            text="Beta",
            id_="beta",
            metadata={
                "source_id": "source-b",
                "file_name": "b.pdf",
                "page_number": 2,
                "element_type": "figure",
            },
        ),
    ]
    retrieval = VectorRetrieval(
        vector_store=_RecordingVectorStore(["alpha", "beta"]),
        doc_store=_RecordingDocStore(docs),
        embedding=_CountingEmbedding(),
        retrieval_mode="vector",
        top_k=2,
    )

    result = retrieval(text="compare figures", do_extend=True)

    assert [doc.doc_id for doc in result] == ["alpha", "beta"]
    trace = retrieval.last_trace
    assert trace is not None
    assert trace["query"] == "compare figures"
    assert trace["elements"][0]["source_id"] == "source-a"
    assert trace["elements"][1]["element_type"] == "figure"
    assert trace["multi_document_summary"]["total_files"] == 2
