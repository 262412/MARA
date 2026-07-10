from __future__ import annotations

from pathlib import Path

import pytest
from ktem.index.file.deletion import DeletionCoordinator, DeletionError
from sqlalchemy import Column, Integer, String, create_engine, func, select
from sqlalchemy.orm import Session, declarative_base


class _Store:
    def __init__(self, values: set[str], *, failure: Exception | None = None):
        self.values = set(values)
        self.failure = failure
        self.calls: list[list[str]] = []

    def delete(self, values: list[str]) -> None:
        self.calls.append(list(values))
        if self.failure is not None:
            raise self.failure
        self.values.difference_update(values)


@pytest.fixture()
def deletion_db(tmp_path):
    base = declarative_base()

    class Source(base):
        __tablename__ = "source"
        id = Column(String, primary_key=True)
        name = Column(String, nullable=False)
        path = Column(String, nullable=False, default="")
        user = Column(String, nullable=False, default="")

    class IndexRow(base):
        __tablename__ = "index_row"
        id = Column(Integer, primary_key=True, autoincrement=True)
        source_id = Column(String, nullable=False)
        target_id = Column(String, nullable=False)
        relation_type = Column(String, nullable=False)
        user = Column(String, nullable=False, default="")

    engine = create_engine(f"sqlite:///{tmp_path / 'deletion.sqlite'}")
    base.metadata.create_all(engine)
    storage = tmp_path / "files"
    storage.mkdir()
    return engine, Source, IndexRow, storage


def _seed_file(
    deletion_db,
    *,
    file_id: str = "file-1",
    user_id: str = "user-1",
    stored_path: str = "stored.bin",
):
    engine, source_table, index_table, storage = deletion_db
    with Session(engine) as session:
        session.add(
            source_table(
                id=file_id,
                name="report.pdf",
                path=stored_path,
                user=user_id,
            )
        )
        for relation_type, target_id in (
            ("vector", "vector-1"),
            ("document", "document-1"),
            ("element_index", "element-1"),
            ("graph_index", "graph-1"),
        ):
            session.add(
                index_table(
                    source_id=file_id,
                    target_id=target_id,
                    relation_type=relation_type,
                    user=user_id,
                )
            )
        session.commit()
    if stored_path and not Path(stored_path).is_absolute() and ".." not in Path(
        stored_path
    ).parts:
        target = storage / stored_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"document")


def _row_counts(deletion_db) -> tuple[int, int]:
    engine, source_table, index_table, _storage = deletion_db
    with Session(engine) as session:
        return (
            session.scalar(select(func.count()).select_from(source_table)),
            session.scalar(select(func.count()).select_from(index_table)),
        )


def _coordinator(
    deletion_db,
    *,
    vector_store=None,
    doc_store=None,
    session_factory=None,
    file_unlinker=None,
):
    engine, source_table, index_table, storage = deletion_db
    return DeletionCoordinator(
        engine=engine,
        source_table=source_table,
        index_table=index_table,
        vector_store=vector_store,
        doc_store=doc_store,
        file_storage_path=storage,
        session_factory=session_factory,
        file_unlinker=file_unlinker,
    )


def test_deletes_all_docstore_relations_then_sql(deletion_db):
    _seed_file(deletion_db)
    vectors = _Store({"vector-1"})
    documents = _Store({"document-1", "element-1", "graph-1"})

    result = _coordinator(
        deletion_db, vector_store=vectors, doc_store=documents
    ).delete("file-1", user_id="user-1")

    assert (result.file_id, result.name) == ("file-1", "report.pdf")
    assert vectors.calls == [["vector-1"]]
    assert documents.calls == [["document-1", "element-1", "graph-1"]]
    assert not (deletion_db[3] / "stored.bin").exists()
    assert _row_counts(deletion_db) == (0, 0)


@pytest.mark.parametrize("failed_stage", ["vector", "docstore", "disk"])
def test_external_failure_retains_sql_and_retry_is_safe(deletion_db, failed_stage):
    _seed_file(deletion_db)
    vectors = _Store(
        {"vector-1"},
        failure=RuntimeError("vector unavailable") if failed_stage == "vector" else None,
    )
    documents = _Store(
        {"document-1", "element-1", "graph-1"},
        failure=RuntimeError("docstore unavailable")
        if failed_stage == "docstore"
        else None,
    )

    def unlink(path: Path) -> None:
        if failed_stage == "disk":
            raise OSError("disk unavailable")
        path.unlink()

    coordinator = _coordinator(
        deletion_db,
        vector_store=vectors,
        doc_store=documents,
        file_unlinker=unlink,
    )
    with pytest.raises(DeletionError, match=failed_stage) as exc_info:
        coordinator.delete("file-1", user_id="user-1")

    assert exc_info.value.stage == failed_stage
    assert exc_info.value.file_id == "file-1"
    assert _row_counts(deletion_db) == (1, 4)

    vectors.failure = None
    documents.failure = None
    result = _coordinator(
        deletion_db, vector_store=vectors, doc_store=documents
    ).delete("file-1", user_id="user-1")
    assert result.file_id == "file-1"
    assert _row_counts(deletion_db) == (0, 0)


def test_missing_external_targets_are_idempotent_success(deletion_db):
    _seed_file(deletion_db)
    (deletion_db[3] / "stored.bin").unlink()

    result = _coordinator(
        deletion_db,
        vector_store=_Store(set()),
        doc_store=_Store(set()),
    ).delete("file-1", user_id="user-1")

    assert result.file_id == "file-1"
    assert _row_counts(deletion_db) == (0, 0)


def test_user_scope_is_revalidated_before_any_external_delete(deletion_db):
    _seed_file(deletion_db)
    vectors = _Store({"vector-1"})
    documents = _Store({"document-1", "element-1", "graph-1"})

    with pytest.raises(DeletionError, match="validate") as exc_info:
        _coordinator(
            deletion_db, vector_store=vectors, doc_store=documents
        ).delete("file-1", user_id="user-2")

    assert exc_info.value.stage == "validate"
    assert vectors.calls == []
    assert documents.calls == []
    assert _row_counts(deletion_db) == (1, 4)


@pytest.mark.parametrize("stored_path", ["../outside.bin", "/tmp/outside.bin"])
def test_storage_path_escape_is_rejected_before_external_delete(
    deletion_db, stored_path
):
    _seed_file(deletion_db, stored_path=stored_path)
    vectors = _Store({"vector-1"})

    with pytest.raises(DeletionError, match="validate"):
        _coordinator(deletion_db, vector_store=vectors).delete(
            "file-1", user_id="user-1"
        )

    assert vectors.calls == []
    assert _row_counts(deletion_db) == (1, 4)


def test_storage_symlink_escape_is_rejected(deletion_db, tmp_path):
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"keep")
    _seed_file(deletion_db)
    stored = deletion_db[3] / "stored.bin"
    stored.unlink()
    stored.symlink_to(outside)

    with pytest.raises(DeletionError, match="validate"):
        _coordinator(deletion_db, vector_store=_Store({"vector-1"})).delete(
            "file-1", user_id="user-1"
        )

    assert outside.read_bytes() == b"keep"
    assert stored.is_symlink()
    assert _row_counts(deletion_db) == (1, 4)


def test_sql_commit_failure_keeps_rows_for_retry(deletion_db):
    _seed_file(deletion_db)
    engine = deletion_db[0]

    class _FailingCommitSession(Session):
        def commit(self) -> None:
            raise RuntimeError("database unavailable")

    with pytest.raises(DeletionError, match="sql") as exc_info:
        _coordinator(
            deletion_db,
            vector_store=_Store({"vector-1"}),
            doc_store=_Store({"document-1", "element-1", "graph-1"}),
            session_factory=lambda: _FailingCommitSession(engine),
        ).delete("file-1", user_id="user-1")

    assert exc_info.value.stage == "sql"
    assert _row_counts(deletion_db) == (1, 4)
    result = _coordinator(
        deletion_db, vector_store=_Store(set()), doc_store=_Store(set())
    ).delete("file-1", user_id="user-1")
    assert result.file_id == "file-1"
    assert _row_counts(deletion_db) == (0, 0)
