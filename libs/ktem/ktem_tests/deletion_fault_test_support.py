"""Fault injection around real SQL, artifact trees, and storage leases."""

import os
from contextlib import contextmanager

from ktem.index.file.artifact_cleanup import FileArtifactCleaner
from ktem.index.file.storage_lifetime import StorageLifetime
from sqlalchemy.orm import Session

from .test_deletion_coordinator import _coordinator


class FaultProbe:
    def __init__(self, database, tmp_path, failure):
        self.database = database
        self.failure = failure
        self.trace = []
        self.vector = self.store("vector", {"vector-1"})
        self.docstore = self.store("docstore", {"document-1", "element-1", "graph-1"})
        self.cleaner = FileArtifactCleaner(
            chunks_root=tmp_path / "chunks",
            markdown_root=tmp_path / "markdown",
            download_root=tmp_path / "downloads",
        )
        self.artifacts = self.cleaner._targets("file-1")
        for target in self.artifacts:
            target.mkdir(parents=True)
            (target / "artifact").write_bytes(b"owned artifact")
        self.lifetime = StorageLifetime(
            database[3],
            mover=self.move,
            unlinker=self.unlink,
            directory_syncer=self.sync,
        )
        self.syncs = 0

    def step(self, stage):
        self.trace.append(stage)
        if self.failure == stage:
            raise OSError(f"injected {stage}")

    def store(self, stage, values):
        probe = self

        class Store:
            def __init__(self):
                self.values = set(values)

            def delete(self, ids, **kwargs):
                assert kwargs == (
                    {"refresh_indices": False} if stage == "docstore" else {}
                )
                self.values.discard(ids[0])
                probe.step(stage)
                self.values.difference_update(ids)

            def create_fts_index(self, *args, **kwargs):
                assert args == ("text",)
                assert kwargs == {"tokenizer_name": "en_stem", "replace": True}
                probe.step("fts")

        return Store()

    def clean(self, file_id):
        self.trace.append("artifacts")
        if self.failure == "artifacts":
            from ktem.index.file.artifact_cleanup import _remove_tree

            _remove_tree(self.artifacts[0])
            raise OSError("injected artifacts")
        self.cleaner.clean(file_id)

    @contextmanager
    def hold(self, path):
        self.step("lease")
        with self.lifetime.hold(path) as lease:
            yield lease

    def move(self, source, target):
        self.step("restore" if ".quarantine-" in source.name else "quarantine")
        os.replace(source, target)

    def sync(self, _directory):
        self.syncs += 1
        if self.failure == "sync" and self.syncs == 1:
            self.step("sync")

    def unlink(self, path):
        self.step("purge")
        path.unlink()

    def session(self):
        probe = self

        class FaultSession(Session):
            deleting = False

            def execute(self, statement, *args, **kwargs):
                if getattr(statement, "is_delete", False):
                    self.deleting = True
                    probe.step(
                        "sql-source"
                        if statement.table.name == "source"
                        else "sql-index"
                    )
                return super().execute(statement, *args, **kwargs)

            def flush(self, *args, **kwargs):
                if self.deleting:
                    probe.step("flush")
                return super().flush(*args, **kwargs)

            def scalar(self, *args, **kwargs):
                probe.step("references")
                return super().scalar(*args, **kwargs)

            def commit(self):
                probe.trace.append("commit")
                if probe.failure in {"commit", "restore"}:
                    raise OSError("injected commit")
                return super().commit()

            def rollback(self):
                probe.trace.append("rollback")
                return super().rollback()

        return FaultSession(self.database[0])

    def coordinator(self):
        return _coordinator(
            self.database,
            vector_store=self.vector,
            doc_store=self.docstore,
            artifact_cleaner=self.clean,
            storage_lifetime=self,
            session_factory=self.session,
        )
