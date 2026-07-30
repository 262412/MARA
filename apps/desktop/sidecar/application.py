from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

DESKTOP_DATA_DIRECTORIES = (
    "state",
    "documents",
    "previews",
    "cache",
    "logs",
    "backups",
    "tmp",
)
FILE_RESPONSE_FIELDS = (
    "file_id",
    "name",
    "size",
    "tokens",
    "loader",
    "date_created",
)


def _collect_doctor() -> dict[str, Any]:
    from slide_cli.docqa_runtime import collect_docqa_doctor_payload

    return collect_docqa_doctor_payload()


def _collect_files() -> list[dict[str, Any]]:
    from slide_cli.docqa_runtime import collect_docqa_file_records

    return collect_docqa_file_records()


def _collect_sessions() -> list[dict[str, Any]]:
    from slide_cli.docqa_runtime import collect_docqa_session_summaries

    return collect_docqa_session_summaries()


class DesktopApplicationService:
    def __init__(
        self,
        *,
        collect_doctor: Callable[[], dict[str, Any]] = _collect_doctor,
        collect_files: Callable[[], list[dict[str, Any]]] = _collect_files,
        collect_sessions: Callable[[], list[dict[str, Any]]] = _collect_sessions,
    ) -> None:
        self._collect_doctor = collect_doctor
        self._collect_files = collect_files
        self._collect_sessions = collect_sessions

    def get_doctor(self) -> dict[str, Any]:
        return self._collect_doctor()

    def list_files(self) -> list[dict[str, Any]]:
        return [
            {field: record.get(field) for field in FILE_RESPONSE_FIELDS}
            for record in self._collect_files()
        ]

    def list_sessions(self) -> list[dict[str, Any]]:
        return self._collect_sessions()


def configure_desktop_data_root(data_root: Path) -> Path:
    expanded_root = data_root.expanduser()
    if not expanded_root.is_absolute():
        raise ValueError("Desktop data root must be absolute")
    resolved_root = expanded_root.resolve()

    for directory in DESKTOP_DATA_DIRECTORIES:
        (resolved_root / directory).mkdir(parents=True, exist_ok=True)

    app_data_dir = resolved_root / "state" / "ktem_app_data"
    app_data_dir.mkdir(parents=True, exist_ok=True)
    os.environ["MARA_DESKTOP_DATA_DIR"] = str(resolved_root)
    os.environ["KH_APP_DATA_DIR"] = str(app_data_dir)
    os.environ["THEFLOW_SETTINGS_MODULE"] = "ktem.default_flowsettings"
    os.environ["KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED"] = "1"
    return app_data_dir
