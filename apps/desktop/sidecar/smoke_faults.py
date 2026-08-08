from __future__ import annotations

import errno
import sqlite3
from typing import Any, Protocol

from .index_task_journal import IndexTaskJournal, persistence_error_from

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
