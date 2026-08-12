from __future__ import annotations

import json
import tempfile
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .query_task_journal import QueryTaskPersistenceError
from .query_tasks import QueryTaskManager
from .test_query_tasks import StubQueryService, wait_for_terminal


class StageJournal:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None
        self.fail_when: Callable[[dict[str, Any]], bool] = lambda _task: False

    def load(self) -> dict[str, Any] | None:
        return self.payload

    def probe(self) -> None:
        return None

    def save(self, payload: dict[str, Any]) -> None:
        copied = json.loads(json.dumps(payload))
        if any(self.fail_when(task) for task in copied["tasks"]):
            raise _locked_error()
        self.payload = copied


class ToggleJournal:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None
        self.writable = True
        self.fail_on_partial = True

    def load(self) -> dict[str, Any] | None:
        return self.payload

    def probe(self) -> None:
        if not self.writable:
            raise _permission_error("write_temp")

    def save(self, payload: dict[str, Any]) -> None:
        partial = any(
            task.get("answer") == "Partial answer" and task.get("status") == "running"
            for task in payload["tasks"]
        )
        if (self.fail_on_partial and partial) or not self.writable:
            raise _permission_error("flush")
        self.payload = json.loads(json.dumps(payload))


class FinalFailureJournal:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None
        self.fail_final = True

    def load(self) -> dict[str, Any] | None:
        return self.payload

    def probe(self) -> None:
        return None

    def save(self, payload: dict[str, Any]) -> None:
        copied = json.loads(json.dumps(payload))
        if self.fail_final and any(
            task.get("status") == "success" for task in copied["tasks"]
        ):
            raise QueryTaskPersistenceError(
                "query_persistence_failed",
                "MARA could not save answer state.",
                retryable=False,
                operation="atomic_replace",
            )
        self.payload = copied


class QueryTaskStagePersistenceTest(unittest.TestCase):
    def test_running_fault_is_typed_before_model_work(self) -> None:
        service = StubQueryService()
        journal = StageJournal()
        journal.fail_when = lambda task: (
            task["status"] == "running" and task["stage"] == "preparing"
        )
        manager = QueryTaskManager(service, journal=journal)
        try:
            created = _create_task(manager, "running-fault")
            failed = wait_for_terminal(manager, created["task_id"])
            self.assertEqual(failed["stage"], "storage_error")
            self.assertEqual(failed["error"]["code"], "query_state_locked")
            self.assertEqual(service.calls, [])
        finally:
            manager.close()

    def test_cancel_fault_keeps_the_partial_answer(self) -> None:
        service = StubQueryService()
        service.block_after_partial = True
        journal = StageJournal()
        manager = QueryTaskManager(service, journal=journal)
        try:
            created = _create_task(manager, "cancel-fault")
            self.assertTrue(service.partial_emitted.wait(timeout=2))
            _wait_for_partial(manager, created["task_id"])
            journal.fail_when = lambda task: bool(task["cancel_requested"])
            failed = manager.cancel_task(created["task_id"])
            self.assertEqual(failed["stage"], "storage_error")
            self.assertEqual(failed["answer"], "Partial answer")
            self.assertEqual(failed["error"]["code"], "query_state_locked")
        finally:
            manager.close()

    def test_retry_fault_does_not_create_or_run_a_new_task(self) -> None:
        service = StubQueryService()
        service.fail_after_partial = True
        journal = StageJournal()
        manager = QueryTaskManager(service, journal=journal)
        try:
            created = _create_task(manager, "retry-original")
            wait_for_terminal(manager, created["task_id"])
            journal.fail_when = lambda task: bool(task["retry_of_task_id"])
            with self.assertRaises(QueryTaskPersistenceError):
                manager.retry_task(
                    created["task_id"],
                    idempotency_key="retry-fault",
                )
            latest = manager.get_latest_task()
            self.assertIsNotNone(latest)
            assert latest is not None
            self.assertEqual(len(service.calls), 1)
            self.assertEqual(latest["task_id"], created["task_id"])
        finally:
            manager.close()


class QueryTaskStorageRecoveryTest(unittest.TestCase):
    def test_partial_fault_blocks_retry_until_storage_recovers(self) -> None:
        service = StubQueryService()
        service.delay_before_partial = 0.03
        service.block_after_partial = True
        journal = ToggleJournal()
        manager = QueryTaskManager(
            service,
            journal=journal,
            journal_flush_interval=0.01,
        )
        try:
            with self.assertLogs("mara.desktop.query_tasks", level="ERROR") as logs:
                created = _create_task(manager, "persistence-original")
                failed = wait_for_terminal(manager, created["task_id"])
            self.assertEqual(failed["stage"], "storage_error")
            self.assertEqual(failed["answer"], "Partial answer")
            self.assertEqual(failed["error"]["code"], "query_state_permission_denied")
            self.assertIn("operation=flush", "\n".join(logs.output))
            self.assertNotIn("Question", "\n".join(logs.output))

            journal.writable = False
            validation_count = service.validate_calls
            with self.assertRaises(QueryTaskPersistenceError):
                manager.retry_task(
                    created["task_id"],
                    idempotency_key="persistence-retry-blocked",
                )
            self.assertEqual(service.validate_calls, validation_count)
            self.assertEqual(len(service.calls), 1)

            journal.writable = True
            journal.fail_on_partial = False
            service.block_after_partial = False
            retried = manager.retry_task(
                created["task_id"],
                idempotency_key="persistence-retry-success",
            )
            completed = wait_for_terminal(manager, retried["task_id"])
            self.assertEqual(completed["status"], "success")
            self.assertEqual(len(service.calls), 2)
            self.assertEqual(service.turn_ids[0], service.turn_ids[1])
        finally:
            manager.close()

    def test_restart_recovers_session_commit_without_another_model_call(self) -> None:
        service = StubQueryService()
        journal = FinalFailureJournal()
        manager = QueryTaskManager(service, journal=journal)
        created = _create_task(manager, "session-commit-original")
        failed = wait_for_terminal(manager, created["task_id"])
        self.assertEqual(failed["stage"], "storage_error")
        self.assertEqual(len(service.calls), 1)
        manager.close()

        journal.fail_final = False
        restored_manager = QueryTaskManager(service, journal=journal)
        try:
            restored = restored_manager.get_task(created["task_id"])
            self.assertEqual(restored["status"], "success")
            self.assertEqual(restored["answer"], "Final answer")
            self.assertEqual(len(service.calls), 1)
        finally:
            restored_manager.close()


class QueryTaskJournalMigrationTest(unittest.TestCase):
    def test_v1_migration_is_versioned_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = Path(temporary_directory) / "query-tasks.json"
            record = _task_record("query-interrupted", answer="Partial answer")
            record.pop("turn_id")
            journal.write_text(
                json.dumps({"journal_version": 1, "tasks": [record]}),
                encoding="utf-8",
            )
            manager = QueryTaskManager(StubQueryService(), journal_path=journal)
            try:
                restored = manager.get_task("query-interrupted")
            finally:
                manager.close()
            migrated = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(migrated["journal_version"], 2)
            self.assertEqual(migrated["tasks"][0]["turn_id"], "query-interrupted")

            second_manager = QueryTaskManager(StubQueryService(), journal_path=journal)
            try:
                self.assertEqual(
                    second_manager.get_task("query-interrupted")["version"],
                    restored["version"],
                )
            finally:
                second_manager.close()

    def test_restart_reports_only_the_last_safely_saved_partial(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = Path(temporary_directory) / "query-tasks.json"
            record = _task_record(
                "query-before-partial-save",
                stage="retrieving",
                answer="",
            )
            journal.write_text(
                json.dumps({"journal_version": 2, "tasks": [record]}),
                encoding="utf-8",
            )
            manager = QueryTaskManager(StubQueryService(), journal_path=journal)
            try:
                restored = manager.get_task("query-before-partial-save")
                self.assertEqual(restored["status"], "failed")
                self.assertEqual(restored["stage"], "interrupted")
                self.assertEqual(restored["answer"], "")
                self.assertIn("last saved partial", restored["error"]["message"])
            finally:
                manager.close()

    def test_corrupt_journal_blocks_readiness_without_deleting_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "query-tasks.json"
            path.write_text("{broken", encoding="utf-8")
            manager = QueryTaskManager(StubQueryService(), journal_path=path)
            try:
                readiness = manager.persistence_readiness()
                self.assertFalse(readiness["query_persistence_ready"])
                self.assertEqual(
                    readiness["query_persistence_issue_code"],
                    "query_state_corrupt",
                )
                self.assertEqual(path.read_text(encoding="utf-8"), "{broken")
            finally:
                manager.close()


def _create_task(manager: QueryTaskManager, idempotency_key: str) -> dict[str, Any]:
    return manager.create_task(
        "session-1",
        "Question",
        ["file-1"],
        idempotency_key=idempotency_key,
    )


def _wait_for_partial(manager: QueryTaskManager, task_id: str) -> None:
    deadline = time.monotonic() + 2
    while (
        manager.get_task(task_id)["answer"] != "Partial answer"
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)


def _locked_error() -> QueryTaskPersistenceError:
    return QueryTaskPersistenceError(
        "query_state_locked",
        "Answer state is locked. Close any extra MARA instance, then retry.",
        retryable=True,
        operation="atomic_replace",
        error_type="PermissionError",
        error_number=13,
        winerror=32,
        retry_count=4,
    )


def _permission_error(operation: str) -> QueryTaskPersistenceError:
    return QueryTaskPersistenceError(
        "query_state_permission_denied",
        "MARA cannot write answer state until data permissions are fixed.",
        retryable=True,
        operation=operation,
    )


def _task_record(
    task_id: str,
    *,
    stage: str = "generating",
    answer: str,
) -> dict[str, Any]:
    return {
        "task_id": task_id,
        "turn_id": task_id,
        "idempotency_key": task_id,
        "retry_of_task_id": None,
        "conversation_id": "session-1",
        "prompt": "Question",
        "selected_file_ids": ["file-1"],
        "status": "running",
        "stage": stage,
        "answer": answer,
        "citations": [],
        "created_at": "2026-08-08T10:00:00Z",
        "updated_at": "2026-08-08T10:00:01Z",
        "version": 2,
        "cancel_requested": False,
        "error": None,
    }
