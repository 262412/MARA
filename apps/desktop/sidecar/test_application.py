from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from .application import DesktopApplicationService, configure_desktop_data_root


class DesktopApplicationServiceTest(unittest.TestCase):
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

        service = DesktopApplicationService(
            collect_doctor=collect_doctor,
            collect_files=collect_files,
            collect_sessions=collect_sessions,
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
        self.assertEqual(calls, ["doctor", "files", "sessions"])

    def test_configures_an_independent_desktop_data_tree(self) -> None:
        environment_names = [
            "KH_APP_DATA_DIR",
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


if __name__ == "__main__":
    unittest.main()
