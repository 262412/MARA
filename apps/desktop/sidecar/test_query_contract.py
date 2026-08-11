from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from .application import DesktopFileNotFoundError
from .query_task_journal import QueryTaskPersistenceError
from .query_tasks import QueryTaskManager
from .server import create_app
from .test_query_tasks import StubQueryService, wait_for_terminal


class ApplicationService:
    def get_doctor(self) -> dict:
        return {}

    def list_files(self) -> list[dict]:
        return []

    def list_sessions(self) -> list[dict]:
        return []

    def get_session(self, conversation_id: str) -> dict:
        return {"conversation_id": conversation_id}

    def create_session(self) -> dict:
        return {"conversation_id": "session-created"}

    def rename_session(self, conversation_id: str, name: str) -> dict:
        return {"conversation_id": conversation_id, "name": name}

    def delete_session(self, conversation_id: str) -> str:
        return conversation_id

    def get_import_capabilities(self) -> dict[str, list[str]]:
        return {"supported_extensions": [".txt"]}

    def index_files(self, paths: list[str], *, reindex: bool = False) -> dict:
        return {
            "successes": [{"name": Path(path).name} for path in paths],
            "failures": [],
        }

    def validate_indexing(self, _paths: list[str]) -> None:
        return None

    def delete_file(self, file_id: str) -> list[dict[str, str]]:
        return []

    def delete_files(self, file_ids: list[str]) -> list[dict[str, str]]:
        return []


class QueryContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "test-token"
        self.query_service = StubQueryService()
        self.manager = QueryTaskManager(self.query_service)
        self.app = create_app(
            self.token,
            ApplicationService(),
            query_task_manager=self.manager,
        )
        self.client = TestClient(self.app)
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Request-ID": "query-contract-request",
            "Idempotency-Key": "query-create-1",
        }

    def tearDown(self) -> None:
        self.app.state.index_task_manager.close()
        self.manager.close()

    def create_query(self, **overrides):
        payload = {
            "conversation_id": "session-1",
            "prompt": "What does the paper say?",
            "selected_file_ids": ["file-1"],
        }
        payload.update(overrides)
        return self.client.post(
            "/v1/query-tasks",
            headers=self.headers,
            json=payload,
        )

    def test_create_get_and_event_stream_are_authenticated_and_idempotent(
        self,
    ) -> None:
        created = self.create_query()
        duplicate = self.create_query()

        self.assertEqual(created.status_code, 202)
        self.assertEqual(created.json()["request_id"], "query-contract-request")
        self.assertEqual(
            duplicate.json()["task"]["task_id"],
            created.json()["task"]["task_id"],
        )
        task_id = created.json()["task"]["task_id"]
        completed = wait_for_terminal(self.manager, task_id)
        response = self.client.get(
            f"/v1/query-tasks/{task_id}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-Request-ID": "query-get-request",
            },
        )
        latest = self.client.get(
            "/v1/query-tasks/latest",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-Request-ID": "query-latest-request",
            },
        )
        events = self.client.get(
            f"/v1/query-tasks/{task_id}/events",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-Request-ID": "query-events-request",
            },
        )

        self.assertEqual(completed["status"], "success")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(latest.status_code, 200)
        self.assertEqual(latest.json()["task"]["task_id"], task_id)
        self.assertEqual(response.json()["task"]["answer"], "Final answer")
        self.assertIn("event: query", events.text)
        self.assertIn("Final answer", events.text)
        self.assertNotIn("/private", response.text + events.text)

    def test_rejects_untrusted_or_invalid_query_requests(self) -> None:
        cases = [
            self.client.post(
                "/v1/query-tasks",
                json={
                    "conversation_id": "session-1",
                    "prompt": "Question",
                    "selected_file_ids": ["file-1"],
                },
            ),
            self.client.post(
                "/v1/query-tasks",
                headers={**self.headers, "Origin": "https://attacker.invalid"},
                json={
                    "conversation_id": "session-1",
                    "prompt": "Question",
                    "selected_file_ids": ["file-1"],
                },
            ),
            self.client.post(
                "/v1/query-tasks?model=private",
                headers=self.headers,
                json={
                    "conversation_id": "session-1",
                    "prompt": "Question",
                    "selected_file_ids": ["file-1"],
                },
            ),
            self.create_query(path="/private/source/paper.pdf"),
            self.create_query(selected_file_ids=["file-1", "file-1"]),
            self.create_query(
                selected_file_ids=[f"file-{index}" for index in range(65)]
            ),
            self.create_query(prompt="   "),
        ]
        missing_key = self.client.post(
            "/v1/query-tasks",
            headers={"Authorization": f"Bearer {self.token}"},
            json={
                "conversation_id": "session-1",
                "prompt": "Question",
                "selected_file_ids": ["file-1"],
            },
        )

        self.assertEqual(cases[0].status_code, 401)
        self.assertEqual(cases[1].status_code, 403)
        for response in (*cases[2:], missing_key):
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json()["code"], "invalid_request")
        self.assertEqual(self.query_service.calls, [])

    def test_query_prevalidation_returns_specific_missing_source_error(self) -> None:
        class MissingSourceService(StubQueryService):
            def validate_query(
                self,
                conversation_id: str,
                prompt: str,
                selected_file_ids: list[str],
            ) -> None:
                raise DesktopFileNotFoundError(selected_file_ids[0])

        manager = QueryTaskManager(MissingSourceService())
        app = create_app(
            self.token,
            ApplicationService(),
            query_task_manager=manager,
        )
        client = TestClient(app)
        try:
            response = client.post(
                "/v1/query-tasks",
                headers=self.headers,
                json={
                    "conversation_id": "session-1",
                    "prompt": "Question",
                    "selected_file_ids": ["file-missing"],
                },
            )
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["code"], "file_not_found")
        finally:
            app.state.index_task_manager.close()
            manager.close()

    def test_query_errors_are_stable_for_missing_conflicting_and_storage_states(
        self,
    ) -> None:
        missing = self.client.get(
            "/v1/query-tasks/query-missing",
            headers={"Authorization": f"Bearer {self.token}"},
        )
        created = self.create_query()
        completed = wait_for_terminal(
            self.manager,
            created.json()["task"]["task_id"],
        )
        conflict = self.client.post(
            f"/v1/query-tasks/{completed['task_id']}/retry",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Idempotency-Key": "query-conflict-retry",
            },
        )

        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["code"], "query_task_not_found")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["code"], "query_task_conflict")

        unrelated_replay = self.client.post(
            "/v1/query-tasks/query-missing/retry",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Idempotency-Key": "query-create-1",
            },
        )
        self.assertEqual(unrelated_replay.status_code, 404)
        self.assertEqual(unrelated_replay.json()["code"], "query_task_not_found")

        class FailingJournal:
            def load(self):
                return None

            def save(self, payload):
                raise QueryTaskPersistenceError(
                    "query_storage_full",
                    "MARA does not have enough free storage to save answer state.",
                )

        manager = QueryTaskManager(StubQueryService(), journal=FailingJournal())
        app = create_app(
            self.token,
            ApplicationService(),
            query_task_manager=manager,
        )
        client = TestClient(app)
        try:
            storage = client.post(
                "/v1/query-tasks",
                headers=self.headers,
                json={
                    "conversation_id": "session-1",
                    "prompt": "Question",
                    "selected_file_ids": ["file-1"],
                },
            )
            self.assertEqual(storage.status_code, 503)
            self.assertEqual(storage.json()["code"], "query_storage_full")
            self.assertTrue(storage.json()["retryable"])
            self.assertNotIn("/private", storage.text)
        finally:
            app.state.index_task_manager.close()
            manager.close()

    def test_cancel_and_retry_preserve_the_original_scope(self) -> None:
        self.query_service.block_after_partial = True
        created = self.create_query(
            prompt="Compare both files",
            selected_file_ids=["file-1", "file-2"],
        )
        task_id = created.json()["task"]["task_id"]
        self.assertTrue(self.query_service.partial_emitted.wait(timeout=2))

        cancelling = self.client.post(
            f"/v1/query-tasks/{task_id}/cancel",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-Request-ID": "query-cancel-request",
            },
        )
        self.query_service.release.set()
        cancelled = wait_for_terminal(self.manager, task_id)

        self.assertEqual(cancelling.status_code, 200)
        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(cancelled["answer"], "Partial answer")

        self.query_service.block_after_partial = False
        retried = self.client.post(
            f"/v1/query-tasks/{task_id}/retry",
            headers={
                "Authorization": f"Bearer {self.token}",
                "X-Request-ID": "query-retry-request",
                "Idempotency-Key": "query-retry-1",
            },
        )
        completed = wait_for_terminal(
            self.manager,
            retried.json()["task"]["task_id"],
        )
        self.assertEqual(retried.status_code, 202)
        self.assertEqual(completed["status"], "success")
        self.assertEqual(completed["selected_file_ids"], ["file-1", "file-2"])
        self.assertEqual(completed["retry_of_task_id"], task_id)


if __name__ == "__main__":
    unittest.main()
