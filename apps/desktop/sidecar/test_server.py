from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from .server import PROTOCOL_VERSION, create_app


class StubApplicationService:
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


class FailingApplicationService(StubApplicationService):
    def get_doctor(self) -> dict:
        raise RuntimeError("database is locked")


class SidecarContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "test-token"
        self.client = TestClient(create_app(self.token, StubApplicationService()))

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

    def test_openapi_declares_all_gate_two_endpoints(self) -> None:
        schema = create_app(self.token, StubApplicationService()).openapi()

        self.assertIn("/v1/doctor", schema["paths"])
        self.assertIn("/v1/files", schema["paths"])
        self.assertIn("/v1/sessions", schema["paths"])
        self.assertIn("SidecarError", schema["components"]["schemas"])


if __name__ == "__main__":
    unittest.main()
