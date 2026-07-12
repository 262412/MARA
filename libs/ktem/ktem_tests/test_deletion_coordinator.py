from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

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

    class Source(base):  # type: ignore[misc, valid-type]
        __tablename__ = "source"
        id = Column(String, primary_key=True)
        name = Column(String, nullable=False)
        path = Column(String, nullable=False, default="")
        size = Column(Integer, nullable=False, default=0)
        user = Column(String, nullable=False, default="")

    class IndexRow(base):  # type: ignore[misc, valid-type]
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
    if (
        stored_path
        and not Path(stored_path).is_absolute()
        and ".." not in Path(stored_path).parts
    ):
        target = storage / stored_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"document")


def _row_counts(deletion_db) -> tuple[int, int]:
    engine, source_table, index_table, _storage = deletion_db
    with Session(engine) as session:
        return (
            int(session.scalar(select(func.count()).select_from(source_table)) or 0),
            int(session.scalar(select(func.count()).select_from(index_table)) or 0),
        )


def _source_ids(deletion_db) -> set[str]:
    engine, source_table, _index_table, _storage = deletion_db
    with Session(engine) as session:
        return set(session.scalars(select(source_table.id)))


def _coordinator(
    deletion_db,
    *,
    vector_store=None,
    doc_store=None,
    session_factory=None,
    file_mover=None,
    file_unlinker=None,
    storage_lifetime=None,
    artifact_cleaner=None,
):
    engine, source_table, index_table, storage = deletion_db
    kwargs: dict[str, Any] = {
        "engine": engine,
        "source_table": source_table,
        "index_table": index_table,
        "vector_store": vector_store,
        "doc_store": doc_store,
        "file_storage_path": storage,
        "session_factory": session_factory,
        "file_unlinker": file_unlinker,
    }
    if file_mover is not None:
        kwargs["file_mover"] = file_mover
    if storage_lifetime is not None:
        kwargs["storage_lifetime"] = storage_lifetime
    if artifact_cleaner is not None:
        kwargs["artifact_cleaner"] = artifact_cleaner
    return DeletionCoordinator(
        **kwargs,
    )


def test_deleting_one_of_two_sources_sharing_path_keeps_physical_blob(deletion_db):
    _seed_file(deletion_db, file_id="file-1", stored_path="shared.bin")
    _seed_file(deletion_db, file_id="file-2", stored_path="shared.bin")

    _coordinator(deletion_db).delete("file-1", user_id="user-1")

    assert _source_ids(deletion_db) == {"file-2"}
    assert (deletion_db[3] / "shared.bin").read_bytes() == b"document"


def test_deleting_last_source_reference_unlinks_physical_blob(deletion_db):
    _seed_file(deletion_db, file_id="file-1", stored_path="shared.bin")

    _coordinator(deletion_db).delete("file-1", user_id="user-1")

    assert _source_ids(deletion_db) == set()
    assert not (deletion_db[3] / "shared.bin").exists()


def test_reference_count_is_global_across_owners(deletion_db):
    _seed_file(
        deletion_db,
        file_id="owner-file",
        user_id="owner-1",
        stored_path="shared.bin",
    )
    _seed_file(
        deletion_db,
        file_id="other-owner-file",
        user_id="owner-2",
        stored_path="shared.bin",
    )

    _coordinator(deletion_db).delete("owner-file", user_id="owner-1")

    assert _source_ids(deletion_db) == {"other-owner-file"}
    assert (deletion_db[3] / "shared.bin").read_bytes() == b"document"


def test_deletes_all_docstore_relations_then_sql(deletion_db):
    _seed_file(deletion_db)
    vectors = _Store({"vector-1"})
    documents = _Store({"document-1", "element-1", "graph-1"})

    result = _coordinator(
        deletion_db, vector_store=vectors, doc_store=documents
    ).delete("file-1", user_id="user-1")

    assert (result.file_id, result.name) == ("file-1", "report.pdf")
    assert vectors.calls == [["vector-1"]]
    assert documents.calls == [["document-1"], ["element-1"], ["graph-1"]]
    assert not (deletion_db[3] / "stored.bin").exists()
    assert _row_counts(deletion_db) == (0, 0)


@pytest.mark.parametrize("failed_stage", ["vector", "docstore"])
def test_external_failure_retains_sql_and_retry_is_safe(deletion_db, failed_stage):
    _seed_file(deletion_db)
    vectors = _Store(
        {"vector-1"},
        failure=RuntimeError("vector unavailable")
        if failed_stage == "vector"
        else None,
    )
    documents = _Store(
        {"document-1", "element-1", "graph-1"},
        failure=RuntimeError("docstore unavailable")
        if failed_stage == "docstore"
        else None,
    )

    coordinator = _coordinator(
        deletion_db,
        vector_store=vectors,
        doc_store=documents,
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


def test_postcommit_unlink_failure_is_logged_as_an_auditable_orphan(
    deletion_db,
    caplog,
):
    _seed_file(deletion_db)
    attempted: list[Path] = []

    def fail_unlink(path: Path) -> None:
        attempted.append(path)
        raise OSError("post-commit unlink unavailable")

    result = _coordinator(deletion_db, file_unlinker=fail_unlink).delete(
        "file-1", user_id="user-1"
    )

    assert result.file_id == "file-1"
    assert _row_counts(deletion_db) == (0, 0)
    assert len(attempted) == 1
    orphan = attempted[0]
    assert orphan.parent == deletion_db[3]
    assert orphan.name.startswith(".stored.bin.quarantine-")
    assert orphan.read_bytes() == b"document"
    assert any(
        record.levelname == "ERROR"
        and "orphan" in record.getMessage().lower()
        and str(orphan) in record.getMessage()
        for record in caplog.records
    )


def test_quarantine_move_failure_retains_rows_and_original_blob(deletion_db):
    _seed_file(deletion_db)
    attempted: list[tuple[Path, Path]] = []

    def fail_move(source: Path, quarantine: Path) -> None:
        attempted.append((source, quarantine))
        raise OSError("quarantine move unavailable")

    with pytest.raises(DeletionError, match="disk") as exc_info:
        _coordinator(deletion_db, file_mover=fail_move).delete(
            "file-1", user_id="user-1"
        )

    assert exc_info.value.stage == "disk"
    assert _row_counts(deletion_db) == (1, 4)
    assert (deletion_db[3] / "stored.bin").read_bytes() == b"document"
    assert len(attempted) == 1
    source, quarantine = attempted[0]
    assert source == deletion_db[3] / "stored.bin"
    assert quarantine.parent == deletion_db[3]
    assert quarantine.name.startswith(".stored.bin.quarantine-")


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


def test_one_missing_docstore_target_does_not_skip_later_targets(deletion_db):
    _seed_file(deletion_db)

    class _MissingRaisesStore:
        def __init__(self):
            self.values = {"document-1", "graph-1"}

        def delete(self, values):
            for value in values:
                if value not in self.values:
                    raise KeyError(value)
                self.values.remove(value)

    documents = _MissingRaisesStore()
    _coordinator(
        deletion_db,
        vector_store=_Store({"vector-1"}),
        doc_store=documents,
    ).delete("file-1", user_id="user-1")

    assert documents.values == set()
    assert _row_counts(deletion_db) == (0, 0)


def test_user_scope_is_revalidated_before_any_external_delete(deletion_db):
    _seed_file(deletion_db)
    vectors = _Store({"vector-1"})
    documents = _Store({"document-1", "element-1", "graph-1"})

    with pytest.raises(DeletionError, match="validate") as exc_info:
        _coordinator(deletion_db, vector_store=vectors, doc_store=documents).delete(
            "file-1", user_id="user-2"
        )

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


def test_storage_symlink_inside_root_is_rejected_without_unlinking_target(deletion_db):
    _seed_file(deletion_db)
    victim = deletion_db[3] / "victim.bin"
    victim.write_bytes(b"keep")
    stored = deletion_db[3] / "stored.bin"
    stored.unlink()
    stored.symlink_to(victim)

    with pytest.raises(DeletionError, match="validate"):
        _coordinator(deletion_db).delete("file-1", user_id="user-1")

    assert stored.is_symlink()
    assert victim.read_bytes() == b"keep"
    assert _row_counts(deletion_db) == (1, 4)


def test_storage_directory_is_rejected_and_rows_remain_retryable(deletion_db):
    _seed_file(deletion_db)
    stored = deletion_db[3] / "stored.bin"
    stored.unlink()
    stored.mkdir()

    with pytest.raises(DeletionError, match="disk"):
        _coordinator(deletion_db).delete("file-1", user_id="user-1")

    assert stored.is_dir()
    assert _row_counts(deletion_db) == (1, 4)


def test_sql_commit_failure_restores_quarantined_blob_for_retry(deletion_db):
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
    assert (deletion_db[3] / "stored.bin").read_bytes() == b"document"
    result = _coordinator(
        deletion_db, vector_store=_Store(set()), doc_store=_Store(set())
    ).delete("file-1", user_id="user-1")
    assert result.file_id == "file-1"
    assert _row_counts(deletion_db) == (0, 0)


def test_file_id_artifacts_are_removed_without_touching_other_namespace(
    deletion_db,
    tmp_path,
):
    _seed_file(deletion_db, stored_path="shared.bin")
    roots = {
        "chunks": tmp_path / "chunks",
        "markdown": tmp_path / "markdown",
        "manifests": tmp_path / "zip" / "manifests" / "v1",
    }
    for root in roots.values():
        for file_id, marker in (
            ("file-1", b"OWNER"),
            ("file-other", b"OTHER"),
            ("shared.bin", b"SHARED-HASH"),
        ):
            path = root / file_id
            path.mkdir(parents=True, exist_ok=True)
            (path / "artifact.bin").write_bytes(marker)

    def clean(file_id: str) -> None:
        for root in roots.values():
            shutil.rmtree(root / file_id)

    _coordinator(deletion_db, artifact_cleaner=clean).delete("file-1", user_id="user-1")

    assert all(not (root / "file-1").exists() for root in roots.values())
    assert all((root / "file-other").is_dir() for root in roots.values())
    assert all((root / "shared.bin").is_dir() for root in roots.values())


def test_artifact_cleanup_failure_retains_sql_and_blob_for_retry(deletion_db):
    _seed_file(deletion_db)

    def fail_cleanup(_file_id: str) -> None:
        raise OSError("artifact root unavailable")

    with pytest.raises(DeletionError) as exc_info:
        _coordinator(deletion_db, artifact_cleaner=fail_cleanup).delete(
            "file-1", user_id="user-1"
        )

    assert exc_info.value.stage == "artifacts"
    assert _row_counts(deletion_db) == (1, 4)
    assert (deletion_db[3] / "stored.bin").read_bytes() == b"document"
