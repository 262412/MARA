from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path

from .query_tasks import QueryTaskConflictError, QueryTaskManager


class StubQueryService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, list[str]]] = []
        self.block_after_partial = False
        self.fail_after_partial = False
        self.partial_emitted = threading.Event()
        self.release = threading.Event()

    def stream_query(
        self,
        conversation_id: str,
        prompt: str,
        selected_file_ids: list[str],
    ):
        self.calls.append((conversation_id, prompt, selected_file_ids))
        yield {
            "stage": "retrieving",
            "answer": "",
            "final": False,
            "citations": [],
        }
        yield {
            "stage": "generating",
            "answer": "Partial answer",
            "final": False,
            "citations": [],
        }
        self.partial_emitted.set()
        if self.block_after_partial:
            self.release.wait(timeout=5)
        if self.fail_after_partial:
            raise RuntimeError("failed at /private/model/config.json")
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
        }


def wait_for_terminal(manager: QueryTaskManager, task_id: str) -> dict:
    snapshot = manager.get_task(task_id)
    while snapshot["status"] in {"queued", "running"}:
        snapshot = manager.wait_for_change(
            task_id,
            snapshot["version"],
            timeout=2,
        )
    return snapshot


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
            duplicate = manager.create_task(
                "ignored-session",
                "Ignored duplicate",
                ["file-2"],
                idempotency_key="query-1",
            )

            self.assertEqual(duplicate["task_id"], created["task_id"])
            completed = wait_for_terminal(manager, created["task_id"])
            self.assertEqual(completed["status"], "success")
            self.assertEqual(completed["answer"], "Final answer")
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
            self.assertEqual(cancelled["answer"], "Partial answer")
            self.assertTrue(cancelled["retryable"])
            self.assertEqual(cancelled["qa_scope"], "multi_document")

            service.block_after_partial = False
            retried = manager.retry_task(
                created["task_id"],
                idempotency_key="query-retry",
            )
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
            self.assertEqual(failed["error"]["code"], "query_failed")
            self.assertEqual(failed["answer"], "Partial answer")
            self.assertTrue(failed["retryable"])
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


if __name__ == "__main__":
    unittest.main()
