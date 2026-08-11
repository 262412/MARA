from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from .application import DesktopApplicationService
from .indexing_readiness import DesktopIndexingPreflightError, IndexingReadiness


class DesktopApplicationIndexingContractTest(unittest.TestCase):
    def test_unconfigured_embedding_is_blocked_before_runtime_or_task_work(
        self,
    ) -> None:
        runtime_created = False

        def create_runtime():
            nonlocal runtime_created
            runtime_created = True
            raise AssertionError("runtime must not be created")

        blocked = IndexingReadiness.blocked(
            code="embedding_not_configured",
            message="Configure an embedding model before indexing files.",
            action="configure_embedding",
            retryable=False,
        )
        service = DesktopApplicationService(
            create_runtime=create_runtime,
            collect_indexing_readiness=lambda: blocked,
        )

        with self.assertRaisesRegex(
            DesktopIndexingPreflightError,
            "Configure an embedding model",
        ):
            service.validate_indexing(["/private/source/paper.txt"])

        self.assertFalse(runtime_created)

    def test_reuses_runtime_index_and_delete_services_without_exposing_paths(
        self,
    ) -> None:
        calls: list[tuple] = []

        class Runtime:
            def index_paths(self, paths, reindex=False):
                calls.append(("index", paths, reindex))
                return SimpleNamespace(
                    as_dict=lambda: {
                        "successes": [
                            {
                                "file_name": "paper.pdf",
                                "file_path": "/private/source/paper.pdf",
                                "status": "success",
                            }
                        ],
                        "failures": [
                            {
                                "file_name": "broken.pdf",
                                "file_path": "/private/source/broken.pdf",
                                "status": "failed",
                                "message": "failed at /private/source/broken.pdf",
                            }
                        ],
                        "debug_messages": ["private runtime details"],
                    }
                )

            def delete_files(self, refs):
                calls.append(("delete", refs))
                return [
                    SimpleNamespace(
                        file_id=file_id,
                        name=f"{file_id}.pdf",
                        path=f"/private/storage/{file_id}.pdf",
                    )
                    for file_id in refs
                ]

        service = DesktopApplicationService(create_runtime=Runtime)

        self.assertEqual(
            service.index_files(
                ["/private/source/paper.pdf", "/private/source/broken.pdf"],
                reindex=True,
            ),
            {
                "successes": [{"name": "paper.pdf"}],
                "failures": [
                    {
                        "name": "broken.pdf",
                        "code": "index_failed",
                        "message": "MARA could not index this file.",
                        "retryable": True,
                    }
                ],
            },
        )
        self.assertEqual(
            service.delete_files(["file-1", "file-2"]),
            [
                {"file_id": "file-1", "name": "file-1.pdf"},
                {"file_id": "file-2", "name": "file-2.pdf"},
            ],
        )
        self.assertEqual(
            calls,
            [
                (
                    "index",
                    ["/private/source/paper.pdf", "/private/source/broken.pdf"],
                    True,
                ),
                ("delete", ["file-1", "file-2"]),
            ],
        )

    def test_classifies_runtime_provider_failures_without_exposing_diagnostics(
        self,
    ) -> None:
        class Runtime:
            def __init__(self, message: str) -> None:
                self.message = message

            def index_paths(self, paths, reindex=False):
                return SimpleNamespace(
                    as_dict=lambda: {
                        "successes": [],
                        "failures": [
                            {
                                "file_name": Path(paths[0]).name,
                                "file_path": paths[0],
                                "status": "failed",
                                "message": self.message,
                            }
                        ],
                        "debug_messages": [],
                    }
                )

        cases = [
            (
                "Error code: 401 - invalid API key at /private/config",
                "embedding_not_configured",
                False,
            ),
            (
                "Error code: 503 - provider unavailable at /private/config",
                "embedding_unavailable",
                True,
            ),
            (
                "No module named 'google.generativeai' from /private/install",
                "embedding_dependency_missing",
                False,
            ),
        ]
        for message, code, retryable in cases:
            with self.subTest(code=code):
                service = DesktopApplicationService(
                    create_runtime=lambda: Runtime(message),
                )
                result = service.index_files(["/private/source/paper.txt"])

                self.assertEqual(result["failures"][0]["code"], code)
                self.assertEqual(result["failures"][0]["retryable"], retryable)
                self.assertNotIn("/private", str(result))


if __name__ == "__main__":
    unittest.main()
