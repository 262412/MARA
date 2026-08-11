from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .indexing_readiness import (
    DesktopIndexingPreflightError,
    evaluate_embedding_readiness,
    validate_index_sources,
    validate_indexing_storage,
)


def _embedding(
    *,
    provider_type: str = "kotaemon.embeddings.OpenAIEmbeddings",
    api_key: str = "configured-key",
    default: bool = True,
) -> dict:
    return {
        "desktop": {
            "default": default,
            "spec": {
                "__type__": provider_type,
                "api_key": api_key,
                "base_url": "http://127.0.0.1:43123/v1",
                "model": "desktop-loopback-embedding",
            },
        }
    }


class DesktopIndexingReadinessTest(unittest.TestCase):
    def test_empty_and_placeholder_credentials_are_not_configured(self) -> None:
        for credential in (
            "",
            "  ",
            "<YOUR_OPENAI_KEY>",
            "your-key",
            "YOUR_API_KEY",
            "YOUR_KEY",
        ):
            with self.subTest(credential=credential):
                readiness = evaluate_embedding_readiness(
                    _embedding(api_key=credential),
                    module_available=lambda _module: True,
                )
                self.assertFalse(readiness.indexing_ready)
                self.assertEqual(
                    readiness.indexing_issue_code,
                    "embedding_not_configured",
                )
                self.assertFalse(readiness.retryable)
                self.assertEqual(readiness.indexing_action, "configure_embedding")

    def test_fresh_configuration_has_no_random_default(self) -> None:
        no_models = evaluate_embedding_readiness(
            {},
            module_available=lambda _module: True,
        )
        no_default = evaluate_embedding_readiness(
            _embedding(default=False),
            module_available=lambda _module: True,
        )

        self.assertEqual(no_models.indexing_issue_code, "embedding_not_configured")
        self.assertEqual(no_default.indexing_issue_code, "embedding_not_configured")
        self.assertFalse(no_models.indexing_ready)
        self.assertFalse(no_default.indexing_ready)

    def test_only_packaged_openai_compatible_providers_can_be_ready(self) -> None:
        ready = evaluate_embedding_readiness(
            _embedding(),
            module_available=lambda module: module == "openai",
        )
        google = evaluate_embedding_readiness(
            _embedding(
                provider_type="kotaemon.embeddings.LCGoogleEmbeddings",
                api_key="configured-google-key",
            ),
            module_available=lambda _module: True,
        )
        missing_openai = evaluate_embedding_readiness(
            _embedding(),
            module_available=lambda _module: False,
        )

        self.assertTrue(ready.indexing_ready)
        self.assertIsNone(ready.indexing_issue_code)
        for blocked in (google, missing_openai):
            self.assertFalse(blocked.indexing_ready)
            self.assertEqual(
                blocked.indexing_issue_code,
                "embedding_dependency_missing",
            )
            self.assertFalse(blocked.retryable)
            self.assertEqual(blocked.indexing_action, "repair_installation")

    def test_unwritable_runtime_storage_fails_closed_without_a_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            data_root = Path(temporary_directory) / "MARA"

            def deny_write(_directory: Path) -> None:
                raise PermissionError("denied: /private/cache/theflow")

            with self.assertRaises(DesktopIndexingPreflightError) as raised:
                validate_indexing_storage(data_root, probe=deny_write)

        self.assertEqual(
            raised.exception.code,
            "index_runtime_storage_unwritable",
        )
        self.assertFalse(raised.exception.retryable)
        self.assertNotIn("/private", str(raised.exception))

    def test_source_permission_denied_is_non_retryable_and_path_free(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory) / "private-note.txt"
            source.write_text("unique desktop source", encoding="utf-8")

            def deny_read(_path: Path) -> None:
                raise PermissionError("denied: /private/source/private-note.txt")

            with self.assertRaises(DesktopIndexingPreflightError) as raised:
                validate_index_sources([str(source)], probe=deny_read)

        self.assertEqual(raised.exception.code, "source_permission_denied")
        self.assertFalse(raised.exception.retryable)
        self.assertNotIn("/private", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
