from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .smoke_model_route_fixture import (
    LEGACY_SECRET_SENTINEL,
    seed_legacy_model_routes,
    verify_migrated_model_routes,
)


class SmokeModelRouteFixtureTest(unittest.TestCase):
    def test_stale_route_fixture_proves_canonical_migration_and_secret_scrub(
        self,
    ) -> None:
        # Keep ktem lazy so unittest discovery cannot bootstrap its process-wide
        # settings before the older real-application smoke fixture selects its
        # dedicated data root.
        from ktem.desktop_model_routes import prepare_desktop_model_routes

        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory) / "MARA"
            database = seed_legacy_model_routes(data_root)
            self.assertIn(LEGACY_SECRET_SENTINEL.encode(), database.read_bytes())
            settings = {
                "KH_LLMS": {
                    "ollama": {
                        "default": True,
                        "spec": {
                            "__type__": "kotaemon.llms.ChatOpenAI",
                            "model": "gpt-5.6-luna",
                            "base_url": "http://127.0.0.1:43127/v1",
                            "api_key": "ollama",
                        },
                    }
                },
                "KH_EMBEDDINGS": {
                    "ollama": {
                        "default": True,
                        "spec": {
                            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
                            "model": "smoke-embedding",
                            "base_url": "http://127.0.0.1:43127/v1",
                            "api_key": "ollama",
                        },
                    }
                },
            }

            prepare_desktop_model_routes(
                settings,
                database_path=database,
                data_root=data_root,
                settings_revision="settings-revision-smoke",
            )
            report = verify_migrated_model_routes(
                data_root,
                expected_chat_model="gpt-5.6-luna",
            )

            self.assertEqual(report["chat_model"], "gpt-5.6-luna")
            self.assertTrue(report["plaintext_secret_absent"])
            self.assertNotIn(
                LEGACY_SECRET_SENTINEL,
                json.dumps(report),
            )

    def test_verification_rejects_plaintext_credentials_anywhere_in_data_root(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory) / "MARA"
            database = seed_legacy_model_routes(data_root)
            from ktem.desktop_model_routes import prepare_desktop_model_routes

            settings = {
                "KH_LLMS": {
                    "openai": {
                        "default": True,
                        "spec": {
                            "__type__": "kotaemon.llms.ChatOpenAI",
                            "model": "gpt-5.6-luna",
                            "base_url": "http://127.0.0.1:43127/v1",
                            "api_key": "current-fake-key",
                        },
                    }
                },
                "KH_EMBEDDINGS": {
                    "openai": {
                        "default": True,
                        "spec": {
                            "__type__": "kotaemon.embeddings.OpenAIEmbeddings",
                            "model": "smoke-embedding",
                            "base_url": "http://127.0.0.1:43127/v1",
                            "api_key": "current-fake-key",
                        },
                    }
                },
            }
            prepare_desktop_model_routes(
                settings,
                database_path=database,
                data_root=data_root,
                settings_revision="settings-revision-smoke",
            )
            log_path = data_root / "logs" / "indexing.log"
            log_path.parent.mkdir(parents=True)
            log_path.write_text("current-fake-key", encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "plaintext"):
                verify_migrated_model_routes(
                    data_root,
                    expected_chat_model="gpt-5.6-luna",
                    forbidden_secrets=("current-fake-key",),
                )


if __name__ == "__main__":
    unittest.main()
