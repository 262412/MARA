from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from .query_stream_runner import QueryService, QueryStreamRunner
from .query_task_journal import (
    JsonQueryTaskJournal,
    QueryTaskJournal,
    QueryTaskPersistenceError,
)

TERMINAL_QUERY_STATUSES = {"success", "failed", "cancelled"}
ACTIVE_QUERY_STATUSES = {"queued", "running"}
QUERY_JOURNAL_VERSION = 1
DEFAULT_JOURNAL_FLUSH_INTERVAL = 0.25
DEFAULT_MAX_RETAINED_TASKS = 100
DEFAULT_STREAM_IDLE_TIMEOUT = 300.0
LOGGER = logging.getLogger("mara.desktop.query_tasks")
IdempotencyFingerprint = tuple[str, ...]


class QueryTaskNotFoundError(LookupError):
    pass


class QueryTaskConflictError(RuntimeError):
    pass


@dataclass
class _QueryTask:
    task_id: str
    idempotency_key: str
    conversation_id: str
    prompt: str
    selected_file_ids: list[str]
    retry_of_task_id: str | None = None
    status: str = "queued"
    stage: str = "queued"
    answer: str = ""
    citations: list[dict[str, Any]] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now())
    updated_at: str = field(default_factory=lambda: _now())
    version: int = 1
    cancel_requested: bool = False
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    error: dict[str, Any] | None = None


class _QueryTaskPersistence:
    _journal: QueryTaskJournal
    _tasks: dict[str, _QueryTask]
    _idempotency: dict[str, tuple[str, IdempotencyFingerprint]]
    _condition: threading.Condition
    _journal_flush_interval: float
    _last_journal_save: float
    _max_retained_tasks: int

    def _touch(self, task: _QueryTask, *, force_persist: bool = True) -> None:
        task.version += 1
        task.updated_at = _now()
        if (
            force_persist
            or time.monotonic() - self._last_journal_save
            >= self._journal_flush_interval
        ):
            self._save_journal()
        self._condition.notify_all()

    def _persist_new_task(
        self,
        task: _QueryTask,
        fingerprint: IdempotencyFingerprint,
    ) -> None:
        self._tasks[task.task_id] = task
        self._idempotency[task.idempotency_key] = (task.task_id, fingerprint)
        pruned = self._prune_terminal_tasks()
        try:
            self._save_journal()
        except QueryTaskPersistenceError:
            self._tasks.pop(task.task_id, None)
            self._idempotency.pop(task.idempotency_key, None)
            for removed in pruned:
                self._tasks[removed.task_id] = removed
                self._idempotency[removed.idempotency_key] = (
                    removed.task_id,
                    _task_fingerprint(removed),
                )
            raise

    def _record_persistence_failure(
        self,
        task_id: str,
        error: QueryTaskPersistenceError,
    ) -> None:
        LOGGER.error(
            "Query task persistence failed task_id=%s error_code=%s",
            task_id,
            error.code,
        )
        with self._condition:
            task = self._tasks[task_id]
            task.status = "failed"
            task.stage = "storage_error"
            task.error = {
                "code": error.code,
                "message": error.message,
                "retryable": True,
            }
            task.version += 1
            task.updated_at = _now()
            self._condition.notify_all()

    def _task_for_idempotency(
        self,
        key: str,
        fingerprint: IdempotencyFingerprint,
    ) -> _QueryTask | None:
        entry = self._idempotency.get(key)
        if entry is None:
            return None
        task_id, existing_fingerprint = entry
        if existing_fingerprint != fingerprint:
            raise QueryTaskConflictError(
                "The idempotency key is already bound to another answer request."
            )
        return self._tasks.get(task_id)

    def _prune_terminal_tasks(self) -> list[_QueryTask]:
        removed: list[_QueryTask] = []
        while len(self._tasks) > self._max_retained_tasks:
            candidates = [
                task
                for task in self._tasks.values()
                if task.status in TERMINAL_QUERY_STATUSES
            ]
            if not candidates:
                break
            oldest = min(candidates, key=lambda task: (task.created_at, task.task_id))
            self._tasks.pop(oldest.task_id, None)
            self._idempotency.pop(oldest.idempotency_key, None)
            removed.append(oldest)
        return removed

    def _load_journal(self) -> None:
        payload = self._journal.load()
        if payload is None:
            return
        if payload.get("journal_version") != QUERY_JOURNAL_VERSION:
            raise RuntimeError("Unsupported Desktop query task journal version.")
        interrupted = False
        for item in payload.get("tasks", []):
            task = _task_from_dict(item)
            if task.status in ACTIVE_QUERY_STATUSES:
                task.status = "failed"
                task.stage = "interrupted"
                task.error = {
                    "code": "query_interrupted",
                    "message": "Answer generation was interrupted when MARA Desktop stopped.",
                    "retryable": True,
                }
                task.version += 1
                task.updated_at = _now()
                interrupted = True
            self._tasks[task.task_id] = task
            self._idempotency[task.idempotency_key] = (
                task.task_id,
                _task_fingerprint(task),
            )
        pruned = self._prune_terminal_tasks()
        if interrupted or pruned:
            self._save_journal()

    def _save_journal(self) -> None:
        self._journal.save(
            {
                "journal_version": QUERY_JOURNAL_VERSION,
                "tasks": [_task_to_dict(task) for task in self._tasks.values()],
            }
        )
        self._last_journal_save = time.monotonic()


class QueryTaskManager(_QueryTaskPersistence):
    def __init__(
        self,
        service: QueryService,
        *,
        journal_path: Path | None = None,
        journal: QueryTaskJournal | None = None,
        journal_flush_interval: float = DEFAULT_JOURNAL_FLUSH_INTERVAL,
        max_retained_tasks: int = DEFAULT_MAX_RETAINED_TASKS,
        stream_idle_timeout: float = DEFAULT_STREAM_IDLE_TIMEOUT,
    ) -> None:
        self._service = service
        self._journal = journal or JsonQueryTaskJournal(journal_path)
        self._tasks: dict[str, _QueryTask] = {}
        self._idempotency: dict[str, tuple[str, IdempotencyFingerprint]] = {}
        self._condition = threading.Condition(threading.RLock())
        self._executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="mara-query-task",
        )
        self._journal_flush_interval = max(0.01, journal_flush_interval)
        self._last_journal_save = 0.0
        self._max_retained_tasks = max(1, max_retained_tasks)
        self._stream_idle_timeout = max(0.1, stream_idle_timeout)
        self._closed = False
        self._load_journal()

    def create_task(
        self,
        conversation_id: str,
        prompt: str,
        selected_file_ids: list[str],
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self._condition:
            self._require_open()
            fingerprint = _create_fingerprint(
                conversation_id,
                prompt,
                selected_file_ids,
            )
            existing = self._task_for_idempotency(idempotency_key, fingerprint)
            if existing is not None:
                return _task_snapshot(existing)
            self._service.validate_query(
                conversation_id,
                prompt,
                selected_file_ids,
            )
            task = _QueryTask(
                task_id=str(uuid4()),
                idempotency_key=idempotency_key,
                conversation_id=conversation_id,
                prompt=prompt,
                selected_file_ids=list(selected_file_ids),
            )
            self._persist_new_task(task, fingerprint)
            snapshot = _task_snapshot(task)
            self._executor.submit(self._run_task, task.task_id)
            return snapshot

    def get_task(self, task_id: str) -> dict[str, Any]:
        with self._condition:
            return _task_snapshot(self._require_task(task_id))

    def get_latest_task(self) -> dict[str, Any] | None:
        with self._condition:
            if not self._tasks:
                return None
            latest = max(self._tasks.values(), key=lambda task: task.created_at)
            return _task_snapshot(latest)

    def retry_task(
        self,
        task_id: str,
        *,
        idempotency_key: str,
    ) -> dict[str, Any]:
        with self._condition:
            self._require_open()
            original = self._require_task(task_id)
            fingerprint = _retry_fingerprint(task_id)
            existing = self._task_for_idempotency(idempotency_key, fingerprint)
            if existing is not None:
                return _task_snapshot(existing)
            if original.status not in {"failed", "cancelled"}:
                raise QueryTaskConflictError(
                    "Only failed or cancelled answer tasks can be retried."
                )
            self._service.validate_query(
                original.conversation_id,
                original.prompt,
                original.selected_file_ids,
            )
            retried = _QueryTask(
                task_id=str(uuid4()),
                idempotency_key=idempotency_key,
                retry_of_task_id=original.task_id,
                conversation_id=original.conversation_id,
                prompt=original.prompt,
                selected_file_ids=list(original.selected_file_ids),
                answer=original.answer,
                citations=[dict(item) for item in original.citations],
            )
            self._persist_new_task(retried, fingerprint)
            snapshot = _task_snapshot(retried)
            self._executor.submit(self._run_task, retried.task_id)
            return snapshot

    def cancel_task(self, task_id: str) -> dict[str, Any]:
        with self._condition:
            task = self._require_task(task_id)
            if task.status == "cancelled":
                return _task_snapshot(task)
            if task.status not in ACTIVE_QUERY_STATUSES:
                raise QueryTaskConflictError(
                    "Only queued or running answer tasks can be cancelled."
                )
            task.cancel_requested = True
            task.cancel_event.set()
            task.stage = "cancelling"
            self._touch(task)
            return _task_snapshot(task)

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
            while (
                task.version <= version and task.status not in TERMINAL_QUERY_STATUSES
            ):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self._condition.wait(remaining)
                task = self._require_task(task_id)
            return _task_snapshot(task)

    def close(self) -> None:
        with self._condition:
            if self._closed:
                return
            self._closed = True
            for task in self._tasks.values():
                if task.status in ACTIVE_QUERY_STATUSES:
                    task.cancel_event.set()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _run_task(self, task_id: str) -> None:
        try:
            self._execute_task(task_id)
        except QueryTaskPersistenceError as error:
            self._tasks[task_id].cancel_event.set()
            self._record_persistence_failure(task_id, error)

    def _execute_task(self, task_id: str) -> None:
        with self._condition:
            task = self._require_task(task_id)
            if task.cancel_requested:
                self._finish_task(task, "cancelled")
                return
            task.status = "running"
            task.stage = "preparing"
            self._touch(task)
            arguments = (
                task.conversation_id,
                task.prompt,
                list(task.selected_file_ids),
            )
            cancel_event = task.cancel_event
        outcome = QueryStreamRunner(
            self._service,
            idle_timeout=self._stream_idle_timeout,
        ).run(
            task_id,
            arguments,
            cancel_event,
            lambda update: self._apply_stream_update(task_id, update),
        )
        with self._condition:
            task = self._require_task(task_id)
            if task.cancel_requested or outcome.status == "cancelled":
                self._finish_task(task, "cancelled")
            elif outcome.status == "success":
                task.status = "success"
                task.stage = "completed"
                task.error = None
                self._touch(task)
            else:
                self._finish_task(task, outcome.status)

    def _apply_stream_update(
        self,
        task_id: str,
        update: dict[str, Any],
    ) -> bool:
        with self._condition:
            task = self._require_task(task_id)
            if task.status != "running":
                return False
            _apply_query_update(task, update)
            self._touch(task, force_persist=False)
            return True

    def _finish_task(self, task: _QueryTask, outcome: str) -> None:
        task.status = "cancelled" if outcome == "cancelled" else "failed"
        task.stage = "completed"
        task.error = _query_outcome_error(outcome)
        self._touch(task)

    def _require_task(self, task_id: str) -> _QueryTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise QueryTaskNotFoundError(task_id)
        return task

    def _require_open(self) -> None:
        if self._closed:
            raise QueryTaskConflictError("The query task manager is stopping.")


def _task_snapshot(task: _QueryTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "retry_of_task_id": task.retry_of_task_id,
        "conversation_id": task.conversation_id,
        "prompt": task.prompt,
        "selected_file_ids": list(task.selected_file_ids),
        "qa_scope": (
            "document" if len(task.selected_file_ids) == 1 else "multi_document"
        ),
        "status": task.status,
        "stage": task.stage,
        "answer": task.answer,
        "citations": [dict(item) for item in task.citations],
        "error": dict(task.error) if task.error else None,
        "retryable": task.status in {"failed", "cancelled"},
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "version": task.version,
    }


def _apply_query_update(task: _QueryTask, update: dict[str, Any]) -> None:
    task.stage = str(update.get("stage") or "generating")
    answer = str(update.get("answer") or "")
    final = bool(update.get("final", False))
    if answer or not task.answer:
        task.answer = answer
    citations = [
        dict(item) for item in update.get("citations", []) if isinstance(item, dict)
    ]
    if citations or not task.citations or final:
        task.citations = citations


def _query_outcome_error(outcome: str) -> dict[str, Any]:
    if outcome == "cancelled":
        return {
            "code": "query_cancelled",
            "message": "Answer generation was cancelled.",
            "retryable": True,
        }
    if outcome == "timeout":
        return {
            "code": "query_timeout",
            "message": "MARA did not receive answer progress before the time limit.",
            "retryable": True,
        }
    return {
        "code": "query_failed",
        "message": "MARA could not complete the answer.",
        "retryable": True,
    }


def _task_to_dict(task: _QueryTask) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "idempotency_key": task.idempotency_key,
        "retry_of_task_id": task.retry_of_task_id,
        "conversation_id": task.conversation_id,
        "prompt": task.prompt,
        "selected_file_ids": list(task.selected_file_ids),
        "status": task.status,
        "stage": task.stage,
        "answer": task.answer,
        "citations": [dict(item) for item in task.citations],
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "version": task.version,
        "cancel_requested": task.cancel_requested,
        "error": task.error,
    }


def _task_from_dict(item: dict[str, Any]) -> _QueryTask:
    return _QueryTask(
        task_id=str(item["task_id"]),
        idempotency_key=str(item["idempotency_key"]),
        retry_of_task_id=(
            str(item["retry_of_task_id"]) if item.get("retry_of_task_id") else None
        ),
        conversation_id=str(item["conversation_id"]),
        prompt=str(item["prompt"]),
        selected_file_ids=[str(value) for value in item.get("selected_file_ids", [])],
        status=str(item.get("status", "failed")),
        stage=str(item.get("stage", "interrupted")),
        answer=str(item.get("answer", "")),
        citations=[
            dict(value)
            for value in item.get("citations", [])
            if isinstance(value, dict)
        ],
        created_at=str(item.get("created_at", _now())),
        updated_at=str(item.get("updated_at", _now())),
        version=int(item.get("version", 1)),
        cancel_requested=bool(item.get("cancel_requested", False)),
        error=item.get("error"),
    )


def _create_fingerprint(
    conversation_id: str,
    prompt: str,
    selected_file_ids: list[str],
) -> IdempotencyFingerprint:
    return ("create", conversation_id, prompt, *selected_file_ids)


def _retry_fingerprint(task_id: str) -> IdempotencyFingerprint:
    return ("retry", task_id)


def _task_fingerprint(task: _QueryTask) -> IdempotencyFingerprint:
    if task.retry_of_task_id:
        return _retry_fingerprint(task.retry_of_task_id)
    return _create_fingerprint(
        task.conversation_id,
        task.prompt,
        task.selected_file_ids,
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
