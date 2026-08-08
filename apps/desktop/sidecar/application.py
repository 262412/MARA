from __future__ import annotations

import os
import threading
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


def _create_runtime() -> Any:
    from slide_cli.docqa_runtime import create_docqa_runtime

    return create_docqa_runtime(include_query_features=False)


class DesktopFileNotFoundError(LookupError):
    pass


class DesktopMutationError(RuntimeError):
    pass


class DesktopApplicationService:
    def __init__(
        self,
        *,
        collect_doctor: Callable[[], dict[str, Any]] = _collect_doctor,
        collect_files: Callable[[], list[dict[str, Any]]] = _collect_files,
        collect_sessions: Callable[[], list[dict[str, Any]]] = _collect_sessions,
        create_runtime: Callable[[], Any] = _create_runtime,
    ) -> None:
        self._collect_doctor = collect_doctor
        self._collect_files = collect_files
        self._collect_sessions = collect_sessions
        self._create_runtime = create_runtime
        self._runtime: Any | None = None
        self._mutation_lock = threading.Lock()

    def get_doctor(self) -> dict[str, Any]:
        return self._collect_doctor()

    def list_files(self) -> list[dict[str, Any]]:
        return [
            {field: record.get(field) for field in FILE_RESPONSE_FIELDS}
            for record in self._collect_files()
        ]

    def list_sessions(self) -> list[dict[str, Any]]:
        return self._collect_sessions()

    def index_files(
        self,
        paths: list[str],
        *,
        reindex: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        with self._mutation_lock:
            result = self._get_runtime().index_paths(paths, reindex=reindex).as_dict()
        return {
            "successes": [
                {"name": _index_result_name(item)}
                for item in result.get("successes", [])
            ],
            "failures": [
                {
                    "name": _index_result_name(item),
                    "code": "index_failed",
                    "message": "MARA could not index this file.",
                    "retryable": True,
                }
                for item in result.get("failures", [])
            ],
        }

    def delete_file(self, file_id: str) -> list[dict[str, str]]:
        try:
            with self._mutation_lock:
                records = self._get_runtime().delete_files([file_id])
        except ValueError as exc:
            raise DesktopFileNotFoundError(file_id) from exc
        except Exception as exc:
            raise DesktopMutationError(file_id) from exc
        return [
            {"file_id": str(record.file_id), "name": str(record.name)}
            for record in records
        ]

    def _get_runtime(self) -> Any:
        if self._runtime is None:
            self._runtime = self._create_runtime()
        return self._runtime


def _index_result_name(item: dict[str, Any]) -> str:
    file_name = str(item.get("file_name", "") or "").strip()
    if file_name:
        return Path(file_name).name
    return Path(str(item.get("file_path", "") or "")).name or "Unknown file"


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
