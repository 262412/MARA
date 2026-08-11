from __future__ import annotations

import errno
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from sqlalchemy.exc import OperationalError as SqlAlchemyOperationalError

from .index_task_journal import IndexTaskPersistenceError, JsonIndexTaskJournal
from .index_tasks import IndexTaskManager
from .smoke_faults import FailOnceIndexService, FailOnceJournal


class SuccessfulIndexService:
    def index_files(self, paths: list[str], *, reindex: bool = False) -> dict:
        return {
            "successes": [{"name": Path(path).name} for path in paths],
            "failures": [],
        }


def wait_for_terminal(manager: IndexTaskManager, task_id: str) -> dict:
    snapshot = manager.get_task(task_id)
    while snapshot["status"] in {"queued", "running"}:
        snapshot = manager.wait_for_change(
            task_id,
            snapshot["version"],
            timeout=2,
        )
    return snapshot


class IndexTaskFaultTest(unittest.TestCase):
    def test_unwritable_journal_is_non_retryable_and_rolls_back_task(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = FailOnceJournal(
                JsonIndexTaskJournal(Path(temporary_directory) / "index-tasks.json"),
                PermissionError(13, "denied", "/private/state/index-tasks.tmp"),
            )
            manager = IndexTaskManager(SuccessfulIndexService(), journal=journal)
            try:
                with self.assertRaises(IndexTaskPersistenceError) as raised:
                    manager.create_task(
                        ["/private/source/paper.txt"],
                        reindex=False,
                        idempotency_key="unwritable-state-1",
                    )

                self.assertEqual(
                    raised.exception.code,
                    "index_runtime_storage_unwritable",
                )
                self.assertFalse(raised.exception.retryable)
                self.assertNotIn("/private", str(raised.exception))
                self.assertIsNone(manager.get_latest_task())
            finally:
                manager.close()

    def test_disk_full_rolls_back_unscheduled_task_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = FailOnceJournal(
                JsonIndexTaskJournal(Path(temporary_directory) / "index-tasks.json"),
                OSError(
                    errno.ENOSPC,
                    "No space left on device",
                    "/private/source/index-tasks.tmp",
                ),
            )
            manager = IndexTaskManager(
                SuccessfulIndexService(),
                journal=journal,
            )
            try:
                with self.assertRaises(IndexTaskPersistenceError) as raised:
                    manager.create_task(
                        ["/private/source/paper.txt"],
                        reindex=False,
                        idempotency_key="disk-full-1",
                    )

                self.assertEqual(raised.exception.code, "index_storage_full")
                self.assertNotIn("/private", str(raised.exception))
                self.assertIsNone(manager.get_latest_task())

                recovered = manager.create_task(
                    ["/private/source/paper.txt"],
                    reindex=False,
                    idempotency_key="disk-full-2",
                )
                terminal = wait_for_terminal(manager, recovered["task_id"])
                self.assertEqual(terminal["status"], "success")
            finally:
                manager.close()

    def test_database_lock_is_path_free_retryable_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = FailOnceIndexService(
                SuccessfulIndexService(),
                sqlite3.OperationalError(
                    "database is locked at /private/source/mara.db"
                ),
            )
            manager = IndexTaskManager(
                service,
                journal_path=Path(temporary_directory) / "index-tasks.json",
            )
            try:
                with self.assertLogs("mara.desktop.index_tasks", level="ERROR") as logs:
                    created = manager.create_task(
                        ["/private/source/paper.txt"],
                        reindex=False,
                        idempotency_key="database-lock-1",
                    )
                    failed = wait_for_terminal(manager, created["task_id"])

                self.assertEqual(failed["status"], "failed")
                self.assertEqual(failed["error"]["code"], "index_database_locked")
                self.assertEqual(
                    failed["failures"][0]["code"],
                    "index_database_locked",
                )
                self.assertTrue(failed["retryable"])
                self.assertNotIn("/private", json.dumps(failed))
                self.assertNotIn("/private", "\n".join(logs.output))
                self.assertNotIn("database is locked", "\n".join(logs.output))

                retried = manager.retry_task(
                    created["task_id"],
                    idempotency_key="database-lock-retry-1",
                )
                terminal = wait_for_terminal(manager, retried["task_id"])
                self.assertEqual(terminal["status"], "success")
                self.assertEqual(terminal["total_files"], 1)
            finally:
                manager.close()

    def test_sqlalchemy_database_lock_uses_the_same_stable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = FailOnceIndexService(
                SuccessfulIndexService(),
                SqlAlchemyOperationalError(
                    "UPDATE source",
                    {},
                    sqlite3.OperationalError("database is locked"),
                ),
            )
            manager = IndexTaskManager(
                service,
                journal_path=Path(temporary_directory) / "index-tasks.json",
            )
            try:
                created = manager.create_task(
                    ["/private/source/paper.txt"],
                    reindex=False,
                    idempotency_key="sqlalchemy-database-lock-1",
                )
                failed = wait_for_terminal(manager, created["task_id"])

                self.assertEqual(
                    failed["error"]["code"],
                    "index_database_locked",
                )
                self.assertNotIn("UPDATE source", json.dumps(failed))
                self.assertNotIn("/private", json.dumps(failed))
            finally:
                manager.close()

    def test_index_storage_enospc_is_retryable_and_path_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = FailOnceIndexService(
                SuccessfulIndexService(),
                OSError(
                    errno.ENOSPC,
                    "No space left on device",
                    "/private/source/vector.lance",
                ),
            )
            manager = IndexTaskManager(
                service,
                journal_path=Path(temporary_directory) / "index-tasks.json",
            )
            try:
                created = manager.create_task(
                    ["/private/source/paper.txt"],
                    reindex=False,
                    idempotency_key="index-storage-full-1",
                )
                failed = wait_for_terminal(manager, created["task_id"])

                self.assertEqual(failed["error"]["code"], "index_storage_full")
                self.assertTrue(failed["retryable"])
                self.assertNotIn("/private", json.dumps(failed))
            finally:
                manager.close()


if __name__ == "__main__":
    unittest.main()
