"""Task-owned backend and index layout receipts; no default collections."""

import pytest
from ktem.index.file.deletion import DeletionCoordinator, DeletionError
from ktem.index.file.source_storage import store_source_file
from sqlalchemy.orm import Session

from kotaemon.base import Document
from kotaemon.storages import LanceDBDocumentStore
from libs.kotaemon.tests.chroma_test_runtime import owned_chroma_stores

from . import test_deletion_coordinator as fixtures
from .test_deletion_coordinator import _coordinator, _row_counts, _seed_file

deletion_db = fixtures.deletion_db


def test_real_chroma_lancedb_delete_fts_and_external_missing_retry(
    deletion_db, tmp_path
):
    _seed_file(deletion_db)
    documents = LanceDBDocumentStore(
        str(tmp_path / "lance"), collection_name="r5a_owned_docs"
    )
    ids = ["document-1", "element-1", "graph-1", "unrelated"]
    documents.add(
        [
            Document(text="deleteunique" if i != "unrelated" else "keepunique")
            for i in ids
        ],
        ids=ids,
    )
    table = documents.db_connection.open_table(documents.collection_name)
    assert len(table.search("deleteunique", query_type="fts").to_list()) == 3
    # This configured backend has no coordinator refresh hook; test actual FTS reads.
    assert getattr(documents, "create_fts_index", None) is None
    with owned_chroma_stores(tmp_path) as create:
        vectors = create(collection_name="r5a-owned-vectors")
        vectors.add([[0.1, 0.2], [0.3, 0.4]], ids=["vector-1", "unrelated"])

        def fail_artifacts(_file):
            raise OSError("retry after external deletion")

        with pytest.raises(DeletionError) as raised:
            _coordinator(
                deletion_db,
                vector_store=vectors,
                doc_store=documents,
                artifact_cleaner=fail_artifacts,
            ).delete("file-1", user_id="user-1")
        assert raised.value.stage == "artifacts" and _row_counts(deletion_db) == (1, 4)
        assert vectors._collection.get()["ids"] == ["unrelated"]
        assert [doc.doc_id for doc in documents.get(ids)] == ["unrelated"]
        # A previously opened table is a snapshot. The production query opens anew.
        assert documents.query("deleteunique") == []
        table = documents.db_connection.open_table(documents.collection_name)
        assert table.search("deleteunique", query_type="fts").to_list() == []
        assert [
            row["id"] for row in table.search("keepunique", query_type="fts").to_list()
        ] == ["unrelated"]
        assert (
            _coordinator(deletion_db, vector_store=vectors, doc_store=documents)
            .delete("file-1", user_id="user-1")
            .file_id
            == "file-1"
        )
        assert vectors._collection.get()["ids"] == ["unrelated"]
        assert _row_counts(deletion_db) == (0, 0)
        with pytest.raises(DeletionError, match="validate"):
            _coordinator(deletion_db, vector_store=vectors, doc_store=documents).delete(
                "file-1", user_id="user-1"
            )
    documents.drop()


def test_real_file_index_layout_separates_identical_content_across_tables(
    deletion_db, tmp_path, monkeypatch
):
    from ktem.index.file import index as module

    monkeypatch.setattr(module, "filestorage_path", tmp_path / "index-storage")
    monkeypatch.setattr(module, "get_vectorstore", lambda _collection: None)
    monkeypatch.setattr(module, "get_docstore", lambda _collection: None)
    engine = deletion_db[0]
    upload = tmp_path / "owned.txt"
    upload.write_bytes(b"same content in different indices")
    instances = [
        module.FileIndex(None, i, f"index {i}", {"private": True}) for i in (101, 102)
    ]
    records = []
    for index in instances:
        resources = index._resources
        resources["Source"].metadata.create_all(engine)
        file_id = store_source_file(
            upload,
            storage_root=resources["FileStoragePath"],
            source_table=resources["Source"],
            user_id="owner",
            session_factory=lambda: Session(engine),
        )
        with Session(engine) as session:
            source = session.get(resources["Source"], file_id)
            assert source is not None
            records.append((file_id, source.path, resources))
    assert records[0][1] == records[1][1]
    assert [r[2]["Source"].__tablename__ for r in records] == [
        "index__101__source",
        "index__102__source",
    ]
    assert [r[2]["FileStoragePath"].name for r in records] == ["index_101", "index_102"]
    first_id, first_path, first = records[0]
    second_id, second_path, second = records[1]
    DeletionCoordinator(
        engine=engine,
        source_table=first["Source"],
        index_table=first["Index"],
        vector_store=None,
        doc_store=None,
        file_storage_path=first["FileStoragePath"],
    ).delete(first_id, user_id="owner")
    assert not (first["FileStoragePath"] / first_path).exists()
    assert (second["FileStoragePath"] / second_path).read_bytes() == upload.read_bytes()
    with Session(engine) as session:
        assert session.get(second["Source"], second_id) is not None
