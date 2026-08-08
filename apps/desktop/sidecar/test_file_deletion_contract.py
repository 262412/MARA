from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from .application import DesktopMutationError
from .server import create_app


class BatchDeleteApplicationService:
    def __init__(self) -> None:
        self.delete_calls: list[list[str]] = []

    def get_doctor(self) -> dict:
        return {}

    def list_files(self) -> list[dict]:
        return []

    def list_sessions(self) -> list[dict]:
        return []

    def get_session(self, conversation_id: str) -> dict:
        return {"conversation_id": conversation_id}

    def get_import_capabilities(self) -> dict[str, list[str]]:
        return {"supported_extensions": [".txt"]}

    def index_files(self, paths: list[str], *, reindex: bool = False) -> dict:
        return {
            "successes": [{"name": Path(path).name} for path in paths],
            "failures": [],
        }

    def delete_file(self, file_id: str) -> list[dict[str, str]]:
        return self.delete_files([file_id])

    def delete_files(self, file_ids: list[str]) -> list[dict[str, str]]:
        self.delete_calls.append(file_ids)
        return [{"file_id": file_id, "name": f"{file_id}.txt"} for file_id in file_ids]


class FailingBatchDeleteApplicationService(BatchDeleteApplicationService):
    def delete_files(self, file_ids: list[str]) -> list[dict[str, str]]:
        raise DesktopMutationError("failed at /private/storage/paper.txt")


class BatchFileDeletionContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "test-token"
        self.service = BatchDeleteApplicationService()
        self.client = TestClient(create_app(self.token, self.service))
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Request-ID": "batch-delete-request",
            "Idempotency-Key": "batch-delete-1",
        }

    def tearDown(self) -> None:
        self.client.app.state.index_task_manager.close()

    def test_batch_delete_is_authenticated_idempotent_and_path_free(self) -> None:
        response = self.client.post(
            "/v1/file-deletions",
            headers=self.headers,
            json={"file_ids": ["file-1", "file-2"]},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["deleted_file_ids"],
            ["file-1", "file-2"],
        )
        self.assertNotIn("path", response.text)
        duplicate = self.client.post(
            "/v1/file-deletions",
            headers=self.headers,
            json={"file_ids": ["file-1", "file-2"]},
        )
        self.assertEqual(
            duplicate.json()["deleted_file_ids"],
            ["file-1", "file-2"],
        )
        self.assertEqual(self.service.delete_calls, [["file-1", "file-2"]])

        unauthenticated = self.client.post(
            "/v1/file-deletions",
            json={"file_ids": ["file-1"]},
        )
        self.assertEqual(unauthenticated.status_code, 401)

    def test_batch_delete_rejects_invalid_and_duplicate_identifiers(self) -> None:
        invalid = self.client.post(
            "/v1/file-deletions",
            headers={**self.headers, "Idempotency-Key": "batch-invalid"},
            json={"file_ids": ["file-1", "/private/source/paper.txt"]},
        )
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["code"], "invalid_request")

        duplicate = self.client.post(
            "/v1/file-deletions",
            headers={**self.headers, "Idempotency-Key": "batch-duplicate"},
            json={"file_ids": ["file-1", "file-1"]},
        )
        self.assertEqual(duplicate.status_code, 422)

    def test_batch_delete_failure_is_stable_retryable_and_path_free(self) -> None:
        with TestClient(
            create_app(self.token, FailingBatchDeleteApplicationService())
        ) as client:
            response = client.post(
                "/v1/file-deletions",
                headers={**self.headers, "Idempotency-Key": "batch-failure"},
                json={"file_ids": ["file-1", "file-2"]},
            )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "file_delete_failed")
        self.assertTrue(response.json()["retryable"])
        self.assertEqual(response.json()["request_id"], "batch-delete-request")
        self.assertNotIn("/private", response.text)


if __name__ == "__main__":
    unittest.main()
