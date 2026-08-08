from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from .server import create_app


class SuccessfulIndexService:
    def get_doctor(self) -> dict:
        return {}

    def list_files(self) -> list[dict]:
        return []

    def list_sessions(self) -> list[dict]:
        return []

    def get_import_capabilities(self) -> dict[str, list[str]]:
        return {"supported_extensions": [".txt"]}

    def index_files(self, paths: list[str], *, reindex: bool = False) -> dict:
        return {
            "successes": [{"name": Path(path).name} for path in paths],
            "failures": [],
        }

    def delete_file(self, file_id: str) -> list[dict[str, str]]:
        return []


class StorageFaultContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "test-token"
        self.source_path = str(
            (Path.cwd() / "private" / "source" / "paper.txt").resolve()
        )
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Request-ID": "storage-fault-request",
        }

    def _create_task(
        self,
        client: TestClient,
        *,
        key: str,
    ):
        return client.post(
            "/v1/index-tasks",
            headers={**self.headers, "Idempotency-Key": key},
            json={"paths": [self.source_path], "reindex": False},
        )

    def _wait_for_terminal(self, client: TestClient, task_id: str) -> dict:
        response = client.get(
            f"/v1/index-tasks/{task_id}",
            headers=self.headers,
        )
        task = response.json()["task"]
        while task["status"] in {"queued", "running"}:
            task = client.get(
                f"/v1/index-tasks/{task_id}",
                headers=self.headers,
            ).json()["task"]
        return task

    def test_disk_full_returns_stable_error_then_accepts_a_new_task(self) -> None:
        app = create_app(
            self.token,
            SuccessfulIndexService(),
            smoke_fault="disk_full",
        )
        client = TestClient(app)
        try:
            with self.assertLogs("mara.desktop.sidecar", level="ERROR") as logs:
                failed = self._create_task(client, key="disk-full-1")

            self.assertEqual(failed.status_code, 503)
            self.assertEqual(failed.json()["code"], "index_storage_full")
            self.assertTrue(failed.json()["retryable"])
            self.assertEqual(
                failed.json()["request_id"],
                "storage-fault-request",
            )
            self.assertNotIn(self.source_path, failed.text)
            self.assertNotIn(self.source_path, "\n".join(logs.output))

            recovered = self._create_task(client, key="disk-full-2")
            self.assertEqual(recovered.status_code, 202)
            terminal = self._wait_for_terminal(
                client,
                recovered.json()["task"]["task_id"],
            )
            self.assertEqual(terminal["status"], "success")
        finally:
            app.state.index_task_manager.close()

    def test_database_lock_is_a_retryable_path_free_task_failure(self) -> None:
        app = create_app(
            self.token,
            SuccessfulIndexService(),
            smoke_fault="database_locked",
        )
        client = TestClient(app)
        try:
            created = self._create_task(client, key="database-lock-1")
            self.assertEqual(created.status_code, 202)
            failed = self._wait_for_terminal(
                client,
                created.json()["task"]["task_id"],
            )
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["error"]["code"], "index_database_locked")
            self.assertEqual(
                failed["failures"][0]["code"],
                "index_database_locked",
            )
            self.assertTrue(failed["retryable"])
            self.assertNotIn(self.source_path, str(failed))

            retried = client.post(
                f"/v1/index-tasks/{failed['task_id']}/retry",
                headers={**self.headers, "Idempotency-Key": "database-lock-retry-1"},
            )
            self.assertEqual(retried.status_code, 202)
            terminal = self._wait_for_terminal(
                client,
                retried.json()["task"]["task_id"],
            )
            self.assertEqual(terminal["status"], "success")
        finally:
            app.state.index_task_manager.close()


if __name__ == "__main__":
    unittest.main()
