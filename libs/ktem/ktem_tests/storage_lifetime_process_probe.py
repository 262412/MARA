"""Owned child for cross-process lease barriers, using real SQL and file locks."""

import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path

from filelock import FileLock
from ktem.index.file.deletion import DeletionCoordinator
from ktem.index.file.storage_lifetime import StorageLifetime
from sqlalchemy import create_engine
from sqlalchemy.ext.automap import automap_base
from sqlalchemy.orm import Session


def wait_for(path):
    deadline = time.monotonic() + 30
    while not path.exists():
        if time.monotonic() > deadline:
            raise TimeoutError(f"Owned test barrier not released: {path}")
        time.sleep(0.02)


def main():
    (
        db_path,
        raw_root,
        raw_barriers,
        operation,
        file_id,
        user_id,
        stored_path,
    ) = sys.argv[1:]
    root, barriers = Path(raw_root), Path(raw_barriers)

    class SignalledLock:
        def __init__(self, path):
            self.lock = FileLock(path)

        def __enter__(self):
            (barriers / "attempted").write_text(str(os.getpid()))
            self.lock.acquire(timeout=30)
            (barriers / "entered").write_text(str(os.getpid()))

        def __exit__(self, *_args):
            self.lock.release()

    lifetime = StorageLifetime(root, lock_factory=SignalledLock)

    class PausingLifetime:
        @contextmanager
        def hold(self, path):
            with lifetime.hold(path) as lease:
                wait_for(barriers / "release")
                yield lease

    engine = create_engine(f"sqlite:///{db_path}")
    base = automap_base()
    base.prepare(autoload_with=engine)
    source = base.classes.source
    try:
        if operation == "delete":
            DeletionCoordinator(
                engine=engine,
                source_table=source,
                index_table=base.classes.index_row,
                vector_store=None,
                doc_store=None,
                file_storage_path=root,
                storage_lifetime=PausingLifetime(),
            ).delete(file_id, user_id=user_id)
        else:
            with PausingLifetime().hold(stored_path) as lease:
                if operation == "publish":
                    lease.publish_from(barriers / "upload.bin")
                    with Session(engine) as session:
                        session.add(
                            source(
                                id=file_id, name=file_id, path=stored_path, user=user_id
                            )
                        )
                        session.commit()
        (barriers / "done").write_text("committed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
