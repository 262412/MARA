from kotaemon.storages import LanceDBDocumentStore


def test_scoped_fts_supplements_partial_postfilter_results():
    scoped_rows = [
        {
            "id": "chunk-introduction",
            "text": "Parallel data supports semantic role induction.",
            "attributes": "{}",
            "_score": 0.9,
        },
        {
            "id": "chunk-main-results",
            "text": (
                "The multilingual model obtains small improvements in both "
                "languages from this parallel data setup."
            ),
            "attributes": "{}",
        },
    ]

    class FakeLanceSearch:
        def __init__(self, docs):
            self.docs = list(docs)

        def where(self, _query_filter, prefilter=True):
            return self

        def limit(self, top_k):
            self.docs = self.docs[:top_k]
            return self

        def to_list(self):
            return self.docs

    class FakeLanceCollection:
        def search(self, query=None, query_type=None):
            if query_type == "fts":
                return FakeLanceSearch(scoped_rows[:1])
            assert query is None
            return FakeLanceSearch(scoped_rows)

    class FakeLanceConnection:
        @staticmethod
        def open_table(_collection_name):
            return FakeLanceCollection()

    store = LanceDBDocumentStore.__new__(LanceDBDocumentStore)
    store.collection_name = "docstore"
    store.db_connection = FakeLanceConnection()

    docs = store.query(
        "Overall, does having parallel data improve semantic role induction "
        "across multiple languages?",
        doc_ids=["chunk-introduction", "chunk-main-results"],
        top_k=10,
    )

    assert {doc.doc_id for doc in docs} == {
        "chunk-introduction",
        "chunk-main-results",
    }
