"""Source-incarnation leases shared by persistent writes and deletion.

Lock order: source lease, optional content-path lease, short SQL session. Never
wait for an indexing worker or yield an event while holding a source lease.
"""

from __future__ import annotations

import json
import os
import sys
from contextlib import AbstractContextManager, contextmanager
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Iterator

from filelock import FileLock
from sqlalchemy import select
from sqlalchemy.orm import Session
from theflow.settings import settings

from .element_index import set_index_row_owner
from .storage_lifetime import _ensure_real_directory, _ensure_root, _require_regular


class _SourceFileLock(FileLock):
    def _release(self) -> None:
        if sys.platform != "win32":
            return super()._release()
        # filelock 3.19.1 otherwise unlinks on Windows. Keep the inode for waiters.
        import msvcrt

        descriptor = self._context.lock_file_fd
        self._context.lock_file_fd = None
        assert descriptor is not None
        try:
            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(descriptor)


def source_lock(engine: Any, source_table: Any, file_id: str) -> FileLock:
    """Use trusted DB configuration, table and UUID, never a client path/name."""
    url = engine.url
    database = url.database
    root = Path(settings.KH_APP_DATA_DIR)
    if url.get_backend_name() == "sqlite" and database not in (None, "", ":memory:"):
        database = os.path.normcase(str(Path(database).resolve()))
        root = Path(database).parent
    _ensure_root(root)
    lock_root = root / ".mara-source-locks"
    lock_root.mkdir(exist_ok=True)
    _ensure_real_directory(lock_root)
    namespace = [
        url.get_backend_name(),
        url.host,
        url.port,
        database,
        source_table.__table__.fullname,
        str(file_id),
    ]
    key = sha256(json.dumps(namespace, separators=(",", ":")).encode()).hexdigest()
    path = lock_root / (key + ".lock")
    if path.exists() or path.is_symlink():
        _require_regular(path, "source lock")
    # Reentrant within one thread, but never across threads. File locking is the
    # cross-object/process authority; the singleton only supports nested finish.
    return _SourceFileLock(str(path), is_singleton=True, thread_local=True)


@contextmanager
def source_write(
    engine: Any,
    source_table: Any,
    file_id: str,
    user_id: Any,
    *,
    session_factory: Callable[[], Session],
) -> Iterator[None]:
    """Validate the unchanged Source incarnation and owner under the write lease."""
    with source_lock(engine, source_table, file_id):
        with session_factory() as session:
            source = session.execute(
                select(source_table).where(source_table.id == file_id)
            ).scalar_one_or_none()
            if source is None:
                raise RuntimeError(f"Source removed during indexing: {file_id}")
            if str(source.user or "") != str(user_id or ""):
                raise RuntimeError(f"Source owner changed during indexing: {file_id}")
        yield


def persist_docstore_batches(
    batches_and_rows: tuple[list[list[Any]], list[Any]],
    *,
    add: Callable[[list[Any]], Any],
    user_id: Any,
    session_factory: Callable[[], Session],
) -> None:
    """Called under the source lease so deletion cannot miss new targets."""
    batches, rows = batches_and_rows
    for batch in batches:
        add(batch)
    set_index_row_owner(rows, user_id)
    with session_factory() as session:
        session.add_all(rows)
        session.commit()


def persist_vector_batch(
    chunks: list[Any],
    file_id: str,
    artifact_generation: Any,
    *,
    vector_indexing: Any,
    index_table: Any,
    user_id: Any,
    has_vector_store: bool,
    session_factory: Callable[[], Session],
    write_scope: Callable[[], AbstractContextManager],
) -> None:
    """Keep the actual vector write, artifacts and SQL registration indivisible
    relative to source deletion, while embedding remains outside the lease.
    """

    @contextmanager
    def register_write():
        with write_scope():
            yield
            vector_indexing.write_chunk_to_file(chunks, file_id, artifact_generation)
            if has_vector_store:
                nodes = [
                    index_table(
                        source_id=file_id,
                        target_id=chunk.doc_id,
                        relation_type="vector",
                    )
                    for chunk in chunks
                ]
                set_index_row_owner(nodes, user_id)
                with session_factory() as session:
                    session.add_all(nodes)
                    session.commit()

    vector_indexing.add_to_vectorstore(chunks, write_scope=register_write)
