import json
import os
import subprocess
import sys

import pytest


def write_export(root, *, broken=False):
    from kotaemon.storages.vectorstores.migration import file_sha256

    from .test_qdrant_local import documents

    root.mkdir()
    records = root / "records.jsonl"
    docs = documents()
    with records.open("w", encoding="utf-8") as stream:
        for doc in docs:
            row = {
                "collection": "documents",
                "id": doc.id_,
                "embedding": doc.embedding,
                "document": doc.text,
                "metadata": {"_node_content": doc.to_json()},
            }
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    manifest = {
        "format": 1,
        "source": str(root.parent / "legacy"),
        "source_files": {},
        "records_sha256": "bad" if broken else file_sha256(records),
        "collections": [
            {"name": "documents", "count": 3, "dimension": 2, "metric": "l2"}
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return docs


def test_migration_verifies_payload_and_reopen(tmp_path):
    from kotaemon.storages import QdrantVectorStore
    from kotaemon.storages.vectorstores.migration import (
        import_snapshot,
        verify_snapshot,
    )

    export, target = tmp_path / "export", tmp_path / "target"
    docs = write_export(export)
    assert import_snapshot(export, target)["points"] == 3
    assert verify_snapshot(export, target)["points"] == 3
    store = QdrantVectorStore(path=target, collection_name="documents")
    try:
        assert store.query([1.0, 0.0], top_k=3)[2] == [doc.id_ for doc in docs]
        store.delete([docs[0].id_])
    finally:
        store.close()
    with pytest.raises(ValueError, match="count"):
        verify_snapshot(export, target)


@pytest.mark.parametrize(
    "invalid", ["hash", "metric", "collection", "duplicate", "dimension"]
)
def test_invalid_export_is_rejected_before_target_creation(tmp_path, invalid):
    from kotaemon.storages.vectorstores.migration import file_sha256, import_snapshot

    export, target = tmp_path / "export", tmp_path / "target"
    write_export(export, broken=invalid == "hash")
    manifest_path = export / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if invalid == "metric":
        manifest["collections"][0]["metric"] = "cosine"
    if invalid == "collection":
        manifest["collections"][0]["name"] = "../outside"
    if invalid in {"duplicate", "dimension"}:
        records = export / "records.jsonl"
        rows = [
            json.loads(line)
            for line in records.read_text(encoding="utf-8").splitlines()
        ]
        if invalid == "duplicate":
            rows[1] = rows[0]
        else:
            rows[1]["embedding"] = [1.0]
        records.write_text(
            "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
        )
        manifest["records_sha256"] = file_sha256(records)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError):
        import_snapshot(export, target)
    assert not target.exists()


def test_migration_refuses_existing_target(tmp_path):
    from kotaemon.storages.vectorstores.migration import import_snapshot

    export, target = tmp_path / "export", tmp_path / "target"
    write_export(export)
    target.mkdir()
    sentinel = target / "user-file"
    sentinel.write_text("keep", encoding="utf-8")
    with pytest.raises(FileExistsError):
        import_snapshot(export, target)
    assert sentinel.read_text(encoding="utf-8") == "keep"


def test_legacy_default_requires_source_bound_completed_migration(tmp_path):
    from kotaemon.storages.vectorstores.migration import (
        default_vectorstore,
        import_snapshot,
        require_verified_migration,
        tree_hashes,
    )

    legacy = tmp_path / "vectorstore"
    legacy.mkdir()
    database = legacy / "chroma.sqlite3"
    database.write_bytes(b"legacy database")
    target = tmp_path / "vectorstore_qdrant"
    with pytest.raises(RuntimeError, match="migrate_chroma_to_qdrant"):
        require_verified_migration(legacy, target)
    export = tmp_path / "export"
    write_export(export)
    path = export / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(source=str(legacy.resolve()), source_files=tree_hashes(legacy))
    path.write_text(json.dumps(manifest), encoding="utf-8")
    import_snapshot(export, target)
    require_verified_migration(legacy, target)
    assert default_vectorstore(tmp_path)["migration_path"] == str(target)
    database.write_bytes(b"source modified after migration")
    with pytest.raises(RuntimeError, match="changed"):
        require_verified_migration(legacy, target)


def test_new_default_is_lazy_and_uses_server(tmp_path):
    from kotaemon.storages.vectorstores.migration import (
        default_namespace,
        default_vectorstore,
    )

    assert default_vectorstore(tmp_path) == {
        "__type__": "kotaemon.storages.QdrantVectorStore",
        "url": "http://127.0.0.1:6333",
        "api_key": None,
        "namespace": default_namespace(tmp_path),
        "mara_compatibility": True,
        "migration_path": str(tmp_path / "vectorstore_qdrant"),
        "legacy_path": str(tmp_path / "vectorstore"),
    }
    assert not (tmp_path / "vectorstore_qdrant").exists()


def test_incomplete_import_never_enables_default(tmp_path, monkeypatch):
    from kotaemon.storages.vectorstores import migration

    export, target = tmp_path / "export", tmp_path / "target"
    write_export(export)

    def fail_verification(*args):
        raise ValueError("simulated verification failure")

    monkeypatch.setattr(migration, "verify_snapshot", fail_verification)
    with pytest.raises(ValueError, match="verification failure"):
        migration.import_snapshot(export, target)
    assert not (target / "mara-migration.json").exists()
    with pytest.raises(RuntimeError, match="incomplete"):
        migration.require_verified_migration(tmp_path / "absent-legacy", target)


def test_new_process_observes_import_and_delete(tmp_path):
    from kotaemon.storages.vectorstores.migration import import_snapshot

    export, target = tmp_path / "export", tmp_path / "target"
    write_export(export)
    import_snapshot(export, target)
    code = """
import json, sys
sys.path[:0] = json.loads(sys.argv[1])
from kotaemon.storages import QdrantVectorStore
store = QdrantVectorStore(path=sys.argv[2], collection_name='documents')
try:
    assert store.count() == int(sys.argv[3])
    if sys.argv[3] == '3':
        store.delete(['file-A/chunk-1'])
    else:
        assert store.query([1.0, 0.0], top_k=3)[2] == ['0007', '中文 ID']
finally:
    store.close()
"""
    for expected in (3, 2):
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                code,
                json.dumps(sys.path),
                str(target),
                str(expected),
            ],
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=90,
        )
        assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.parametrize("server", [False, True])
def test_legacy_snapshot_export_import_and_source_rollback(tmp_path, server, request):
    pytest.importorskip(
        "chromadb", reason="Executed in the isolated legacy migration job"
    )
    pytest.importorskip("llama_index.vector_stores.chroma")
    from kotaemon.storages.vectorstores.migration import (
        import_snapshot,
        tree_hashes,
        verify_snapshot,
    )
    from scripts.migrate_chroma_to_qdrant import export_snapshot

    from .chroma_test_runtime import owned_chroma_stores
    from .test_qdrant_local import documents

    source, snapshot = tmp_path / "legacy", tmp_path / "snapshot"
    export, target = tmp_path / "export", tmp_path / "target"
    docs = documents()
    options = {}
    if server:
        from .qdrant_test_runtime import clear_service_namespace, service_options

        url = os.environ.get("MARA_TEST_QDRANT_URL")
        if not url:
            pytest.skip("The server migration case requires an owned Qdrant service")
        options = service_options(tmp_path)
        request.addfinalizer(lambda: clear_service_namespace(tmp_path))
    with owned_chroma_stores(tmp_path) as create:
        legacy = create(path=source, collection_name="documents")
        legacy.add(docs)
    before = tree_hashes(source)
    assert export_snapshot(source, snapshot, export)["points"] == 3
    assert tree_hashes(source) == before
    assert import_snapshot(export, target, **options)["points"] == 3
    assert verify_snapshot(export, target, **options)["points"] == 3
    assert tree_hashes(source) == before
    with owned_chroma_stores(tmp_path) as create:
        rollback = create(path=source, collection_name="documents")
        assert rollback.count() == 3
        _, _, ids = rollback.query([1.0, 0.0], top_k=3)
        assert ids == [doc.id_ for doc in docs]


def test_empty_snapshot_can_be_verified(tmp_path):
    from kotaemon.storages.vectorstores.migration import (
        file_sha256,
        import_snapshot,
        verify_snapshot,
    )

    export, target = tmp_path / "export", tmp_path / "target"
    write_export(export)
    records = export / "records.jsonl"
    records.write_text("", encoding="utf-8")
    path = export / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(collections=[], records_sha256=file_sha256(records))
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert import_snapshot(export, target) == {"collections": 0, "points": 0}
    assert verify_snapshot(export, target) == {"collections": 0, "points": 0}
