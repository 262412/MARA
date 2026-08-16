from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from .query_tasks import QueryTaskManager
from .test_query_tasks import StubQueryService


class QueryTerminalJournalMigrationTest(unittest.TestCase):
    def test_v2_migration_adds_terminal_fields_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal = Path(temporary_directory) / "query-tasks.json"
            journal.write_text(
                json.dumps({"journal_version": 2, "tasks": [_v2_task_record()]}),
                encoding="utf-8",
            )

            manager = QueryTaskManager(StubQueryService(), journal_path=journal)
            try:
                migrated_task = manager.get_task("query-v2")
            finally:
                manager.close()

            migrated = json.loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(migrated["journal_version"], 3)
            self.assertEqual(migrated["tasks"][0]["terminal_semantic_commit"], {})
            self.assertEqual(migrated["tasks"][0]["terminal_outcome"], "")
            self.assertEqual(migrated["tasks"][0]["terminal_outcome_reason"], "")

            second_manager = QueryTaskManager(StubQueryService(), journal_path=journal)
            try:
                self.assertEqual(
                    second_manager.get_task("query-v2")["version"],
                    migrated_task["version"],
                )
            finally:
                second_manager.close()


def _v2_task_record() -> dict[str, Any]:
    return {
        "task_id": "query-v2",
        "turn_id": "query-v2",
        "idempotency_key": "query-v2",
        "retry_of_task_id": None,
        "conversation_id": "session-1",
        "prompt": "Question",
        "selected_file_ids": ["file-1"],
        "status": "running",
        "stage": "generating",
        "answer": "Saved partial",
        "citations": [],
        "created_at": "2026-08-08T10:00:00Z",
        "updated_at": "2026-08-08T10:00:01Z",
        "version": 2,
        "cancel_requested": False,
        "error": None,
    }
