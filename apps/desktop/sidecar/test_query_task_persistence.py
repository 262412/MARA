from __future__ import annotations

import json
import os
import tempfile
import threading
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import patch

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


class FailOnceCheckpointJournal:
    def __init__(self) -> None:
        self.payload: dict[str, Any] | None = None
        self.partial_failures = 0

    def load(self) -> dict[str, Any] | None:
        return self.payload

    def probe(self) -> None:
        return None

    def save(self, payload: dict[str, Any]) -> None:
        copied = json.loads(json.dumps(payload))
        has_partial = any(
            task.get("status") == "running" and bool(task.get("answer"))
            for task in copied["tasks"]
        )
        if has_partial and self.partial_failures == 0:
            self.partial_failures += 1
            raise _permission_error("flush")
        self.payload = copied


class PermissionRevocationService(StubQueryService):
    def __init__(self) -> None:
        super().__init__()
        self.first_partial = threading.Event()
        self.release_second_partial = threading.Event()

    def stream_query(
        self,
        conversation_id: str,
        prompt: str,
        selected_file_ids: list[str],
        cancel_event: threading.Event | None = None,
        *,
        turn_id: str = "",
    ):
        self.calls.append((conversation_id, prompt, selected_file_ids))
        self.turn_ids.append(turn_id)
        time.sleep(0.02)
        yield {
            "stage": "generating",
            "answer": "Saved partial",
            "final": False,
            "citations": [],
        }
        self.first_partial.set()
        self.release_second_partial.wait(timeout=3)
        if cancel_event is not None and cancel_event.is_set():
            return
        time.sleep(0.02)
        yield {
            "stage": "generating",
            "answer": "Unsaved partial with private sentinel",
            "final": False,
            "citations": [],
        }


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
    def test_two_access_denied_replaces_recover_inside_one_model_turn(self) -> None:
        service = StubQueryService()
        service.delay_before_partial = 0.03
        real_replace = os.replace
        transient_failures = 0

        def fail_two_partial_replaces(source: Path, destination: Path) -> None:
            nonlocal transient_failures
            payload = json.loads(Path(source).read_text(encoding="utf-8"))
            contains_partial = any(
                task.get("status") == "running" and bool(task.get("answer"))
                for task in payload.get("tasks", [])
            )
            if contains_partial and transient_failures < 2:
                transient_failures += 1
                error = PermissionError(13, "private path sentinel")
                error.winerror = 5  # type: ignore[attr-defined]
                raise error
            real_replace(source, destination)

        with tempfile.TemporaryDirectory() as temporary_directory:
            journal_path = Path(temporary_directory) / "query-tasks.json"
            manager = QueryTaskManager(
                service,
                journal_path=journal_path,
                journal_flush_interval=0.0,
            )
            try:
                with patch(
                    "sidecar.query_task_journal.os.replace",
                    side_effect=fail_two_partial_replaces,
                ):
                    created = _create_task(manager, "replace-recovery")
                    completed = wait_for_terminal(manager, created["task_id"])

                self.assertEqual(completed["status"], "success")
                self.assertTrue(completed["answer_saved"])
                self.assertEqual(transient_failures, 2)
                self.assertEqual(len(service.calls), 1)
                self.assertEqual(len(service.turn_ids), 1)
                persisted = json.loads(journal_path.read_text(encoding="utf-8"))
                matching = [
                    task
                    for task in persisted["tasks"]
                    if task["task_id"] == created["task_id"]
                ]
                self.assertEqual(len(matching), 1)
                self.assertEqual(matching[0]["status"], "success")
            finally:
                manager.close()

    def test_one_transient_checkpoint_failure_recovers_without_second_model_call(
        self,
    ) -> None:
        service = StubQueryService()
        service.delay_before_partial = 0.03
        journal = FailOnceCheckpointJournal()
        manager = QueryTaskManager(
            service,
            journal=journal,
            journal_flush_interval=0.01,
        )
        try:
            created = _create_task(manager, "transient-checkpoint")
            completed = wait_for_terminal(manager, created["task_id"])

            self.assertEqual(completed["status"], "success")
            self.assertTrue(completed["answer_saved"])
            self.assertEqual(journal.partial_failures, 1)
            self.assertEqual(len(service.calls), 1)
            assert journal.payload is not None
            matching = [
                task
                for task in journal.payload["tasks"]
                if task["task_id"] == created["task_id"]
            ]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["status"], "success")
        finally:
            manager.close()

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
            self.assertFalse(failed["answer_saved"])
            self.assertEqual(failed["error"]["code"], "query_state_permission_denied")
            self.assertEqual(failed["error"]["persistence"]["operation"], "flush")
            self.assertFalse(failed["error"]["persistence"]["smoke_mode"])
            self.assertRegex(
                failed["error"]["persistence"]["fingerprint"],
                r"^qpf-[0-9a-f]{16}$",
            )
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

    @unittest.skipIf(os.name == "nt", "POSIX permission revocation coverage")
    def test_unwritable_state_directory_blocks_before_model_validation(self) -> None:
        service = StubQueryService()
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_directory = Path(temporary_directory) / "state"
            state_directory.mkdir()
            journal_path = state_directory / "query-tasks.json"
            state_directory.chmod(0o500)
            manager = QueryTaskManager(service, journal_path=journal_path)
            try:
                with self.assertRaises(QueryTaskPersistenceError) as caught:
                    _create_task(manager, "unwritable-before-model")
                self.assertEqual(caught.exception.operation, "write_temp")
                self.assertEqual(service.validate_calls, 0)
                self.assertEqual(service.calls, [])
                self.assertFalse(journal_path.exists())
            finally:
                state_directory.chmod(0o700)
                manager.close()

    @unittest.skipIf(os.name == "nt", "POSIX permission revocation coverage")
    def test_linux_permission_revocation_preserves_last_saved_partial(self) -> None:
        service = PermissionRevocationService()
        with tempfile.TemporaryDirectory() as temporary_directory:
            state_directory = Path(temporary_directory) / "state"
            journal_path = state_directory / "query-tasks.json"
            manager = QueryTaskManager(
                service,
                journal_path=journal_path,
                journal_flush_interval=0.01,
            )
            try:
                created = _create_task(manager, "linux-permission-revocation")
                self.assertTrue(service.first_partial.wait(timeout=2))
                deadline = time.monotonic() + 2
                while time.monotonic() < deadline:
                    persisted = json.loads(journal_path.read_text(encoding="utf-8"))
                    saved = next(
                        task
                        for task in persisted["tasks"]
                        if task["task_id"] == created["task_id"]
                    )
                    if saved["answer"] == "Saved partial":
                        break
                    time.sleep(0.01)
                else:
                    self.fail("The first partial answer was not durably checkpointed")

                state_directory.chmod(0o500)
                service.release_second_partial.set()
                failed = wait_for_terminal(manager, created["task_id"])

                self.assertEqual(failed["stage"], "storage_error")
                self.assertEqual(
                    failed["answer"],
                    "Unsaved partial with private sentinel",
                )
                self.assertFalse(failed["answer_saved"])
                self.assertEqual(
                    failed["error"]["persistence"]["operation"],
                    "write_temp",
                )
                self.assertNotIn(
                    "private sentinel",
                    json.dumps(failed["error"]),
                )
                persisted = json.loads(journal_path.read_text(encoding="utf-8"))
                saved = next(
                    task
                    for task in persisted["tasks"]
                    if task["task_id"] == created["task_id"]
                )
                self.assertEqual(saved["answer"], "Saved partial")
            finally:
                service.release_second_partial.set()
                manager.close()
                state_directory.chmod(0o700)
                time.sleep(0.05)


class QueryTaskJournalMigrationTest(unittest.TestCase):
    def test_invalid_answer_saved_type_is_rejected_without_rewriting_v2(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = Path(temporary_directory) / "query-tasks.json"
            record = _task_record("query-invalid-answer-state", answer="Partial answer")
            record["answer_saved"] = "false"
            original = json.dumps({"journal_version": 2, "tasks": [record]})
            journal.write_text(original, encoding="utf-8")

            manager = QueryTaskManager(StubQueryService(), journal_path=journal)
            try:
                readiness = manager.persistence_readiness()
                self.assertFalse(readiness["query_persistence_ready"])
                self.assertEqual(
                    readiness["query_persistence_issue_code"],
                    "query_state_corrupt",
                )
                self.assertEqual(journal.read_text(encoding="utf-8"), original)
            finally:
                manager.close()

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
