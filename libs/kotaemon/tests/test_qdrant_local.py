import math

import pytest
from llama_index.core.schema import NodeRelationship, RelatedNodeInfo
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters

from kotaemon.base import DocumentWithEmbedding
from kotaemon.storages import QdrantVectorStore


@pytest.fixture
def stores(tmp_path):
    opened = []

    def create(name="documents"):
        store = QdrantVectorStore(path=tmp_path / "qdrant", collection_name=name)
        opened.append(store)
        return store

    yield create
    for store in opened:
        store.close()


def documents():
    return [
        DocumentWithEmbedding(
            id_=identifier,
            text=text,
            source="synthetic-file",
            channel="index",
            mimetype="text/markdown",
            embedding=embedding,
            metadata={"group": group, "title": "中文 / café"},
            relationships={NodeRelationship.SOURCE: RelatedNodeInfo(node_id=source)},
        )
        for identifier, text, embedding, group, source in [
            ("file-A/chunk-1", "第一段", [0.8, 0.6], "a", "source-A"),
            ("0007", "second", [2.0, 0.0], "b", "source-B"),
            ("中文 ID", "third", [0.0, 2.0], "a", "source-A"),
        ]
    ]


def test_local_ids_payload_scores_and_scopes(stores):
    store = stores()
    docs = documents()
    assert store.count() == 0
    assert store.add(docs) == [doc.id_ for doc in docs]
    assert store.count() == 3
    _, scores, ids = store.query([1.0, 0.0], top_k=3)
    assert ids == ["file-A/chunk-1", "0007", "中文 ID"]
    assert scores == pytest.approx([math.exp(-0.4), math.exp(-1), math.exp(-5)])
    assert store.query([1.0, 0.0], top_k=3, ids=["0007"])[2] == ["0007"]
    assert store.query([1.0, 0.0], top_k=3, doc_ids=["source-B"])[2] == ["0007"]
    filtered = store.query(
        [1.0, 0.0],
        top_k=3,
        filters=MetadataFilters(filters=[MetadataFilter(key="group", value="a")]),
    )
    assert filtered[2] == ["file-A/chunk-1", "中文 ID"]
    nodes = store._client.get_nodes()
    assert {
        node.id_: (node.text, node.metadata, node.ref_doc_id) for node in nodes
    } == {doc.id_: (doc.text, doc.metadata, doc.ref_doc_id) for doc in docs}


def test_local_shared_client_close_and_reopen(stores):
    first, second = stores("first"), stores("second")
    first.add(documents())
    second.add([[1.0, 0.0]], ids=["other"])
    first.close()
    first.close()
    assert second.count() == 1
    with pytest.raises(RuntimeError, match="closed"):
        first.count()
    second.close()
    reopened = stores("first")
    assert reopened.count() == 3
    reopened.delete(["file-A/chunk-1"])
    reopened.close()
    again = stores("first")
    assert again.count() == 2
    assert again.query([1.0, 0.0], top_k=3)[2] == ["0007", "中文 ID"]


def test_local_empty_scopes_do_not_expand_to_all_documents(stores):
    store = stores()
    assert store.add([]) == []
    assert store.query([1.0, 0.0]) == ([], [], [])
    store.add(documents())
    assert store.query([1.0, 0.0], ids=[]) == ([], [], [])
    assert store.query([1.0, 0.0], doc_ids=[]) == ([], [], [])


def test_delete_from_an_empty_store_is_idempotent(stores):
    store = stores()
    store.delete(["never-indexed"])
    store.delete([])
    assert store.count() == 0


def test_local_configuration_round_trip(stores):
    from theflow.utils.modules import deserialize

    store = stores()
    store.add(documents())
    config = {
        "__type__": "kotaemon.storages.QdrantVectorStore",
        **store.__persist_flow__(),
    }
    restored = deserialize(config, safe=False)
    try:
        assert restored.count() == 3
        assert restored.query([1.0, 0.0])[2] == ["file-A/chunk-1"]
    finally:
        restored.close()


@pytest.mark.parametrize("name", ["../outside", "/absolute", "x\\y", "..", ""])
def test_local_collection_names_cannot_escape_storage(tmp_path, name):
    with pytest.raises(ValueError, match="collection name"):
        QdrantVectorStore(path=tmp_path / "target", collection_name=name)
    assert not (tmp_path / "target").exists()


def test_default_refuses_legacy_data_before_creating_target(tmp_path):
    legacy = tmp_path / "legacy"
    legacy.mkdir()
    (legacy / "chroma.sqlite3").write_bytes(b"legacy")
    with pytest.raises(RuntimeError, match="verified migration"):
        QdrantVectorStore(
            path=tmp_path / "target", legacy_path=legacy, collection_name="docs"
        )
    assert not (tmp_path / "target").exists()


def test_local_rejects_existing_incompatible_metric(tmp_path):
    from qdrant_client import QdrantClient, models

    client = QdrantClient(path=tmp_path)
    client.create_collection(
        "docs",
        vectors_config={
            "text-dense": models.VectorParams(size=2, distance=models.Distance.COSINE)
        },
    )
    client.close()
    with pytest.raises(ValueError, match="Euclidean"):
        QdrantVectorStore(path=tmp_path, collection_name="docs")
    # A rejected open must release the local client lease and its file lock.
    client = QdrantClient(path=tmp_path)
    assert client.collection_exists("docs")
    client.close()
