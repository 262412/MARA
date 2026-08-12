from __future__ import annotations

import errno
import os
import sqlite3
from pathlib import Path
from typing import Any, Protocol

from .index_task_journal import IndexTaskJournal, persistence_error_from
from .query_task_journal import QueryTaskJournal, QueryTaskPersistenceError

DISK_FULL_FAULT = "disk_full"
DATABASE_LOCKED_FAULT = "database_locked"


class IndexService(Protocol):
    def index_files(
        self,
        paths: list[str],
        *,
        reindex: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        ...


class FailOnceJournal:
    def __init__(self, delegate: IndexTaskJournal, error: OSError) -> None:
        self._delegate = delegate
        self._error: OSError | None = error

    def load(self) -> dict[str, Any] | None:
        return self._delegate.load()

    def save(self, payload: dict[str, Any]) -> None:
        if self._error is not None:
            error, self._error = self._error, None
            raise persistence_error_from(error)
        self._delegate.save(payload)


class FailOnceIndexService:
    def __init__(self, delegate: IndexService, error: Exception) -> None:
        self._delegate = delegate
        self._error: Exception | None = error

    def index_files(
        self,
        paths: list[str],
        *,
        reindex: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        if self._error is not None:
            error, self._error = self._error, None
            raise error
        return self._delegate.index_files(paths, reindex=reindex)


class PartialQueryJournalFault:
    def __init__(self, delegate: QueryTaskJournal, marker: Path) -> None:
        self._delegate = delegate
        self._marker = marker
        self._faulted = False

    def load(self) -> dict[str, Any] | None:
        return self._delegate.load()

    def probe(self) -> None:
        if self._faulted and self._marker.exists():
            raise _query_permission_error("write_temp")
        self._delegate.probe()

    def save(self, payload: dict[str, Any]) -> None:
        if self._faulted and self._marker.exists():
            raise _query_permission_error("atomic_replace")
        if self._marker.exists() and _contains_running_partial(payload):
            self._faulted = True
            raise _query_permission_error("flush")
        self._delegate.save(payload)


def inject_smoke_fault(
    service: IndexService,
    journal: IndexTaskJournal,
    fault: str | None,
) -> tuple[IndexService, IndexTaskJournal]:
    if fault is None:
        return service, journal
    if fault == DISK_FULL_FAULT:
        return service, FailOnceJournal(
            journal,
            OSError(errno.ENOSPC, "No space left on device"),
        )
    if fault == DATABASE_LOCKED_FAULT:
        return (
            FailOnceIndexService(
                service,
                sqlite3.OperationalError("database is locked"),
            ),
            journal,
        )
    raise ValueError("Unsupported Desktop smoke fault")


def inject_query_smoke_fault(
    journal: QueryTaskJournal,
    marker: Path | None,
) -> QueryTaskJournal:
    return PartialQueryJournalFault(journal, marker) if marker is not None else journal


def query_smoke_fault_marker(data_root: Path) -> Path | None:
    marker = os.environ.get("MARA_DESKTOP_QUERY_SMOKE_FAULT_MARKER", "")
    if not marker:
        return None
    resolved = Path(marker).resolve()
    expected_parent = (data_root / "tmp").resolve()
    if resolved.parent != expected_parent:
        raise ValueError("Query smoke fault marker must be Desktop-owned.")
    return resolved


def _contains_running_partial(payload: dict[str, Any]) -> bool:
    tasks = payload.get("tasks", [])
    return any(
        isinstance(task, dict)
        and task.get("status") == "running"
        and bool(task.get("answer"))
        for task in tasks
    )


def _query_permission_error(operation: str) -> QueryTaskPersistenceError:
    return QueryTaskPersistenceError(
        "query_state_permission_denied",
        "MARA cannot write answer state until app data permissions are fixed.",
        retryable=True,
        operation=operation,
        error_type="PermissionError",
        error_number=errno.EACCES,
        winerror=5,
    )
