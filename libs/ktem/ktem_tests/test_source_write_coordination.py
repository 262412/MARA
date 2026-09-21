"""Real-store deletion barriers protect both writes and relation registration."""

import logging
import os
import sys
import threading
from concurrent.futures import CancelledError
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from ktem.index.file import source_writes
from ktem.index.file.deletion import DeletionCoordinator
from ktem.index.file.source_writes import source_lock

from kotaemon.base import Document

from . import indexing_backend_test_support as support

backend = support.backend


def coordinator(backend):
    return DeletionCoordinator(
        engine=backend.engine,
        source_table=backend.resources["Source"],
        index_table=backend.resources["Index"],
        vector_store=backend.vectors,
        doc_store=backend.documents,
        file_storage_path=backend.resources["FileStoragePath"],
    )


def capture(errors, operation):
    try:
        operation()
    except BaseException as error:
        logging.getLogger(__name__).exception("Owned writer/delete operation failed")
        errors.append(error)


@pytest.mark.parametrize("stage", ["docstore", "vector"])
@pytest.mark.parametrize("threaded", [False, True])
def test_waiting_delete_recollects_targets_after_store_write_before_relation(
    backend, monkeypatch, stage, threaded
):
    backend.source.write_text("protectedunique material", encoding="utf-8")
    pipeline = backend.pipeline(threaded=threaded)
    entered, release, planned, deleted = (threading.Event() for _ in range(4))
    store = backend.documents if stage == "docstore" else backend.vectors
    original_add = type(store).add

    def blocked_add(instance, *args, **kwargs):
        result = original_add(instance, *args, **kwargs)
        entered.set()
        assert release.wait(10)
        return result

    monkeypatch.setattr(type(store), "add", blocked_add)
    deleter = coordinator(backend)
    original_plan = deleter._gather_plan
    plans = []

    def gather(*args):
        plan = original_plan(*args)
        plans.append(plan)
        planned.set()
        return plan

    monkeypatch.setattr(deleter, "_gather_plan", gather)
    writer_errors: list[BaseException] = []
    delete_errors: list[BaseException] = []
    events = []
    writer = threading.Thread(
        target=capture,
        args=(
            writer_errors,
            lambda: events.extend(pipeline.stream(backend.source, False)),
        ),
    )

    def delete():
        deleter.delete(support.rows(backend, "Source")[0].id, user_id="alice")
        deleted.set()

    deleting = threading.Thread(target=capture, args=(delete_errors, delete))
    try:
        writer.start()
        assert entered.wait(10)
        deleting.start()
        assert planned.wait(10)
        assert not deleted.is_set()
        assert not (
            plans[0].docstore_ids if stage == "docstore" else plans[0].vector_ids
        )
    finally:
        release.set()
        writer.join(10)
        if deleting.ident is not None:
            deleting.join(10)
        assert not writer.is_alive() and not deleting.is_alive()
    assert not delete_errors and deleted.is_set()
    assert len(plans) == 2
    assert plans[1].docstore_ids if stage == "docstore" else plans[1].vector_ids
    assert all(
        "Source removed during indexing" in str(error) for error in writer_errors
    )
    assert support.rows(backend, "Source") == []
    assert support.rows(backend, "Index") == []
    assert backend.vectors._collection.get()["ids"] == []
    assert backend.documents.query("protectedunique") == []
    assert not (backend.resources["FileStoragePath"] / plans[0].stored_path).exists()


def test_source_leases_are_reentrant_per_thread_and_distinct_sources_progress(backend):
    pipeline = backend.pipeline()
    backend.source.write_text("source", encoding="utf-8")
    first = pipeline.store_file(backend.source)
    backend.source = backend.source.with_name("other.txt")
    backend.source.write_text("other", encoding="utf-8")
    second = pipeline.store_file(backend.source)
    attempted, entered = threading.Event(), threading.Event()
    errors: list[BaseException] = []

    def enter_first():
        attempted.set()
        with pipeline.source_write_scope(first):
            entered.set()

    worker = threading.Thread(target=capture, args=(errors, enter_first))
    try:
        with pipeline.source_write_scope(first):
            with pipeline.source_write_scope(first):
                worker.start()
                assert attempted.wait(5)
                with pipeline.source_write_scope(second):
                    assert not entered.is_set()
    finally:
        if worker.ident is not None:
            worker.join(5)
            assert not worker.is_alive()
    assert entered.is_set() and not errors
    lease = source_lock(backend.engine, backend.resources["Source"], first)
    lock_path = Path(lease.lock_file)
    identity = lock_path.stat().st_ino
    with lease:
        assert lock_path.stat().st_ino == identity
    assert lock_path.stat().st_ino == identity


@pytest.mark.parametrize(
    "error",
    [RuntimeError("write failed"), CancelledError("cancel"), KeyboardInterrupt()],
)
def test_failed_write_releases_lease_and_preserves_primary_error(
    backend, monkeypatch, error
):
    pipeline = backend.pipeline()
    backend.source.write_text("failureunique", encoding="utf-8")
    file_id = pipeline.store_file(backend.source)
    doc = Document(text="failureunique", metadata={"file_id": file_id})

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(type(backend.documents), "add", fail)
    with pytest.raises(type(error)) as caught:
        pipeline.handle_chunks_docstore([doc], file_id)
    assert caught.value is error
    with source_lock(backend.engine, backend.resources["Source"], file_id).acquire(
        timeout=0
    ):
        assert support.rows(backend, "Index") == []
    coordinator(backend).delete(file_id, user_id="alice")
    assert support.rows(backend, "Source") == []


def test_wrong_owner_is_rejected_before_any_persistent_write(backend):
    pipeline = backend.pipeline("alice")
    backend.source.write_text("ownerunique", encoding="utf-8")
    file_id = pipeline.store_file(backend.source)
    stranger = backend.pipeline("bob")
    with pytest.raises(RuntimeError, match="Source owner changed"):
        stranger.handle_chunks_docstore([Document(text="ownerunique")], file_id)
    assert support.rows(backend, "Index") == []
    assert backend.vectors._collection.get()["ids"] == []
    assert support.rows(backend, "Source")[0].user == "alice"


@pytest.mark.parametrize("fail_unlock", [False, True])
def test_windows_release_closes_owned_descriptor_without_removing_shared_lock_path(
    tmp_path, monkeypatch, fail_unlock
):
    # Real Windows process tests cover locking. This portable test also forces
    # unlock failure, which must still close only this lease's owned descriptor.
    path = tmp_path / "owned.lock"
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR)
    context = SimpleNamespace(lock_file_fd=descriptor)
    lease = cast(source_writes._SourceFileLock, SimpleNamespace(_context=context))
    calls = []
    failure = OSError("owned unlock failure")

    def unlock(fd, operation, length):
        calls.append((fd, operation, length))
        if fail_unlock:
            raise failure

    monkeypatch.setitem(
        sys.modules, "msvcrt", SimpleNamespace(locking=unlock, LK_UNLCK=0)
    )
    monkeypatch.setattr(source_writes, "os", SimpleNamespace(name="nt", close=os.close))
    try:
        if fail_unlock:
            with pytest.raises(OSError) as caught:
                source_writes._SourceFileLock._release(lease)
            assert caught.value is failure
        else:
            source_writes._SourceFileLock._release(lease)
        assert calls == [(descriptor, 0, 1)]
        assert context.lock_file_fd is None
        with pytest.raises(OSError):
            os.fstat(descriptor)
        assert path.exists()
    finally:
        if context.lock_file_fd is not None:
            os.close(context.lock_file_fd)
