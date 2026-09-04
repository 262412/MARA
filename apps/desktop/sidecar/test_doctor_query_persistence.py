from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from .query_tasks import QueryTaskManager
from .server import create_app
from .test_query_tasks import StubQueryService
from .test_server import StubApplicationService


class DoctorQueryPersistenceTest(unittest.TestCase):
    def test_corrupt_journal_blocks_queries_without_deleting_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            journal_path = Path(temporary_directory) / "query-tasks.json"
            journal_path.write_text("{broken", encoding="utf-8")
            manager = QueryTaskManager(
                StubQueryService(),
                journal_path=journal_path,
            )
            app = create_app(
                "test-token",
                StubApplicationService(),
                query_task_manager=manager,
            )
            client = TestClient(app)
            try:
                response = client.get(
                    "/v1/doctor",
                    headers={"Authorization": "Bearer test-token"},
                )
                self.assertEqual(response.status_code, 200)
                doctor = response.json()["doctor"]
                self.assertFalse(doctor["ok"])
                self.assertFalse(doctor["query_persistence_ready"])
                self.assertEqual(
                    doctor["query_persistence_issue_code"],
                    "query_state_corrupt",
                )
                self.assertFalse(doctor["query_ready"])
                self.assertEqual(doctor["query_issue_code"], "query_state_corrupt")
                self.assertEqual(journal_path.read_text(encoding="utf-8"), "{broken")
            finally:
                app.state.index_task_manager.close()
                manager.close()
