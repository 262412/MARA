from __future__ import annotations

import errno
import logging
import sqlite3
import threading
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy.exc import OperationalError as SqlAlchemyOperationalError

from .index_task_journal import (
    IndexTaskJournal,
    IndexTaskPersistenceError,
    JsonIndexTaskJournal,
)

TERMINAL_STATUSES = {"partial", "success", "failed", "cancelled"}
ACTIVE_STATUSES = {"queued", "running"}
JOURNAL_VERSION = 1
LOGGER = logging.getLogger("mara.desktop.index_tasks")


class IndexService(Protocol):
    def index_files(
        self,
        paths: list[str],
        *,
        reindex: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        ...


class IndexTaskNotFoundError(LookupError):
    pass


class IndexTaskConflictError(RuntimeError):
    pass


@dataclass
class _TaskSource:
    path: str
    name: str
    status: str = "pending"
    error: dict[str, Any] | None = None


@dataclass
class _IndexTask:
    task_id: str
    idempotency_key: str
    reindex: bool
    sources: list[_TaskSource]
    status: str = "queued"
    stage: str = "queued"
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())
    version: int = 1
    cancel_requested: bool = False
    error: dict[str, Any] | None = None


class IndexTaskManager:
    def __init__(
        self,
        service: IndexService,
        *,
        journal_path: Path | None = None,
        journal: IndexTaskJournal | None = None,
    ) -> None:
        self._service = service
        self._journal = journal or JsonIndexTaskJournal(journal_path)
        self._tasks: dict[str, _IndexTask] = {}
        self._idempotency: dict[str, str] = {}
        self._condition = threading.Condition(threading.RLock())
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="mara-index-task",
        )
        self._closed = False
        self._load_journal()

    def create_task(
        self,
        paths: list[str],
        *,
        reindex: bool,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self._condition:
            _require_open(self._closed)
            existing = self._task_for_idempotency(idempotency_key)
            if existing is not None:
                return self._snapshot(existing)
            task = _IndexTask(
                task_id=str(uuid4()),
                idempotency_key=idempotency_key,
                reindex=reindex,
                sources=[
                    _TaskSource(path=path, name=Path(path).name or "Unknown file")
                    for path in paths
                ],
            )
            _persist_new_task(
                self._tasks,
                self._idempotency,
                task,
                self._save_journal,
            )
            snapshot = self._snapshot(task)
            self._executor.submit(self._run_task, task.task_id)
            return snapshot

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._condition:
            return self._snapshot(self._require_task(task_id))

    def get_latest_task(self) -> dict[str, Any] | None:
        with self._condition:
            if not self._tasks:
                return None
            latest = max(self._tasks.values(), key=lambda task: task.created_at)
            return self._snapshot(latest)

    def retry_task(
        self,
        task_id: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self._condition:
            _require_open(self._closed)
            existing = self._task_for_idempotency(idempotency_key)
            if existing is not None:
                return self._snapshot(existing)
            original = self._require_task(task_id)
            if original.status not in {"partial", "failed", "cancelled"}:
                raise IndexTaskConflictError(
                    "Only partial, failed, or cancelled tasks can be retried."
                )
            sources = [
                source for source in original.sources if source.status != "success"
            ]
            if not sources:
                raise IndexTaskConflictError("The task has no retryable files.")
            retried = _IndexTask(
                task_id=str(uuid4()),
                idempotency_key=idempotency_key,
                reindex=True,
                sources=[
                    _TaskSource(path=source.path, name=source.name)
                    for source in sources
                ],
            )
            _persist_new_task(
                self._tasks,
                self._idempotency,
                retried,
                self._save_journal,
            )
            snapshot = self._snapshot(retried)
            self._executor.submit(self._run_task, retried.task_id)
            return snapshot

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        with self._condition:
            task = self._require_task(task_id)
            if task.status == "cancelled":
                return self._snapshot(task)
            if task.status not in ACTIVE_STATUSES:
                raise IndexTaskConflictError(
                    "Only queued or running tasks can be cancelled."
                )
            task.cancel_requested = True
            task.stage = "cancelling"
            self._touch(task)
            return self._snapshot(task)

    def wait_for_change(
        self,
        task_id: str,
        version: int,
        *,
        timeout: float,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        with self._condition:
            task = self._require_task(task_id)
            while task.version <= version and task.status not in TERMINAL_STATUSES:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
                task = self._require_task(task_id)
            return self._snapshot(task)

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run_task(self, task_id: str) -> None:
        try:
            self._execute_task(task_id)
        except IndexTaskPersistenceError as error:
            _record_persistence_failure(
                self._condition,
                self._tasks,
                task_id,
                error,
            )

    def _execute_task(self, task_id: str) -> None:
        with self._condition:
            task = self._require_task(task_id)
            if task.cancel_requested:
                self._finish_cancelled(task)
                return
            task.status = "running"
            task.stage = "indexing"
            self._touch(task)

        for source_index in range(len(task.sources)):
            with self._condition:
                task = self._require_task(task_id)
                if task.cancel_requested:
                    break
                source = task.sources[source_index]
            try:
                result = self._service.index_files(
                    [source.path],
                    reindex=task.reindex,
                )
            except Exception as exc:
                LOGGER.error(
                    "Index task failed task_id=%s file_name=%s error_type=%s",
                    task_id,
                    source.name,
                    type(exc).__name__,
                )
                result = {
                    "successes": [],
                    "failures": [_failure_from_exception(source.name, exc)],
                }
            with self._condition:
                task = self._require_task(task_id)
                source = task.sources[source_index]
                if result.get("successes") and not result.get("failures"):
                    source.status = "success"
                    source.error = None
                else:
                    source.status = "failed"
                    source.error = _failure_from_result(source.name, result)
                self._touch(task)

        with self._condition:
            task = self._require_task(task_id)
            if task.cancel_requested:
                self._finish_cancelled(task)
                return
            successes = sum(source.status == "success" for source in task.sources)
            failures = sum(source.status == "failed" for source in task.sources)
            if successes == len(task.sources):
                task.status = "success"
                task.stage = "completed"
                task.error = None
            elif successes:
                task.status = "partial"
                task.stage = "completed"
                task.error = {
                    "code": "index_partial_failure",
                    "message": "Some files could not be indexed.",
                    "retryable": True,
                }
            else:
                task.status = "failed"
                task.stage = "completed"
                task.error = _task_failure(task.sources, bool(failures))
            self._touch(task)

    def _finish_cancelled(self, task: _IndexTask) -> None:
        task.status = "cancelled"
        task.stage = "completed"
        task.error = {
            "code": "index_cancelled",
            "message": "Indexing was cancelled.",
            "retryable": True,
        }
        self._touch(task)

    def _touch(self, task: _IndexTask) -> None:
        task.version += 1
        task.updated_at = _now()
        self._save_journal()
        self._condition.notify_all()

    def _task_for_idempotency(self, key: str) -> _IndexTask | None:
        task_id = self._idempotency.get(key)
        return self._tasks.get(task_id) if task_id else None

    def _require_task(self, task_id: str) -> _IndexTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise IndexTaskNotFoundError(task_id)
        return task

    def _snapshot(self, task: _IndexTask) -> dict[str, Any]:
        success_count = sum(source.status == "success" for source in task.sources)
        failures = [source.error for source in task.sources if source.error]
        return {
            "task_id": task.task_id,
            "status": task.status,
            "stage": task.stage,
            "completed_files": sum(
                source.status in {"success", "failed"} for source in task.sources
            ),
            "total_files": len(task.sources),
            "file_names": [source.name for source in task.sources],
            "success_count": success_count,
            "failure_count": len(failures),
            "failures": failures,
            "error": task.error,
            "retryable": task.status in {"partial", "failed", "cancelled"},
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "version": task.version,
        }

    def _load_journal(self) -> None:
        payload = self._journal.load()
        if payload is None:
            return
        if payload.get("journal_version") != JOURNAL_VERSION:
            raise RuntimeError("Unsupported Desktop index task journal version.")
        interrupted = False
        for item in payload.get("tasks", []):
            task = _task_from_dict(item)
            if task.status in ACTIVE_STATUSES:
                task.status = "failed"
                task.stage = "interrupted"
                task.error = {
                    "code": "index_interrupted",
                    "message": "Indexing was interrupted when MARA Desktop stopped.",
                    "retryable": True,
                }
                task.version += 1
                task.updated_at = _now()
                interrupted = True
            self._tasks[task.task_id] = task
            self._idempotency[task.idempotency_key] = task.task_id
        if interrupted:
            self._save_journal()

    def _save_journal(self) -> None:
        self._journal.save(
            {
                "journal_version": JOURNAL_VERSION,
                "tasks": [_task_to_dict(task) for task in self._tasks.values()],
            }
        )


def _persist_new_task(
    tasks: dict[str, _IndexTask],
    idempotency: dict[str, str],
    task: _IndexTask,
    save: Callable[[], None],
) -> None:
    tasks[task.task_id] = task
    idempotency[task.idempotency_key] = task.task_id
    try:
        save()
    except IndexTaskPersistenceError:
        tasks.pop(task.task_id, None)
        idempotency.pop(task.idempotency_key, None)
        raise


def _require_open(closed: bool) -> None:
    if closed:
        raise IndexTaskConflictError("The index task manager is stopping.")


def _record_persistence_failure(
    condition: threading.Condition,
    tasks: dict[str, _IndexTask],
    task_id: str,
    error: IndexTaskPersistenceError,
) -> None:
    LOGGER.error(
        "Index task persistence failed task_id=%s error_code=%s",
        task_id,
        error.code,
    )
    with condition:
        _set_persistence_failure(tasks[task_id], error)
        condition.notify_all()


def _set_persistence_failure(
    task: _IndexTask,
    error: IndexTaskPersistenceError,
) -> None:
    for source in task.sources:
        source.status = "failed"
        source.error = _known_failure(source.name, error.code, error.message)
    task.status = "failed"
    task.stage = "storage_error"
    task.error = {
        "code": error.code,
        "message": error.message,
        "retryable": True,
    }
    task.version += 1
    task.updated_at = _now()


def _safe_failure(name: str) -> dict[str, Any]:
    return {
        "name": name,
        "code": "index_failed",
        "message": "MARA could not index this file.",
        "retryable": True,
    }


def _known_failure(name: str, code: str, message: str) -> dict[str, Any]:
    return {
        "name": name,
        "code": code,
        "message": message,
        "retryable": True,
    }


def _failure_from_exception(name: str, error: Exception) -> dict[str, Any]:
    if isinstance(error, OSError) and (
        error.errno == errno.ENOSPC or getattr(error, "winerror", None) == 112
    ):
        return _known_failure(
            name,
            "index_storage_full",
            "MARA does not have enough free storage to index this file.",
        )
    if isinstance(error, (sqlite3.OperationalError, SqlAlchemyOperationalError)) and (
        "locked" in str(error).lower() or "busy" in str(error).lower()
    ):
        return _known_failure(
            name,
            "index_database_locked",
            "MARA data is temporarily busy. Try indexing this file again.",
        )
    return _safe_failure(name)


def _task_failure(
    sources: list[_TaskSource],
    retryable: bool,
) -> dict[str, Any]:
    failures = [source.error for source in sources if source.error]
    codes = {failure["code"] for failure in failures}
    if len(codes) == 1 and next(iter(codes)) in {
        "index_storage_full",
        "index_database_locked",
    }:
        failure = failures[0]
        return {
            "code": failure["code"],
            "message": failure["message"],
            "retryable": bool(failure["retryable"]),
        }
    return {
        "code": "index_failed",
        "message": "MARA could not index the selected files.",
        "retryable": retryable,
    }


def _failure_from_result(name: str, result: dict[str, Any]) -> dict[str, Any]:
    failures = result.get("failures", [])
    if not failures:
        return _safe_failure(name)
    failure = failures[0]
    return {
        "name": Path(str(failure.get("name", name))).name or name,
        "code": str(failure.get("code", "index_failed")),
        "message": "MARA could not index this file.",
        "retryable": bool(failure.get("retryable", True)),
    }


def _task_to_dict(task: _IndexTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "idempotency_key": task.idempotency_key,
        "reindex": task.reindex,
        "sources": [source.__dict__ for source in task.sources],
        "status": task.status,
        "stage": task.stage,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "version": task.version,
        "cancel_requested": task.cancel_requested,
        "error": task.error,
    }


def _task_from_dict(item: dict[str, Any]) -> _IndexTask:
    return _IndexTask(
        task_id=str(item["task_id"]),
        idempotency_key=str(item["idempotency_key"]),
        reindex=bool(item.get("reindex", False)),
        sources=[_TaskSource(**source) for source in item.get("sources", [])],
        status=str(item.get("status", "failed")),
        stage=str(item.get("stage", "interrupted")),
        created_at=str(item.get("created_at", _now())),
        updated_at=str(item.get("updated_at", _now())),
        version=int(item.get("version", 1)),
        cancel_requested=bool(item.get("cancel_requested", False)),
        error=item.get("error"),
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
