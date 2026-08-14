from __future__ import annotations

import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from ktem.docqa.terminal_semantic_commit import build_terminal_semantic_commit

from . import query_tasks as query_tasks_module
from .query_readiness import QueryFailureContract
from .query_tasks import (
    QueryTaskConflictError,
    QueryTaskManager,
    QueryTaskNotFoundError,
)


class StubQueryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[str]]] = []
        self.validate_calls = 0
        self.turn_ids: list[str] = []
        self.committed_turns: dict[str, dict[str, object]] = {}
        self.block_after_partial = False
        self.fail_after_partial = False
        self.delay_before_partial = 0.0
        self.partial_emitted = threading.Event()
        self.release = threading.Event()

    def validate_query(
        self,
        conversation_id: str,
        prompt: str,
        selected_file_ids: list[str],
    ) -> dict[str, object]:
        self.validate_calls += 1
        return {
            "route_provider": "openai",
            "route_model": "gpt-5.6-luna",
            "settings_revision": "settings-revision-test",
            "sidecar_pid": 4321,
            "route_fingerprint": "a" * 64,
        }

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
        yield {
            "stage": "retrieving",
            "answer": "",
            "final": False,
            "citations": [],
        }
        if self.delay_before_partial:
            time.sleep(self.delay_before_partial)
        yield {
            "stage": "generating",
            "answer": "Partial answer",
            "final": False,
            "citations": [],
        }
        self.partial_emitted.set()
        if self.block_after_partial:
            while not self.release.wait(timeout=0.01):
                if cancel_event is not None and cancel_event.is_set():
                    return
            if cancel_event is not None and cancel_event.is_set():
                return
        if self.fail_after_partial:
            raise RuntimeError("failed at /private/model/config.json")
        if turn_id:
            self.committed_turns[turn_id] = {
                "answer": "Final answer",
                "citations": [],
                "terminal_semantic_commit": _answered_terminal_commit(),
            }
        yield {
            "stage": "completed",
            "answer": "Final answer",
            "final": True,
            "citations": [
                {
                    "citation_id": "chunk-1",
                    "file_id": selected_file_ids[0],
                    "file_name": "paper.pdf",
                    "page_label": "3",
                    "element_id": "paragraph-7",
                    "quote": "Grounded evidence.",
                }
            ],
            "terminal_semantic_commit": _answered_terminal_commit(),
            "terminal_outcome": "answered",
            "terminal_outcome_reason": "",
        }

    def recover_committed_turn(
        self,
        _conversation_id: str,
        turn_id: str,
    ) -> dict[str, object] | None:
        return self.committed_turns.get(turn_id)


def wait_for_terminal(manager: QueryTaskManager, task_id: str) -> dict:
    deadline = time.monotonic() + 10
    snapshot = manager.get_task(task_id)
    while snapshot["status"] in {"queued", "running"}:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Query task {task_id} did not reach a terminal state.")
        snapshot = manager.wait_for_change(
            task_id,
            snapshot["version"],
            timeout=min(2, max(0.01, deadline - time.monotonic())),
        )
    return snapshot


def _answered_terminal_commit() -> dict[str, object]:
    return build_terminal_semantic_commit(
        "Final answer",
        {"status": "supported", "action": "return"},
        {"status": "ok", "action": "return"},
        {"items": [], "metadata": {}},
        presentation_answer="Final answer",
    ).as_dict()


class QueryTaskManagerTest(unittest.TestCase):
    def test_streams_in_background_and_deduplicates_creation(self) -> None:
        service = StubQueryService()
        manager = QueryTaskManager(service)
        try:
            created = manager.create_task(
                "session-1",
                "What does the paper say?",
                ["file-1"],
                idempotency_key="query-1",
            )
            self.assertEqual(created["route_provider"], "openai")
            self.assertEqual(created["route_model"], "gpt-5.6-luna")
            self.assertEqual(created["settings_revision"], "settings-revision-test")
            self.assertEqual(created["sidecar_pid"], 4321)
            self.assertEqual(created["route_fingerprint"], "a" * 64)
            duplicate = manager.create_task(
                "session-1",
                "What does the paper say?",
                ["file-1"],
                idempotency_key="query-1",
            )

            self.assertEqual(duplicate["task_id"], created["task_id"])
            completed = wait_for_terminal(manager, created["task_id"])
            self.assertEqual(completed["status"], "success")
            self.assertEqual(completed["answer"], "Final answer")
            self.assertEqual(completed["terminal_outcome"], "answered")
            self.assertEqual(
                completed["terminal_semantic_commit"]["semantic_answer"],
                "Final answer",
            )
            self.assertEqual(completed["qa_scope"], "document")
            self.assertEqual(completed["citations"][0]["file_id"], "file-1")
            self.assertEqual(
                service.calls,
                [("session-1", "What does the paper say?", ["file-1"])],
            )
            self.assertNotIn("/private", json.dumps(completed))
        finally:
            manager.close()

    def test_cancel_preserves_partial_answer_and_retry_reuses_scope(self) -> None:
        service = StubQueryService()
        service.block_after_partial = True
        manager = QueryTaskManager(service)
        try:
            created = manager.create_task(
                "session-1",
                "Summarize both files",
                ["file-1", "file-2"],
                idempotency_key="query-cancel",
            )
            self.assertTrue(service.partial_emitted.wait(timeout=2))
            cancelling = manager.cancel_task(created["task_id"])
            self.assertEqual(cancelling["stage"], "cancelling")
            service.release.set()
            cancelled = wait_for_terminal(manager, created["task_id"])
            self.assertEqual(cancelled["status"], "cancelled")
            self.assertEqual(cancelled["terminal_outcome"], "cancelled")
            self.assertEqual(cancelled["answer"], "Partial answer")
            self.assertTrue(cancelled["retryable"])
            self.assertEqual(cancelled["qa_scope"], "multi_document")

            service.block_after_partial = False
            retried = manager.retry_task(
                created["task_id"],
                idempotency_key="query-retry",
            )
            self.assertEqual(retried["answer"], "Partial answer")
            completed = wait_for_terminal(manager, retried["task_id"])
            self.assertEqual(completed["status"], "success")
            self.assertEqual(completed["retry_of_task_id"], created["task_id"])
            self.assertEqual(
                service.calls[-1],
                ("session-1", "Summarize both files", ["file-1", "file-2"]),
            )
            with self.assertRaises(QueryTaskConflictError):
                manager.retry_task(
                    completed["task_id"],
                    idempotency_key="retry-success",
                )
        finally:
            manager.close()

    def test_cancel_terminates_a_never_yielding_stream_and_releases_worker(
        self,
    ) -> None:
        class NeverYieldThenSuccessService(StubQueryService):
            def stream_query(
                self,
                conversation_id: str,
                prompt: str,
                selected_file_ids: list[str],
                cancel_event: threading.Event | None = None,
                *,
                turn_id: str = "",
            ):
                if prompt == "Never returns":
                    self.partial_emitted.set()
                    threading.Event().wait()
                    yield  # pragma: no cover
                yield {
                    "stage": "completed",
                    "answer": "Second task completed",
                    "final": True,
                    "citations": [],
                }

        service = NeverYieldThenSuccessService()
        manager = QueryTaskManager(service, stream_idle_timeout=2)
        try:
            first = manager.create_task(
                "session-1",
                "Never returns",
                ["file-1"],
                idempotency_key="never-yields",
            )
            self.assertTrue(service.partial_emitted.wait(timeout=1))
            manager.cancel_task(first["task_id"])
            cancelled = wait_for_terminal(manager, first["task_id"])
            self.assertEqual(cancelled["status"], "cancelled")

            second = manager.create_task(
                "session-1",
                "Can still run",
                ["file-1"],
                idempotency_key="after-cancel",
            )
            completed = wait_for_terminal(manager, second["task_id"])
            self.assertEqual(completed["status"], "success")
            self.assertEqual(completed["answer"], "Second task completed")
        finally:
            manager.close()

    def test_idempotency_keys_are_bound_to_operation_and_target_task(self) -> None:
        manager = QueryTaskManager(StubQueryService())
        try:
            created = manager.create_task(
                "session-1",
                "Question",
                ["file-1"],
                idempotency_key="shared-key",
            )
            wait_for_terminal(manager, created["task_id"])

            with self.assertRaises(QueryTaskNotFoundError):
                manager.retry_task(
                    "missing-task",
                    idempotency_key="shared-key",
                )
            with self.assertRaises(QueryTaskConflictError):
                manager.create_task(
                    "session-1",
                    "Different question",
                    ["file-1"],
                    idempotency_key="shared-key",
                )
        finally:
            manager.close()

    def test_journal_writes_are_coalesced_and_terminal_history_is_bounded(
        self,
    ) -> None:
        class CountingJournal:
            def __init__(self) -> None:
                self.payload = None
                self.save_count = 0

            def load(self):
                return self.payload

            def probe(self):
                return None

            def save(self, payload):
                self.save_count += 1
                self.payload = json.loads(json.dumps(payload))

        class ManyUpdatesService(StubQueryService):
            def stream_query(
                self,
                conversation_id: str,
                prompt: str,
                selected_file_ids: list[str],
                cancel_event: threading.Event | None = None,
                *,
                turn_id: str = "",
            ):
                for index in range(100):
                    yield {
                        "stage": "generating",
                        "answer": "x" * (index + 1),
                        "final": False,
                        "citations": [],
                    }
                yield {
                    "stage": "completed",
                    "answer": prompt,
                    "final": True,
                    "citations": [],
                }

        journal = CountingJournal()
        manager = QueryTaskManager(
            ManyUpdatesService(),
            journal=journal,
            journal_flush_interval=0.25,
            max_retained_tasks=2,
        )
        task_ids: list[str] = []
        try:
            with patch.object(
                query_tasks_module,
                "_now",
                return_value="2026-08-09T10:00:00+00:00",
            ):
                for index in range(3):
                    created = manager.create_task(
                        "session-1",
                        f"Question {index}",
                        ["file-1"],
                        idempotency_key=f"bounded-{index}",
                    )
                    task_ids.append(created["task_id"])
                    wait_for_terminal(manager, created["task_id"])

            self.assertLess(journal.save_count, 20)
            payload = journal.payload
            assert payload is not None
            self.assertEqual(len(payload["tasks"]), 2)
            with self.assertRaises(QueryTaskNotFoundError):
                manager.get_task(task_ids[0])
        finally:
            manager.close()

    def test_failure_is_stable_retryable_and_path_free(self) -> None:
        service = StubQueryService()
        service.fail_after_partial = True
        manager = QueryTaskManager(service)
        try:
            created = manager.create_task(
                "session-1",
                "Question",
                ["file-1"],
                idempotency_key="query-failure",
            )
            failed = wait_for_terminal(manager, created["task_id"])
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["error"]["code"], "query_runtime_failed")
            self.assertEqual(failed["answer"], "Partial answer")
            self.assertFalse(failed["retryable"])
            self.assertNotIn("/private", json.dumps(failed))
        finally:
            manager.close()

    def test_restart_marks_an_active_task_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = Path(temporary_directory) / "query-tasks.json"
            journal.write_text(
                json.dumps(
                    {
                        "journal_version": 1,
                        "tasks": [
                            {
                                "task_id": "query-interrupted",
                                "idempotency_key": "query-original",
                                "retry_of_task_id": None,
                                "conversation_id": "session-1",
                                "prompt": "Question",
                                "selected_file_ids": ["file-1"],
                                "status": "running",
                                "stage": "generating",
                                "answer": "Partial answer",
                                "citations": [],
                                "created_at": "2026-08-08T10:00:00Z",
                                "updated_at": "2026-08-08T10:00:01Z",
                                "version": 3,
                                "cancel_requested": False,
                                "error": None,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            manager = QueryTaskManager(StubQueryService(), journal_path=journal)
            try:
                restored = manager.get_task("query-interrupted")
                self.assertEqual(restored["status"], "failed")
                self.assertEqual(restored["stage"], "interrupted")
                self.assertEqual(restored["answer"], "Partial answer")
                self.assertEqual(restored["error"]["code"], "query_interrupted")
                self.assertTrue(restored["retryable"])
            finally:
                manager.close()


class QueryTaskReadinessTest(unittest.TestCase):
    def test_query_preflight_rejection_does_not_write_the_journal(self) -> None:
        class CountingJournal:
            def __init__(self) -> None:
                self.save_count = 0

            def load(self):
                return None

            def probe(self):
                return None

            def save(self, _payload):
                self.save_count += 1

        class RejectedService(StubQueryService):
            def validate_query(self, conversation_id, prompt, selected_file_ids):
                raise RuntimeError("llm_not_configured")

        journal = CountingJournal()
        manager = QueryTaskManager(RejectedService(), journal=journal)
        try:
            with self.assertRaisesRegex(RuntimeError, "llm_not_configured"):
                manager.create_task(
                    "session-1",
                    "Question",
                    ["file-1"],
                    idempotency_key="query-preflight",
                )
            self.assertEqual(journal.save_count, 0)
            self.assertIsNone(manager.get_latest_task())
        finally:
            manager.close()

    def test_classified_runtime_failure_is_stable(self) -> None:
        self.assertEqual(
            QueryFailureContract(
                code="query_runtime_failed",
                message="MARA could not complete the answer.",
                retryable=False,
            ).as_dict(),
            {
                "code": "query_runtime_failed",
                "message": "MARA could not complete the answer.",
                "retryable": False,
                "provider_request_id": None,
                "diagnostic": None,
            },
        )


class QueryTaskRouteFailureTest(unittest.TestCase):
    def test_provider_request_identity_is_preserved_without_raw_error_text(
        self,
    ) -> None:
        class ProviderError(RuntimeError):
            status_code = 404
            request_id = "provider-request-404"
            body = {"code": "model_not_found"}

        class ProviderFailureService(StubQueryService):
            def stream_query(
                self,
                conversation_id: str,
                prompt: str,
                selected_file_ids: list[str],
                cancel_event: threading.Event | None = None,
                *,
                turn_id: str = "",
            ):
                raise ProviderError("secret-sentinel /private/provider/response")
                yield

        manager = QueryTaskManager(ProviderFailureService())
        try:
            created = manager.create_task(
                "session-1",
                "Question",
                ["file-1"],
                idempotency_key="provider-failure",
            )
            failed = wait_for_terminal(manager, created["task_id"])

            self.assertEqual(failed["error"]["code"], "llm_model_not_found")
            self.assertEqual(
                failed["error"]["provider_request_id"],
                "provider-request-404",
            )
            self.assertEqual(
                failed["error"]["diagnostic"],
                "provider_status=404 provider_code=model_not_found",
            )
            self.assertNotIn("secret-sentinel", json.dumps(failed))
            self.assertNotIn("/private", json.dumps(failed))
        finally:
            manager.close()


if __name__ == "__main__":
    unittest.main()
