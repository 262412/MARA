from __future__ import annotations

import unittest
from types import SimpleNamespace

from .application import DesktopApplicationService, DesktopSessionNotFoundError


class DesktopSessionMutationApplicationServiceTest(unittest.TestCase):
    def test_reuses_runtime_create_and_owner_scoped_mutations(self) -> None:
        calls: list[tuple[str, str, str | None]] = []

        class Runtime:
            def __init__(self) -> None:
                self.name = "Original session"

            def create_session(self):
                calls.append(("create", "session-created", None))
                return self._session("session-created")

            def rename_session(self, conversation_id, name):
                if conversation_id == "session-missing":
                    raise PermissionError("owner scope")
                calls.append(("rename", conversation_id, name))
                self.name = name

            def load_session(self, conversation_id):
                return self._session(conversation_id)

            def _session(self, conversation_id):
                return SimpleNamespace(
                    conversation_id=conversation_id,
                    name=self.name,
                    messages=[],
                    graph_source_ids=[],
                    origin="desktop",
                    is_public=False,
                    date_created=None,
                    date_updated=None,
                )

            def delete_session(self, conversation_id):
                if conversation_id == "session-missing":
                    raise PermissionError("owner scope")
                calls.append(("delete", conversation_id, None))

        service = DesktopApplicationService(create_runtime=Runtime)

        created = service.create_session()
        renamed = service.rename_session("session-1", "Renamed session")
        self.assertEqual(created["conversation_id"], "session-created")
        self.assertEqual(created["messages"], [])
        self.assertEqual(renamed["name"], "Renamed session")
        self.assertEqual(service.delete_session("session-1"), "session-1")
        self.assertEqual(
            calls,
            [
                ("create", "session-created", None),
                ("rename", "session-1", "Renamed session"),
                ("delete", "session-1", None),
            ],
        )
        with self.assertRaises(DesktopSessionNotFoundError):
            service.rename_session("session-missing", "Missing")
        with self.assertRaises(DesktopSessionNotFoundError):
            service.delete_session("session-missing")


if __name__ == "__main__":
    unittest.main()
