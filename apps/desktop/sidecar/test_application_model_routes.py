from __future__ import annotations

import unittest
from types import SimpleNamespace

from .application import DesktopApplicationService
from .indexing_readiness import IndexingReadiness
from .model_routes import query_route_name
from .query_readiness import QueryReadiness


class DesktopApplicationModelRouteTest(unittest.TestCase):
    def test_doctor_and_query_validation_share_runtime_route_identity(self) -> None:
        identity = SimpleNamespace(
            query_route_name="openai",
            query_provider="openai",
            query_model="gpt-5.6-luna",
            embedding_route_name="ollama",
            embedding_provider="ollama",
            embedding_model="nomic-embed-text",
            settings_revision="settings-revision-3",
            sidecar_pid=4321,
            route_fingerprint="a" * 64,
        )

        class Runtime:
            def load_session(self, conversation_id):
                return SimpleNamespace(conversation_id=conversation_id)

        service = DesktopApplicationService(
            collect_doctor=lambda: {
                "ok": True,
                "llm_default": "legacy",
                "embedding_default": "google",
            },
            collect_files=lambda: [{"file_id": "file-1", "name": "paper.pdf"}],
            collect_indexing_readiness=IndexingReadiness.ready,
            collect_query_readiness=lambda: QueryReadiness.ready(
                query_provider="openai",
                query_model="gpt-5.6-luna",
                embedding_provider="ollama",
                embedding_model="nomic-embed-text",
            ),
            create_runtime=Runtime,
            prepare_model_routes=lambda: identity,
        )

        doctor = service.get_doctor()
        diagnostics = service.validate_query("session-1", "Question", ["file-1"])

        self.assertEqual(doctor["llm_default"], "openai")
        self.assertEqual(doctor["query_model"], "gpt-5.6-luna")
        self.assertEqual(doctor["settings_revision"], "settings-revision-3")
        self.assertEqual(doctor["sidecar_pid"], 4321)
        self.assertEqual(doctor["route_fingerprint"], "a" * 64)
        self.assertEqual(
            diagnostics,
            {
                "settings_revision": "settings-revision-3",
                "sidecar_pid": 4321,
                "route_fingerprint": "a" * 64,
                "route_provider": "openai",
                "route_model": "gpt-5.6-luna",
            },
        )

    def test_legacy_runtime_keeps_implicit_model_selection(self) -> None:
        self.assertIsNone(query_route_name(None))


if __name__ == "__main__":
    unittest.main()
