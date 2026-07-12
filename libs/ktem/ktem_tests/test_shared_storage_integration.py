from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import sha256
from types import SimpleNamespace
from typing import Any, cast

import pytest
from ktem.index.file.deletion import DeletionCoordinator
from ktem.index.file.pipelines import IndexPipeline
from ktem.index.file.storage_lifetime import StorageLifetime
from sqlalchemy import Column, String, create_engine, select
from sqlalchemy.orm import Session, declarative_base


@pytest.fixture()
def shared_storage_db(tmp_path):
    base = declarative_base()

    class Source(base):  # type: ignore[misc, valid-type]
        __tablename__ = "source"
        id = Column(String, primary_key=True)
        name = Column(String, nullable=False)
        path = Column(String, nullable=False)
        user = Column(String, nullable=False)

    class IndexRow(base):  # type: ignore[misc, valid-type]
        __tablename__ = "index_row"
        id = Column(String, primary_key=True)
        source_id = Column(String, nullable=False)
        target_id = Column(String, nullable=False)
        relation_type = Column(String, nullable=False)

    engine = create_engine(f"sqlite:///{tmp_path / 'shared.sqlite'}")
    base.metadata.create_all(engine)
    storage = tmp_path / "storage"
    storage.mkdir()
    (storage / "shared.bin").write_bytes(b"document")
    return engine, Source, IndexRow, storage


def _add_source(shared_storage_db, file_id: str, user_id: str) -> None:
    engine, source_table, _index_table, _storage = shared_storage_db
    with Session(engine) as session:
        session.add(
            source_table(
                id=file_id,
                name=f"{file_id}.pdf",
                path="shared.bin",
                user=user_id,
            )
        )
        session.commit()


def _coordinator(shared_storage_db, lifetime) -> DeletionCoordinator:
    engine, source_table, index_table, storage = shared_storage_db
    kwargs: dict[str, Any] = {
        "engine": engine,
        "source_table": source_table,
        "index_table": index_table,
        "vector_store": None,
        "doc_store": None,
        "file_storage_path": storage,
        "storage_lifetime": lifetime,
    }
    return DeletionCoordinator(**kwargs)


def _source_ids(shared_storage_db) -> set[str]:
    engine, source_table, _index_table, _storage = shared_storage_db
    with Session(engine) as session:
        return set(session.scalars(select(source_table.id)))


def test_concurrent_deletes_remove_shared_blob_only_after_last_reference(
    shared_storage_db,
):
    _add_source(shared_storage_db, "file-1", "user-1")
    _add_source(shared_storage_db, "file-2", "user-2")
    storage = shared_storage_db[3]
    start = threading.Barrier(2)

    def delete(file_id: str, user_id: str) -> str:
        start.wait(timeout=5)
        lifetime = StorageLifetime(storage)
        return (
            _coordinator(shared_storage_db, lifetime)
            .delete(file_id, user_id=user_id)
            .file_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(delete, "file-1", "user-1")
        second = executor.submit(delete, "file-2", "user-2")
        assert {first.result(timeout=10), second.result(timeout=10)} == {
            "file-1",
            "file-2",
        }

    assert _source_ids(shared_storage_db) == set()
    assert not (storage / "shared.bin").exists()


def test_upload_commit_under_same_lock_wins_against_waiting_delete(
    shared_storage_db,
):
    _add_source(shared_storage_db, "file-old", "user-old")
    engine, source_table, _index_table, storage = shared_storage_db
    lifetime = StorageLifetime(storage)
    delete_attempted = threading.Event()

    class _SignallingLifetime:
        @contextmanager
        def hold(self, stored_path):
            delete_attempted.set()
            with lifetime.hold(stored_path) as lease:
                yield lease

    with ThreadPoolExecutor(max_workers=1) as executor:
        with lifetime.hold("shared.bin") as upload_lease:
            deleted = executor.submit(
                _coordinator(shared_storage_db, _SignallingLifetime()).delete,
                "file-old",
                user_id="user-old",
            )
            assert delete_attempted.wait(5)
            upload_lease.publish_from(storage / "shared.bin")
            with Session(engine) as session:
                session.add(
                    source_table(
                        id="file-new",
                        name="new.pdf",
                        path="shared.bin",
                        user="user-new",
                    )
                )
                session.commit()

        assert deleted.result(timeout=10).file_id == "file-old"

    assert _source_ids(shared_storage_db) == {"file-new"}
    assert (storage / "shared.bin").read_bytes() == b"document"


def test_store_file_holds_shared_path_lock_through_source_commit(
    monkeypatch,
    tmp_path,
):
    storage = tmp_path / "storage"
    storage.mkdir()
    upload = tmp_path / "upload.pdf"
    upload.write_bytes(b"document")
    stored_path = sha256(b"document").hexdigest()
    active = False
    published: list[str] = []

    class _Lease:
        def publish_from(self, source) -> None:
            assert active
            assert source == upload
            (storage / stored_path).write_bytes(source.read_bytes())
            published.append(stored_path)

    class _Lifetime:
        @contextmanager
        def hold(self, path):
            nonlocal active
            assert path == stored_path
            active = True
            try:
                yield _Lease()
            finally:
                active = False

    class _Source:
        id = "file-new"

        def __init__(self, **values):
            self.values = values

    class _Session:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def add(self, source) -> None:
            assert active
            assert source.values["path"] == stored_path

        def commit(self) -> None:
            assert active

    monkeypatch.setattr("ktem.index.file.pipelines.Session", lambda _engine: _Session())
    pipeline = cast(
        IndexPipeline,
        SimpleNamespace(
            FSPath=storage,
            Source=_Source,
            user_id="user-new",
            _storage_lifetime=_Lifetime(),
        ),
    )

    file_id = IndexPipeline.store_file(pipeline, upload)

    assert file_id == "file-new"
    assert published == [stored_path]
