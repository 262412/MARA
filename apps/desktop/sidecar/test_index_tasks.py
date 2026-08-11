from __future__ import annotations

import errno
import json
import sqlite3
import tempfile
import threading
import unittest
from pathlib import Path

from .index_tasks import (
    IndexTaskConflictError,
    IndexTaskManager,
    _failure_from_exception,
    _missing_module_name,
)
from .indexing_readiness import DesktopIndexingPreflightError


class StubIndexService:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], bool]] = []
        self.release = threading.Event()
        self.block = False
        self.fail_once = {"broken.pdf"}

    def index_files(self, paths: list[str], *, reindex: bool = False) -> dict:
        self.calls.append((paths, reindex))
        if self.block:
            self.release.wait(timeout=5)
        name = Path(paths[0]).name
        if name in self.fail_once:
            self.fail_once.remove(name)
            return {
                "successes": [],
                "failures": [
                    {
                        "name": name,
                        "code": "index_failed",
                        "message": "MARA could not index this file.",
                        "retryable": True,
                    }
                ],
            }
        return {"successes": [{"name": name}], "failures": []}


def wait_for_terminal(manager: IndexTaskManager, task_id: str) -> dict:
    snapshot = manager.get_task(task_id)
    while snapshot["status"] in {"queued", "running"}:
        snapshot = manager.wait_for_change(
            task_id,
            snapshot["version"],
            timeout=2,
        )
    return snapshot


class IndexTaskManagerTest(unittest.TestCase):
    def test_preflight_failure_never_creates_or_schedules_a_task(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = Path(temporary_directory) / "index-tasks.json"
            service = StubIndexService()

            def reject(_paths: list[str]) -> None:
                raise DesktopIndexingPreflightError(
                    "embedding_not_configured",
                    "Configure an embedding model before indexing files.",
                    retryable=False,
                    status_code=409,
                )

            manager = IndexTaskManager(
                service,
                journal_path=journal,
                validator=reject,
            )
            try:
                with self.assertRaises(DesktopIndexingPreflightError):
                    manager.create_task(
                        ["/private/source/paper.txt"],
                        reindex=False,
                        idempotency_key="no-model",
                    )

                self.assertIsNone(manager.get_latest_task())
                self.assertFalse(journal.exists())
                self.assertEqual(service.calls, [])
            finally:
                manager.close()

    def test_runtime_failures_use_stable_retry_semantics(self) -> None:
        class StatusError(RuntimeError):
            def __init__(self, status_code: int) -> None:
                super().__init__(f"provider failed with {status_code} at /private")
                self.status_code = status_code

        cases = [
            (
                ModuleNotFoundError(name="google.generativeai"),
                "embedding_dependency_missing",
                False,
            ),
            (StatusError(401), "embedding_not_configured", False),
            (StatusError(403), "embedding_not_configured", False),
            (StatusError(503), "embedding_unavailable", True),
            (
                ConnectionError("network to /private failed"),
                "embedding_unavailable",
                True,
            ),
            (
                OSError(errno.ENOSPC, "full", "/private/vector.lance"),
                "index_storage_full",
                True,
            ),
            (
                sqlite3.OperationalError("database is locked at /private/mara.db"),
                "index_database_locked",
                True,
            ),
            (
                PermissionError(13, "denied", "/private/source/paper.txt"),
                "source_permission_denied",
                False,
            ),
            (RuntimeError("unknown failure at /private"), "index_failed", True),
        ]

        for error, expected_code, retryable in cases:
            with self.subTest(error=type(error).__name__, code=expected_code):
                failure = _failure_from_exception("paper.txt", error)
                self.assertEqual(failure["code"], expected_code)
                self.assertEqual(failure["retryable"], retryable)
                self.assertNotIn("/private", json.dumps(failure))

    def test_missing_module_diagnostic_is_narrow_and_path_free(self) -> None:
        missing = ModuleNotFoundError(name="lancedb.fts")
        unsafe = ModuleNotFoundError(name="/private/source/module.py")

        self.assertEqual(_missing_module_name(missing), "lancedb.fts")
        self.assertEqual(_missing_module_name(unsafe), "unknown")
        self.assertEqual(_missing_module_name(RuntimeError("failed")), "none")

    def test_runs_in_background_deduplicates_and_retries_only_failed_sources(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            service = StubIndexService()
            manager = IndexTaskManager(
                service,
                journal_path=Path(temporary_directory) / "index-tasks.json",
            )
            try:
                created = manager.create_task(
                    ["/private/paper.pdf", "/private/broken.pdf"],
                    reindex=False,
                    idempotency_key="import-1",
                )
                duplicate = manager.create_task(
                    ["/ignored/duplicate.pdf"],
                    reindex=True,
                    idempotency_key="import-1",
                )

                self.assertEqual(duplicate["task_id"], created["task_id"])
                partial = wait_for_terminal(manager, created["task_id"])
                self.assertEqual(partial["status"], "partial")
                self.assertEqual(partial["completed_files"], 2)
                self.assertEqual(partial["success_count"], 1)
                self.assertEqual(partial["failure_count"], 1)
                self.assertNotIn("/private", json.dumps(partial))

                retried = manager.retry_task(
                    created["task_id"],
                    idempotency_key="retry-1",
                )
                success = wait_for_terminal(manager, retried["task_id"])
                self.assertEqual(success["status"], "success")
                self.assertEqual(service.calls[-1][0], ["/private/broken.pdf"])
                self.assertTrue(service.calls[-1][1])
                with self.assertRaises(IndexTaskConflictError):
                    manager.retry_task(
                        success["task_id"],
                        idempotency_key="retry-success",
                    )
            finally:
                manager.close()

    def test_cancellation_is_recorded_and_completed_tasks_survive_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = Path(temporary_directory) / "index-tasks.json"
            service = StubIndexService()
            service.block = True
            manager = IndexTaskManager(service, journal_path=journal)
            created = manager.create_task(
                ["/private/slow.pdf", "/private/pending.pdf"],
                reindex=False,
                idempotency_key="cancel-1",
            )
            running = manager.wait_for_change(
                created["task_id"],
                created["version"],
                timeout=2,
            )
            self.assertEqual(running["status"], "running")
            cancelling = manager.cancel_task(created["task_id"])
            self.assertEqual(cancelling["stage"], "cancelling")
            service.release.set()
            cancelled = wait_for_terminal(manager, created["task_id"])
            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(cancelled["completed_files"], 1)
            self.assertEqual(
                manager.cancel_task(created["task_id"])["status"],
                "cancelled",
            )
            manager.close()

            restored = IndexTaskManager(StubIndexService(), journal_path=journal)
            try:
                self.assertEqual(
                    restored.get_task(created["task_id"])["status"],
                    "cancelled",
                )
            finally:
                restored.close()

    def test_restart_marks_an_unfinished_journal_task_retryable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = Path(temporary_directory) / "index-tasks.json"
            journal.write_text(
                json.dumps(
                    {
                        "journal_version": 1,
                        "tasks": [
                            {
                                "task_id": "task-interrupted",
                                "idempotency_key": "import-interrupted",
                                "reindex": False,
                                "sources": [
                                    {
                                        "path": "/private/paper.pdf",
                                        "name": "paper.pdf",
                                        "status": "pending",
                                        "error": None,
                                    }
                                ],
                                "status": "running",
                                "stage": "indexing",
                                "created_at": "2026-08-08T10:00:00Z",
                                "updated_at": "2026-08-08T10:00:01Z",
                                "version": 2,
                                "cancel_requested": False,
                                "error": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manager = IndexTaskManager(StubIndexService(), journal_path=journal)
            try:
                interrupted = manager.get_task("task-interrupted")
                latest = manager.get_latest_task()
                self.assertIsNotNone(latest)
                assert latest is not None
                self.assertEqual(latest["task_id"], "task-interrupted")
                self.assertEqual(interrupted["status"], "failed")
                self.assertEqual(interrupted["stage"], "interrupted")
                self.assertTrue(interrupted["retryable"])
                self.assertNotIn("/private", json.dumps(interrupted))
            finally:
                manager.close()


if __name__ == "__main__":
    unittest.main()
