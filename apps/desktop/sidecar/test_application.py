from __future__ import annotations

import os
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from .application import (
    DesktopApplicationService,
    DesktopSessionNotFoundError,
    configure_desktop_data_root,
)


class _StreamingQueryRuntime:
    def __init__(self, requests: list[SimpleNamespace]) -> None:
        self.requests = requests

    def load_session(self, conversation_id):
        return SimpleNamespace(conversation_id=conversation_id)

    def stream_turn(self, request):
        self.requests.append(request)
        yield SimpleNamespace(
            answer="Partial answer",
            event={"channel": "chat", "content": "/private/partial"},
            response=None,
        )
        yield SimpleNamespace(
            answer="Grounded answer [1]",
            event={},
            response=SimpleNamespace(
                conversation_id="session-1",
                answer="Grounded answer [1]",
                selected_file_ids=["file-1"],
                evidence_bundle={
                    "items": [
                        {
                            "evidence_id": "chunk-1",
                            "source_id": "file-1",
                            "source_name": "/private/source/paper.pdf",
                            "page_label": "3",
                            "element_id": "paragraph-7",
                            "text": "The grounded evidence.",
                        }
                    ]
                },
                evidence_metadata={},
            ),
        )


class DesktopApplicationServiceTest(unittest.TestCase):
    def test_desktop_runtime_enables_only_the_gate3_query_profile(self) -> None:
        with patch("slide_cli.docqa_runtime.create_docqa_runtime") as create_runtime:
            from .application import _create_runtime

            _create_runtime()

        create_runtime.assert_called_once_with(
            include_query_features=True,
            include_file_artifacts=False,
            reasoning_paths=("ktem.reasoning.simple.FullQAPipeline",),
        )

    def test_reuses_existing_docqa_service_functions_without_click(self) -> None:
        calls: list[str] = []

        def collect_doctor() -> dict:
            calls.append("doctor")
            return {"ok": True}

        def collect_files() -> list[dict]:
            calls.append("files")
            return [
                {
                    "file_id": "file-1",
                    "name": "paper.pdf",
                    "size": 1024,
                    "tokens": 42,
                    "loader": "PDFLoader",
                    "path": "/private/source/paper.pdf",
                    "date_created": "2026-07-30T10:00:00",
                }
            ]

        def collect_sessions() -> list[dict]:
            calls.append("sessions")
            return [{"conversation_id": "session-1"}]

        def collect_import_capabilities() -> dict:
            calls.append("import-capabilities")
            return {"supported_extensions": [".pdf", ".md"]}

        service = DesktopApplicationService(
            collect_doctor=collect_doctor,
            collect_files=collect_files,
            collect_sessions=collect_sessions,
            collect_import_capabilities=collect_import_capabilities,
        )

        self.assertEqual(service.get_doctor(), {"ok": True})
        self.assertEqual(
            service.list_files(),
            [
                {
                    "file_id": "file-1",
                    "name": "paper.pdf",
                    "size": 1024,
                    "tokens": 42,
                    "loader": "PDFLoader",
                    "date_created": "2026-07-30T10:00:00",
                }
            ],
        )
        self.assertEqual(
            service.list_sessions(),
            [{"conversation_id": "session-1"}],
        )
        self.assertEqual(
            service.get_import_capabilities(),
            {"supported_extensions": [".pdf", ".md"]},
        )
        self.assertEqual(
            calls,
            ["doctor", "files", "sessions", "import-capabilities"],
        )

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

        runtime = Runtime()
        service = DesktopApplicationService(create_runtime=lambda: runtime)

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

    def test_loads_authorized_runtime_session_without_exposing_internal_state(
        self,
    ) -> None:
        created = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)

        class Runtime:
            def load_session(self, conversation_id):
                if conversation_id != "session-1":
                    return None
                return SimpleNamespace(
                    conversation_id=conversation_id,
                    name="Research session",
                    messages=[
                        ("What is MARA?", "A local research assistant."),
                        ("", ""),
                    ],
                    graph_source_ids=["file-1"],
                    origin="desktop",
                    is_public=False,
                    date_created=created,
                    date_updated=None,
                    data_source={"path": "/private/session/source"},
                    user_id="default",
                )

        service = DesktopApplicationService(create_runtime=Runtime)

        self.assertEqual(
            service.get_session("session-1"),
            {
                "conversation_id": "session-1",
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
                "date_created": "2026-08-08T10:00:00+00:00",
                "date_updated": None,
            },
        )
        with self.assertRaises(DesktopSessionNotFoundError):
            service.get_session("session-missing")


class DesktopApplicationRuntimeTest(unittest.TestCase):
    def test_serializes_collectors_with_runtime_initialization(self) -> None:
        collector_started = threading.Event()
        release_collector = threading.Event()
        runtime_started = threading.Event()

        def collect_doctor() -> dict:
            collector_started.set()
            if not release_collector.wait(timeout=2):
                raise RuntimeError("Test collector was not released")
            return {"ok": True}

        class Runtime:
            def load_session(self, conversation_id):
                return SimpleNamespace(
                    conversation_id=conversation_id,
                    name="Serialized session",
                    messages=[],
                    graph_source_ids=[],
                    origin="desktop",
                    is_public=False,
                    date_created=None,
                    date_updated=None,
                )

        def create_runtime():
            runtime_started.set()
            return Runtime()

        service = DesktopApplicationService(
            collect_doctor=collect_doctor,
            create_runtime=create_runtime,
        )
        try:
            with ThreadPoolExecutor(max_workers=2) as executor:
                doctor = executor.submit(service.get_doctor)
                self.assertTrue(collector_started.wait(timeout=1))
                session = executor.submit(service.get_session, "session-1")
                self.assertFalse(runtime_started.wait(timeout=0.1))
                release_collector.set()
                self.assertEqual(doctor.result(timeout=1), {"ok": True})
                self.assertEqual(
                    session.result(timeout=1)["conversation_id"],
                    "session-1",
                )
        finally:
            release_collector.set()

    def test_configures_an_independent_desktop_data_tree(self) -> None:
        environment_names = [
            "KH_APP_DATA_DIR",
            "KH_OFFICE_TO_PDF_INDEXING",
            "KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED",
            "MARA_DESKTOP_DATA_DIR",
            "THEFLOW_SETTINGS_MODULE",
        ]
        original = {name: os.environ.get(name) for name in environment_names}
        try:
            with tempfile.TemporaryDirectory() as temporary_directory:
                root = Path(temporary_directory) / "MARA"
                resolved_root = root.resolve()
                app_data = configure_desktop_data_root(root)

                self.assertEqual(
                    app_data,
                    resolved_root / "state" / "ktem_app_data",
                )
                self.assertEqual(os.environ["KH_APP_DATA_DIR"], str(app_data))
                self.assertEqual(
                    os.environ["KH_OFFICE_TO_PDF_INDEXING"],
                    "false",
                )
                self.assertEqual(
                    os.environ["THEFLOW_SETTINGS_MODULE"],
                    "ktem.default_flowsettings",
                )
                self.assertEqual(
                    os.environ["KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED"],
                    "1",
                )
                for name in [
                    "state",
                    "documents",
                    "previews",
                    "cache",
                    "logs",
                    "backups",
                    "tmp",
                ]:
                    self.assertTrue((resolved_root / name).is_dir())
        finally:
            for name, value in original.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value


class DesktopQueryApplicationServiceTest(unittest.TestCase):
    def test_streams_a_real_docqa_turn_with_safe_source_identity(self) -> None:
        requests: list[SimpleNamespace] = []
        runtime = _StreamingQueryRuntime(requests)

        service = DesktopApplicationService(
            collect_files=lambda: [
                {
                    "file_id": "file-1",
                    "name": "paper.pdf",
                    "size": 1024,
                    "tokens": 42,
                    "loader": "PDFLoader",
                    "path": "/private/source/paper.pdf",
                    "date_created": None,
                }
            ],
            create_runtime=lambda: runtime,
            create_query_request=lambda **values: SimpleNamespace(**values),
        )

        updates = list(
            service.stream_query(
                "session-1",
                "What does the paper say?",
                ["file-1"],
            )
        )

        self.assertEqual(
            updates,
            [
                {
                    "stage": "generating",
                    "answer": "Partial answer",
                    "final": False,
                    "citations": [],
                },
                {
                    "stage": "completed",
                    "answer": "Grounded answer [1]",
                    "final": True,
                    "citations": [
                        {
                            "citation_id": "chunk-1",
                            "file_id": "file-1",
                            "file_name": "paper.pdf",
                            "page_label": "3",
                            "element_id": "paragraph-7",
                            "quote": "The grounded evidence.",
                        }
                    ],
                },
            ],
        )
        request = requests[0]
        self.assertEqual(request.conversation_id, "session-1")
        self.assertEqual(request.prompt, "What does the paper say?")
        self.assertEqual(request.selected_file_ids, ["file-1"])
        self.assertEqual(request.qa_scope, "document")
        self.assertEqual(request.reasoning_type, "simple")
        self.assertEqual(request.use_citation, "inline")
        self.assertEqual(request.origin, "desktop")
        self.assertIsNone(request.llm)
        self.assertEqual(
            request.source_identity_crosswalk,
            [
                {
                    "canonical_dataset_id": "file-1",
                    "runtime_file_id": "file-1",
                    "runtime_source_id": "file-1",
                    "filename": "paper.pdf",
                    "aliases": ["paper.pdf"],
                }
            ],
        )
        self.assertNotIn("/private", str(updates))
        self.assertNotIn("/private", str(request.source_identity_crosswalk))

    def test_query_never_creates_a_replacement_for_a_missing_session(self) -> None:
        class Runtime:
            def load_session(self, conversation_id):
                return None

            def stream_turn(self, request):
                raise AssertionError("A missing session must not start a turn")

        service = DesktopApplicationService(
            collect_files=lambda: [
                {
                    "file_id": "file-1",
                    "name": "paper.pdf",
                }
            ],
            create_runtime=Runtime,
            create_query_request=lambda **values: SimpleNamespace(**values),
        )

        with self.assertRaises(DesktopSessionNotFoundError):
            list(service.stream_query("session-missing", "Question", ["file-1"]))

    def test_projects_generated_reference_evidence_to_selected_files(self) -> None:
        class Runtime:
            def load_session(self, conversation_id):
                return SimpleNamespace(conversation_id=conversation_id)

            def stream_turn(self, _request):
                yield SimpleNamespace(
                    answer="Grounded answer",
                    event={},
                    response=SimpleNamespace(
                        answer="Grounded answer",
                        evidence_bundle={
                            "items": [
                                {
                                    "evidence_id": "citation-refs",
                                    "source_id": "refs",
                                    "source_name": "Generated citations",
                                    "text": "paper.pdf evidence and notes.md evidence",
                                    "metadata": {"source": "references_html"},
                                }
                            ]
                        },
                        evidence_metadata={},
                    ),
                )

        service = DesktopApplicationService(
            collect_files=lambda: [
                {"file_id": "file-1", "name": "paper.pdf"},
                {"file_id": "file-2", "name": "notes.md"},
            ],
            create_runtime=Runtime,
            create_query_request=lambda **values: SimpleNamespace(**values),
        )

        [update] = list(
            service.stream_query(
                "session-1",
                "Compare the sources",
                ["file-1", "file-2"],
            )
        )

        self.assertEqual(
            [citation["file_id"] for citation in update["citations"]],
            ["file-1", "file-2"],
        )
        self.assertEqual(
            len({citation["citation_id"] for citation in update["citations"]}),
            2,
        )
        self.assertNotIn("/private", str(update))


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
