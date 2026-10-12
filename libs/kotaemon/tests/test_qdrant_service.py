import json
import math
import os
from types import SimpleNamespace

import pytest
from qdrant_client import QdrantClient

from kotaemon.storages import QdrantVectorStore

from .test_qdrant_local import documents


def assert_peer_reader_observes_collection(client, namespace=None):
    writer = QdrantVectorStore(
        collection_name="shared",
        client=client,
        namespace=namespace,
        mara_compatibility=True,
    )
    reader = QdrantVectorStore(
        collection_name="shared",
        client=client,
        namespace=namespace,
        mara_compatibility=True,
    )
    try:
        assert reader.count() == 0
        writer.add(documents())
        assert reader.query([1.0, 0.0])[2] == ["file-A/chunk-1"]
    finally:
        writer.close()
        reader.close()


def test_client_opened_before_writer_reads_newly_created_collection():
    client = QdrantClient(":memory:")
    try:
        assert_peer_reader_observes_collection(client)
    finally:
        client.close()


def test_server_namespace_preserves_mara_ids_payloads_and_l2_scores():
    client = QdrantClient(":memory:")
    first = QdrantVectorStore(
        collection_name="docs",
        client=client,
        namespace="first",
        mara_compatibility=True,
    )
    second = QdrantVectorStore(
        collection_name="docs",
        client=client,
        namespace="second",
        mara_compatibility=True,
    )
    try:
        assert first.count() == second.count() == 0
        first.add(documents())
        assert second.count() == 0
        _, scores, ids = first.query([1.0, 0.0], top_k=3, ids=["0007"])
        assert ids == ["0007"]
        nodes = first._client.get_nodes()
        assert all(node.source == "synthetic-file" for node in nodes)
        assert all(node.mimetype == "text/markdown" for node in nodes)
        assert scores == pytest.approx([math.exp(-1)])
        first.delete(["0007"])
        assert first.count() == 2
        assert first.__persist_flow__()["collection_name"] == "docs"
        assert first.__persist_flow__()["namespace"] == "first"
    finally:
        first.close()
        second.close()
        assert client.get_collections().collections
        client.close()


@pytest.fixture
def service_options(tmp_path):
    from .qdrant_test_runtime import clear_service_namespace, service_options

    url = os.environ.get("MARA_TEST_QDRANT_URL")
    if not url:
        pytest.skip("Set MARA_TEST_QDRANT_URL to an owned Qdrant test service")
    try:
        yield service_options(tmp_path)
    finally:
        clear_service_namespace(tmp_path)


def test_real_server_reader_observes_another_clients_new_collection(service_options):
    client = QdrantClient(
        url=service_options["url"], api_key=service_options["api_key"]
    )
    try:
        assert_peer_reader_observes_collection(client, service_options["namespace"])
    finally:
        client.close()


def test_real_server_migration_is_bound_to_source_and_destination(
    tmp_path, service_options
):
    from kotaemon.storages.vectorstores.migration import (
        import_snapshot,
        require_verified_migration,
        tree_hashes,
        verify_snapshot,
    )

    from .test_vector_migration import write_export

    export, target, legacy = (
        tmp_path / name for name in ("export", "receipt", "legacy")
    )
    write_export(export)
    legacy.mkdir()
    (legacy / "chroma.sqlite3").write_bytes(b"synthetic stopped source")
    path = export / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(source=str(legacy.resolve()), source_files=tree_hashes(legacy))
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert import_snapshot(export, target, **service_options)["points"] == 3
    assert verify_snapshot(export, target, **service_options)["points"] == 3
    with pytest.raises(FileExistsError, match="namespace"):
        import_snapshot(export, tmp_path / "second-receipt", **service_options)
    config = {
        **service_options,
        "mara_compatibility": True,
        "legacy_path": legacy,
        "migration_path": target,
        "collection_name": "documents",
    }
    store = QdrantVectorStore(**config)
    try:
        assert store.count() == 3
        with pytest.raises(ValueError, match="different Qdrant destination"):
            verify_snapshot(
                export, target, **{**service_options, "namespace": "different"}
            )
        _, scores, ids = store.query([1.0, 0.0], top_k=3)
        assert ids == ["file-A/chunk-1", "0007", "中文 ID"]
        assert scores == pytest.approx([math.exp(-0.4), math.exp(-1), math.exp(-5)])
        assert store.query([1.0, 0.0], doc_ids=["source-B"])[2] == ["0007"]
        restored = QdrantVectorStore(**store.__persist_flow__())
        try:
            assert restored.count() == 3
        finally:
            restored.close()
        with pytest.raises(RuntimeError, match="migration"):
            require_verified_migration(
                legacy, target, url=service_options["url"], namespace="different"
            )
        store._client.client.delete_collection(
            service_options["namespace"] + "__mara_migration"
        )
        with pytest.raises(RuntimeError, match="does not contain"):
            QdrantVectorStore(**config)
        assert store.count() == 3
    finally:
        store.close()


@pytest.mark.parametrize("namespace", ["../outside", "a__b", ""])
def test_invalid_namespace_is_rejected_before_connecting(namespace):
    with pytest.raises(ValueError):
        QdrantVectorStore(
            collection_name="docs", namespace=namespace, mara_compatibility=True
        )


@pytest.mark.parametrize(
    "version,accepted",
    [("1.18.0", False), ("1.19.1", False), ("1.19.2", True), ("1.20.0", True)],
)
def test_default_service_requires_security_fixed_server(version, accepted):
    from kotaemon.storages.vectorstores.qdrant_service_migration import (
        require_server_version,
    )

    client = SimpleNamespace(info=lambda: SimpleNamespace(version=version))
    if accepted:
        require_server_version(client)
    else:
        with pytest.raises(RuntimeError, match="1.19.2"):
            require_server_version(client)
