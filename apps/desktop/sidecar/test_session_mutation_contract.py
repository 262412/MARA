from __future__ import annotations

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from .application import DesktopSessionNotFoundError
from .server import create_app


class SessionMutationService:
    def __init__(self) -> None:
        self.create_calls = 0
        self.rename_calls: list[tuple[str, str]] = []
        self.delete_calls: list[str] = []
        self.name = "Research session"

    def get_doctor(self) -> dict:
        return {}

    def list_files(self) -> list[dict]:
        return []

    def list_sessions(self) -> list[dict]:
        return []

    def get_session(self, conversation_id: str) -> dict:
        if conversation_id != "session-1":
            raise DesktopSessionNotFoundError(conversation_id)
        return self._session(conversation_id)

    def create_session(self) -> dict:
        self.create_calls += 1
        return self._session("session-created")

    def rename_session(self, conversation_id: str, name: str) -> dict:
        if conversation_id != "session-1":
            raise DesktopSessionNotFoundError(conversation_id)
        self.rename_calls.append((conversation_id, name))
        self.name = name
        return self._session(conversation_id)

    def delete_session(self, conversation_id: str) -> str:
        if conversation_id != "session-1":
            raise DesktopSessionNotFoundError(conversation_id)
        self.delete_calls.append(conversation_id)
        return conversation_id

    def get_import_capabilities(self) -> dict[str, list[str]]:
        return {"supported_extensions": [".txt"]}

    def index_files(self, paths: list[str], *, reindex: bool = False) -> dict:
        return {
            "successes": [{"name": Path(path).name} for path in paths],
            "failures": [],
        }

    def delete_file(self, file_id: str) -> list[dict[str, str]]:
        return []

    def delete_files(self, file_ids: list[str]) -> list[dict[str, str]]:
        return []

    def _session(self, conversation_id: str) -> dict:
        return {
            "conversation_id": conversation_id,
            "name": self.name,
            "messages": [],
            "graph_source_ids": [],
            "origin": "desktop",
            "is_public": False,
            "date_created": None,
            "date_updated": None,
        }


class FailingSessionMutationService(SessionMutationService):
    def create_session(self) -> dict:
        raise RuntimeError("failed at /private/session.json")

    def rename_session(self, conversation_id: str, name: str) -> dict:
        raise RuntimeError("failed at /private/session.json")

    def delete_session(self, conversation_id: str) -> str:
        raise RuntimeError("failed at /private/session.json")


class SessionMutationContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.token = "test-token"
        self.service = SessionMutationService()
        self.client = TestClient(create_app(self.token, self.service))

    def tearDown(self) -> None:
        self.client.app.state.index_task_manager.close()

    def request(
        self,
        method: str,
        conversation_id: str,
        *,
        key: str | None,
        payload: dict | None = None,
        query: str = "",
    ):
        headers = {
            "Authorization": f"Bearer {self.token}",
            "X-Request-ID": f"request-{method.lower()}",
        }
        if key is not None:
            headers["Idempotency-Key"] = key
        return self.client.request(
            method,
            f"/v1/sessions/{conversation_id}{query}",
            headers=headers,
            json=payload,
        )

    def create_request(
        self,
        *,
        key: str | None,
        payload: dict | None = None,
        query: str = "",
        authenticated: bool = True,
    ):
        headers = {"X-Request-ID": "request-post"}
        if authenticated:
            headers["Authorization"] = f"Bearer {self.token}"
        if key is not None:
            headers["Idempotency-Key"] = key
        return self.client.post(
            f"/v1/sessions{query}",
            headers=headers,
            json={} if payload is None else payload,
        )

    def test_create_is_idempotent_authenticated_and_path_free(self) -> None:
        created = self.create_request(key="create-session-1")
        duplicate = self.create_request(key="create-session-1")

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["request_id"], "request-post")
        self.assertEqual(
            created.json()["session"]["conversation_id"],
            "session-created",
        )
        self.assertEqual(created.json(), duplicate.json())
        self.assertEqual(self.service.create_calls, 1)
        self.assertNotIn("path", created.text.lower())

        for rejected in (
            self.create_request(key="unauthenticated", authenticated=False),
            self.create_request(key=None),
            self.create_request(key="query", query="?name=private"),
            self.create_request(
                key="extra",
                payload={"path": "/private/session.json"},
            ),
        ):
            self.assertIn(rejected.status_code, (401, 422))
        self.assertEqual(self.service.create_calls, 1)

    def test_rename_and_delete_are_idempotent_and_path_free(self) -> None:
        renamed = self.request(
            "PATCH",
            "session-1",
            key="rename-session-1",
            payload={"name": "  Renamed session  "},
        )
        duplicate = self.request(
            "PATCH",
            "session-1",
            key="rename-session-1",
            payload={"name": "Ignored duplicate"},
        )
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(renamed.json()["session"]["name"], "Renamed session")
        self.assertEqual(duplicate.json()["session"]["name"], "Renamed session")
        self.assertEqual(self.service.rename_calls, [("session-1", "Renamed session")])
        self.assertNotIn("path", renamed.text.lower())

        deleted = self.request("DELETE", "session-1", key="delete-session-1")
        duplicate_delete = self.request("DELETE", "session-1", key="delete-session-1")
        self.assertEqual(deleted.json()["deleted_conversation_id"], "session-1")
        self.assertEqual(
            duplicate_delete.json()["deleted_conversation_id"], "session-1"
        )
        self.assertEqual(self.service.delete_calls, ["session-1"])

    def test_mutations_reject_missing_authentication_and_idempotency(self) -> None:
        unauthenticated = self.client.patch(
            "/v1/sessions/session-1",
            json={"name": "Rejected"},
        )
        missing_key = self.request(
            "PATCH",
            "session-1",
            key=None,
            payload={"name": "Rejected"},
        )
        self.assertEqual(unauthenticated.status_code, 401)
        self.assertEqual(missing_key.status_code, 422)
        self.assertEqual(missing_key.json()["code"], "invalid_request")

    def test_mutations_reject_invalid_names_identifiers_and_queries(self) -> None:
        for index, payload in enumerate(
            (
                {"name": "   "},
                {"name": "x" * 201},
                {"name": "Valid", "path": "/private/session.json"},
            )
        ):
            invalid = self.request(
                "PATCH",
                "session-1",
                key=f"rename-invalid-{index}",
                payload=payload,
            )
            self.assertEqual(invalid.status_code, 422)
            self.assertEqual(invalid.json()["code"], "invalid_request")
        invalid_identifier = self.request("DELETE", "session!1", key="delete-invalid")
        rejected_query = self.request(
            "DELETE",
            "session-1",
            key="delete-query",
            query="?force=true",
        )
        self.assertEqual(invalid_identifier.status_code, 422)
        self.assertEqual(rejected_query.status_code, 422)

    def test_missing_sessions_return_the_stable_not_found_error(self) -> None:
        renamed = self.request(
            "PATCH",
            "session-missing",
            key="rename-missing",
            payload={"name": "Missing"},
        )
        deleted = self.request("DELETE", "session-missing", key="delete-missing")
        for response in (renamed, deleted):
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.json()["code"], "session_not_found")

    def test_failures_are_stable_retryable_and_path_free(self) -> None:
        with TestClient(
            create_app(self.token, FailingSessionMutationService())
        ) as client:
            headers = {
                "Authorization": f"Bearer {self.token}",
                "Idempotency-Key": "failure",
            }
            with self.assertLogs("mara.desktop.sidecar", level="ERROR"):
                renamed = client.patch(
                    "/v1/sessions/session-1",
                    headers={**headers, "X-Request-ID": "rename-failure"},
                    json={"name": "Rejected"},
                )
                deleted = client.delete(
                    "/v1/sessions/session-1",
                    headers={**headers, "X-Request-ID": "delete-failure"},
                )
                created = client.post(
                    "/v1/sessions",
                    headers={**headers, "X-Request-ID": "create-failure"},
                    json={},
                )

        for response, request_id in (
            (created, "create-failure"),
            (renamed, "rename-failure"),
            (deleted, "delete-failure"),
        ):
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["code"], "session_mutation_failed")
            self.assertTrue(response.json()["retryable"])
            self.assertEqual(response.json()["request_id"], request_id)
            self.assertNotIn("/private", response.text)


if __name__ == "__main__":
    unittest.main()
