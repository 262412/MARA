from kotaemon.base import Document, DocumentWithEmbedding
from kotaemon.indices import VectorIndexing, VectorRetrieval


class _CountingEmbedding:
    model = "counting-embedding"

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
    assert pipeline.last_indexing_status["status"] == "completed"
    assert pipeline.last_indexing_status["stages"]["embed"]["count"] == 2
    assert pipeline.last_indexing_status["stages"]["vector_write"]["count"] == 2
    assert pipeline.last_indexing_status["stages"]["docstore_write"]["count"] == 2
    assert pipeline.last_indexing_status["stages"]["refresh"]["count"] == 1


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
    assert retrieval.last_trace["query"] == "compare figures"
    assert retrieval.last_trace["elements"][0]["source_id"] == "source-a"
    assert retrieval.last_trace["elements"][1]["element_type"] == "figure"
    assert retrieval.last_trace["multi_document_summary"]["total_files"] == 2
