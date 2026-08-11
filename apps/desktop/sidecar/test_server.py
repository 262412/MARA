from __future__ import annotations

import json
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from .application import DesktopSessionNotFoundError
from .indexing_readiness import DesktopIndexingPreflightError
from .server import PROTOCOL_VERSION, create_app


class StubApplicationService:
    def __init__(self) -> None:
        self.delete_calls: list[list[str]] = []

    def get_doctor(self) -> dict:
        return {
            "ok": True,
            "app_name": "MARA",
            "default_user_id": "default",
            "index_name": "File Collection",
            "index_id": 1,
            "llm_default": "local",
            "embedding_default": "local",
            "file_count": 1,
            "session_count": 1,
            "graph_cache_dir": "/desktop/state/knowledge_graph/conversations",
            "issues": [],
            "warnings": [],
            "indexing_ready": True,
            "indexing_issue_code": None,
            "indexing_message": "File indexing is ready.",
            "indexing_action": "none",
            "indexing_retryable": False,
        }

    def list_files(self) -> list[dict]:
        return [
            {
                "file_id": "file-1",
                "name": "paper.pdf",
                "size": 1024,
                "tokens": 42,
                "loader": "PDFLoader",
                "date_created": "2026-07-30T10:00:00",
            }
        ]

    def list_sessions(self) -> list[dict]:
        return [
            {
                "conversation_id": "session-1",
                "name": "Research session",
                "message_count": 2,
                "graph_source_count": 1,
                "origin": "desktop",
                "is_public": False,
                "date_created": "2026-07-30T10:00:00",
                "date_updated": "2026-07-30T10:05:00",
            }
        ]

    def get_session(self, conversation_id: str) -> dict:
        if conversation_id != "session-1":
            raise DesktopSessionNotFoundError(conversation_id)
        return {
            "conversation_id": conversation_id,
            "name": "Research session",
            "messages": [
                {"role": "user", "content": "What is MARA?"},
                {
                    "role": "assistant",
                    "content": "A local research assistant.",
                },
            ],
            "graph_source_ids": ["file-1"],
            "origin": "desktop",
            "is_public": False,
            "date_created": "2026-07-30T10:00:00",
            "date_updated": "2026-07-30T10:05:00",
        }

    def create_session(self) -> dict:
        session = self.get_session("session-1")
        session["conversation_id"] = "session-created"
        session["messages"] = []
        return session

    def rename_session(self, conversation_id: str, name: str) -> dict:
        session = self.get_session(conversation_id)
        session["name"] = name
        return session

    def delete_session(self, conversation_id: str) -> str:
        self.get_session(conversation_id)
        return conversation_id

    def get_import_capabilities(self) -> dict:
        return {
            "supported_extensions": [
                ".pdf",
                ".docx",
                ".xlsx",
                ".pptx",
                ".csv",
                ".html",
                ".mhtml",
                ".txt",
                ".md",
                ".zip",
            ]
        }

    def index_files(self, paths: list[str], *, reindex: bool = False) -> dict:
        return {
            "successes": [{"name": Path(path).name} for path in paths],
            "failures": [],
        }

    def validate_indexing(self, _paths: list[str]) -> None:
        return None

    def delete_file(self, file_id: str) -> list[dict]:
        return self.delete_files([file_id])

    def delete_files(self, file_ids: list[str]) -> list[dict]:
        self.delete_calls.append(file_ids)
        return [{"file_id": file_id, "name": f"{file_id}.pdf"} for file_id in file_ids]


class FailingApplicationService(StubApplicationService):
    def get_doctor(self) -> dict:
        raise RuntimeError("database is locked")


class UnconfiguredEmbeddingService(StubApplicationService):
    def validate_indexing(self, _paths: list[str]) -> None:
        raise DesktopIndexingPreflightError(
            "embedding_not_configured",
            "Configure an embedding model before indexing files.",
            retryable=False,
            status_code=409,
        )


class SidecarContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "test-token"
        self.service = StubApplicationService()
        self.client = TestClient(create_app(self.token, self.service))

    def tearDown(self) -> None:
        self.client.app.state.index_task_manager.close()

    def authenticated_get(
        self,
        path: str,
        *,
        token: str | None = None,
        origin: str | None = None,
        request_id: str = "request-123",
    ):
        headers = {
            "Authorization": f"Bearer {token or self.token}",
            "X-Request-ID": request_id,
        }
        if origin is not None:
            headers["Origin"] = origin
        return self.client.get(path, headers=headers)

    def authenticated_request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        idempotency_key: str | None = None,
        request_id: str = "request-123",
    ):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Request-ID": request_id,
        }
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return self.client.request(method, path, headers=headers, json=json)

    def test_health_rejects_missing_credentials_with_stable_error(self) -> None:
        response = self.client.get("/health", headers={"X-Request-ID": "request-401"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {
                "code": "unauthorized",
                "message": "Valid Sidecar credentials are required.",
                "details": None,
                "retryable": False,
                "request_id": "request-401",
            },
        )

    def test_health_reports_only_runtime_metadata(self) -> None:
        response = self.authenticated_get("/health")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["state"], "healthy")
        self.assertEqual(payload["protocol"], PROTOCOL_VERSION)
        self.assertIn("session_create", payload["capabilities"])
        self.assertNotIn("token", payload)
        self.assertNotIn("port", payload)

    def test_rejects_requests_with_a_browser_origin(self) -> None:
        response = self.authenticated_get(
            "/v1/doctor",
            origin="https://attacker.invalid",
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "origin_forbidden")

    def test_doctor_files_and_sessions_use_versioned_contracts(self) -> None:
        doctor = self.authenticated_get("/v1/doctor").json()
        files = self.authenticated_get("/v1/files").json()
        sessions = self.authenticated_get("/v1/sessions").json()

        self.assertTrue(doctor["doctor"]["ok"])
        self.assertEqual(doctor["request_id"], "request-123")
        self.assertEqual(files["files"][0]["file_id"], "file-1")
        self.assertNotIn("path", files["files"][0])
        self.assertEqual(files["request_id"], "request-123")
        self.assertEqual(sessions["sessions"][0]["conversation_id"], "session-1")
        self.assertEqual(sessions["request_id"], "request-123")

        self.assertTrue(doctor["doctor"]["indexing_ready"])
        self.assertIsNone(doctor["doctor"]["indexing_issue_code"])
        self.assertEqual(doctor["doctor"]["request_id"], "request-123")

    def test_session_detail_is_authenticated_validated_and_path_free(self) -> None:
        response = self.authenticated_get("/v1/sessions/session-1")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["request_id"], "request-123")
        self.assertEqual(payload["session"]["conversation_id"], "session-1")
        self.assertEqual(
            payload["session"]["messages"][1],
            {"role": "assistant", "content": "A local research assistant."},
        )
        self.assertNotIn("path", response.text.lower())

        unauthenticated = self.client.get("/v1/sessions/session-1")
        self.assertEqual(unauthenticated.status_code, 401)
        invalid = self.authenticated_get("/v1/sessions/session!1")
        self.assertEqual(invalid.status_code, 422)
        rejected_query = self.authenticated_get("/v1/sessions/session-1?raw=true")
        self.assertEqual(rejected_query.status_code, 422)
        missing = self.authenticated_get("/v1/sessions/session-missing")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(missing.json()["code"], "session_not_found")

    def test_import_capabilities_are_authenticated_and_path_free(self) -> None:
        response = self.authenticated_get("/v1/import-capabilities")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["request_id"], "request-123")
        self.assertIn(
            ".pdf", response.json()["import_capabilities"]["supported_extensions"]
        )
        self.assertNotIn("path", response.text.lower())

        unauthenticated = self.client.get("/v1/import-capabilities")
        self.assertEqual(unauthenticated.status_code, 401)
        rejected_query = self.authenticated_get("/v1/import-capabilities?all=true")
        self.assertEqual(rejected_query.status_code, 422)

    def test_unknown_query_parameters_use_the_stable_validation_error(self) -> None:
        response = self.authenticated_get("/v1/files?path=/etc/passwd")

        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.json()["code"], "invalid_request")
        self.assertFalse(response.json()["retryable"])
        self.assertEqual(response.json()["request_id"], "request-123")

    def test_application_failures_do_not_expose_tracebacks(self) -> None:
        client = TestClient(create_app(self.token, FailingApplicationService()))
        with self.assertLogs("mara.desktop.sidecar", level="ERROR"):
            response = client.get(
                "/v1/doctor",
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "X-Request-ID": "request-503",
                },
            )

        self.assertEqual(response.status_code, 503)
        payload = response.json()
        self.assertEqual(payload["code"], "application_service_unavailable")
        self.assertTrue(payload["retryable"])
        self.assertEqual(payload["request_id"], "request-503")
        self.assertNotIn("traceback", response.text.lower())
        self.assertNotIn("database is locked", response.text.lower())

    def test_index_task_contract_is_authenticated_idempotent_and_path_free(
        self,
    ) -> None:
        private_root = Path.cwd().resolve() / "private" / "source"
        source_path = str(private_root / "paper.pdf")
        ignored_path = str(private_root / "ignored.pdf")
        self.assertIsNone(
            self.authenticated_get("/v1/index-tasks/latest").json()["task"]
        )
        response = self.authenticated_request(
            "POST",
            "/v1/index-tasks",
            json={"paths": [source_path], "reindex": False},
            idempotency_key="import-request-1",
        )

        self.assertEqual(response.status_code, 202)
        created = response.json()["task"]
        duplicate = self.authenticated_request(
            "POST",
            "/v1/index-tasks",
            json={"paths": [ignored_path], "reindex": True},
            idempotency_key="import-request-1",
        ).json()["task"]
        self.assertEqual(duplicate["task_id"], created["task_id"])
        self.assertEqual(
            self.authenticated_get("/v1/index-tasks/latest").json()["task"]["task_id"],
            created["task_id"],
        )

        task_id = created["task_id"]
        task = self.authenticated_get(f"/v1/index-tasks/{task_id}").json()["task"]
        while task["status"] in {"queued", "running"}:
            task = self.authenticated_get(f"/v1/index-tasks/{task_id}").json()["task"]
        self.assertEqual(task["status"], "success")
        self.assertNotIn(str(private_root), json.dumps(task))

        events = self.authenticated_get(f"/v1/index-tasks/{task_id}/events")
        self.assertEqual(events.status_code, 200)
        self.assertIn("event: task", events.text)
        self.assertNotIn(str(private_root), events.text)

    def test_index_tasks_validate_authentication_parameters_and_idempotency(
        self,
    ) -> None:
        unauthenticated = self.client.post(
            "/v1/index-tasks",
            json={"paths": ["/private/source/paper.pdf"]},
        )
        self.assertEqual(unauthenticated.status_code, 401)

        missing_key = self.authenticated_request(
            "POST",
            "/v1/index-tasks",
            json={"paths": ["/private/source/paper.pdf"]},
        )
        self.assertEqual(missing_key.status_code, 422)
        self.assertEqual(missing_key.json()["code"], "invalid_request")

        relative_path = self.authenticated_request(
            "POST",
            "/v1/index-tasks",
            json={"paths": ["relative/paper.pdf"]},
            idempotency_key="import-relative",
        )
        self.assertEqual(relative_path.status_code, 422)
        self.assertEqual(relative_path.json()["code"], "invalid_request")

    def test_delete_uses_stable_file_id_and_returns_no_local_path(self) -> None:
        response = self.authenticated_request(
            "DELETE",
            "/v1/files/file-1",
            idempotency_key="delete-file-1",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_file_ids"], ["file-1"])
        self.assertNotIn("path", response.text)
        duplicate = self.authenticated_request(
            "DELETE",
            "/v1/files/file-1",
            idempotency_key="delete-file-1",
        )
        self.assertEqual(duplicate.json()["deleted_file_ids"], ["file-1"])
        self.assertEqual(self.service.delete_calls, [["file-1"]])

    def test_unknown_index_task_uses_stable_not_found_error(self) -> None:
        response = self.authenticated_get("/v1/index-tasks/task-missing")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "index_task_not_found")
        self.assertFalse(response.json()["retryable"])

    def test_openapi_declares_explicit_desktop_endpoints(self) -> None:
        schema = create_app(self.token, StubApplicationService()).openapi()

        self.assertIn("/v1/doctor", schema["paths"])
        self.assertIn("/v1/files", schema["paths"])
        self.assertIn("/v1/sessions", schema["paths"])
        self.assertIn("post", schema["paths"]["/v1/sessions"])
        self.assertIn("/v1/sessions/{conversation_id}", schema["paths"])
        self.assertIn("patch", schema["paths"]["/v1/sessions/{conversation_id}"])
        self.assertIn("delete", schema["paths"]["/v1/sessions/{conversation_id}"])
        self.assertIn("/v1/import-capabilities", schema["paths"])
        self.assertIn("/v1/index-tasks", schema["paths"])
        self.assertIn("/v1/index-tasks/latest", schema["paths"])
        self.assertIn("/v1/index-tasks/{task_id}/events", schema["paths"])
        self.assertIn("/v1/query-tasks", schema["paths"])
        self.assertIn("/v1/query-tasks/latest", schema["paths"])
        self.assertIn("/v1/query-tasks/{task_id}/events", schema["paths"])
        self.assertIn("/v1/query-tasks/{task_id}/retry", schema["paths"])
        self.assertIn("/v1/query-tasks/{task_id}/cancel", schema["paths"])
        self.assertIn("/v1/files/{file_id}", schema["paths"])
        self.assertIn("/v1/file-deletions", schema["paths"])
        self.assertIn("SidecarError", schema["components"]["schemas"])
        self.assertIn("SessionRenameRequest", schema["components"]["schemas"])
        self.assertIn("SessionDeleteResponse", schema["components"]["schemas"])
        self.assertIn("QueryTaskCreateRequest", schema["components"]["schemas"])
        self.assertIn("QueryTaskResponse", schema["components"]["schemas"])
        self.assertEqual(
            schema["components"]["schemas"]["QueryTaskCreateRequest"]["properties"][
                "selected_file_ids"
            ]["maxItems"],
            64,
        )


class SidecarIndexingReadinessContractTest(unittest.TestCase):
    def test_unconfigured_embedding_is_rejected_before_task_creation(self) -> None:
        token = "test-token"
        client = TestClient(create_app(token, UnconfiguredEmbeddingService()))
        try:
            response = client.post(
                "/v1/index-tasks",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Request-ID": "request-no-embedding",
                    "Idempotency-Key": "import-no-embedding",
                },
                json={"paths": ["/private/source/paper.txt"]},
            )
            latest = client.get(
                "/v1/index-tasks/latest",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Request-ID": "request-latest",
                },
            )

            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()["code"], "embedding_not_configured")
            self.assertFalse(response.json()["retryable"])
            self.assertEqual(response.json()["request_id"], "request-no-embedding")
            self.assertNotIn("/private", response.text)
            self.assertIsNone(latest.json()["task"])
        finally:
            client.app.state.index_task_manager.close()


if __name__ == "__main__":
    unittest.main()
