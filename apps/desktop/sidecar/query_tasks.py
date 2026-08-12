from __future__ import annotations

import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from uuid import uuid4

from .query_readiness import QueryFailureContract, classify_query_failure
from .query_stream_runner import QueryService, QueryStreamRunner
from .query_task_journal import (
    JsonQueryTaskJournal,
    QueryTaskJournal,
    QueryTaskPersistenceError,
)
from .query_task_recovery import (
    ACTIVE_QUERY_STATUSES,
    QUERY_JOURNAL_VERSION,
    load_recoverable_tasks,
    restore_committed_turn,
)
from .query_task_state import QueryTaskState as _QueryTask
from .query_task_state import now as _now
from .query_task_state import task_snapshot as _task_snapshot
from .query_task_state import task_to_dict as _task_to_dict

TERMINAL_QUERY_STATUSES = {"success", "failed", "cancelled"}
DEFAULT_JOURNAL_FLUSH_INTERVAL = 0.25
DEFAULT_MAX_RETAINED_TASKS = 100
DEFAULT_STREAM_IDLE_TIMEOUT = 300.0
LOGGER = logging.getLogger("mara.desktop.query_tasks")
IdempotencyFingerprint = tuple[str, ...]


class QueryTaskNotFoundError(LookupError):
    pass


class QueryTaskConflictError(RuntimeError):
    pass


class _QueryTaskPersistence:
    _service: QueryService
    _journal: QueryTaskJournal
    _tasks: dict[str, _QueryTask]
    _idempotency: dict[str, tuple[str, IdempotencyFingerprint]]
    _condition: threading.Condition
    _journal_flush_interval: float
    _last_journal_save: float
    _max_retained_tasks: int
    _persistence_issue: QueryTaskPersistenceError | None

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
            "Query task persistence failed task_id=%s error_code=%s operation=%s "
            "error_type=%s errno=%s winerror=%s retried=%s retry_count=%s",
            task_id,
            error.code,
            error.operation,
            error.error_type,
            error.error_number,
            error.winerror,
            error.retry_count > 0,
            error.retry_count,
        )
        with self._condition:
            self._persistence_issue = error
            task = self._tasks[task_id]
            task.status = "failed"
            task.stage = "storage_error"
            task.error = {
                "code": error.code,
                "message": error.message,
                "retryable": error.retryable,
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
            oldest = min(candidates, key=lambda task: task.created_at)
            self._tasks.pop(oldest.task_id, None)
            self._idempotency.pop(oldest.idempotency_key, None)
            removed.append(oldest)
        return removed

    def _load_journal(self) -> None:
        loaded_tasks, changed = load_recoverable_tasks(self._journal, self._service)
        for task in loaded_tasks:
            self._tasks[task.task_id] = task
            self._idempotency[task.idempotency_key] = (
                task.task_id,
                _task_fingerprint(task),
            )
        pruned = self._prune_terminal_tasks()
        if changed or pruned:
            self._save_journal()

    def _save_journal(self) -> None:
        self._journal.save(
            {
                "journal_version": QUERY_JOURNAL_VERSION,
                "tasks": [_task_to_dict(task) for task in self._tasks.values()],
            }
        )
        self._last_journal_save = time.monotonic()

    def persistence_readiness(self) -> dict[str, Any]:
        with self._condition:
            error = self._persistence_issue
            if error is None or error.code != "query_state_corrupt":
                try:
                    self._probe_journal()
                    self._persistence_issue = None
                    error = None
                except QueryTaskPersistenceError as current_error:
                    self._persistence_issue = current_error
                    error = current_error
            if error is None:
                return {
                    "query_persistence_ready": True,
                    "query_persistence_issue_code": None,
                    "query_persistence_message": "Answer state storage is ready.",
                    "query_persistence_action": "none",
                    "query_persistence_retryable": False,
                }
            return {
                "query_persistence_ready": False,
                "query_persistence_issue_code": error.code,
                "query_persistence_message": error.message,
                "query_persistence_action": _persistence_action(error.code),
                "query_persistence_retryable": error.retryable,
            }

    def _probe_journal(self) -> None:
        probe = getattr(self._journal, "probe", None)
        if callable(probe):
            probe()

    def _assert_persistence_ready(self) -> None:
        if (
            self._persistence_issue is not None
            and self._persistence_issue.code == "query_state_corrupt"
        ):
            raise self._persistence_issue
        try:
            self._probe_journal()
        except QueryTaskPersistenceError as error:
            self._persistence_issue = error
            raise
        self._persistence_issue = None


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
        self._persistence_issue: QueryTaskPersistenceError | None = None
        try:
            self._load_journal()
        except QueryTaskPersistenceError as error:
            self._persistence_issue = error

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
            self._assert_persistence_ready()
            route = (
                self._service.validate_query(
                    conversation_id,
                    prompt,
                    selected_file_ids,
                )
                or {}
            )
            task_id = str(uuid4())
            task = _QueryTask(
                task_id=task_id,
                idempotency_key=idempotency_key,
                conversation_id=conversation_id,
                prompt=prompt,
                selected_file_ids=list(selected_file_ids),
                turn_id=task_id,
                route_provider=str(route.get("route_provider") or ""),
                route_model=str(route.get("route_model") or ""),
                settings_revision=str(route.get("settings_revision") or ""),
                sidecar_pid=int(route.get("sidecar_pid") or os.getpid()),
                route_fingerprint=str(route.get("route_fingerprint") or ""),
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
            self._assert_persistence_ready()
            if restore_committed_turn(self._service, original):
                try:
                    self._save_journal()
                except QueryTaskPersistenceError as error:
                    self._record_persistence_failure(original.task_id, error)
                    raise
                self._idempotency[idempotency_key] = (original.task_id, fingerprint)
                self._condition.notify_all()
                return _task_snapshot(original)
            route = (
                self._service.validate_query(
                    original.conversation_id,
                    original.prompt,
                    original.selected_file_ids,
                )
                or {}
            )
            retried = _QueryTask(
                task_id=str(uuid4()),
                idempotency_key=idempotency_key,
                retry_of_task_id=original.task_id,
                conversation_id=original.conversation_id,
                prompt=original.prompt,
                selected_file_ids=list(original.selected_file_ids),
                turn_id=original.turn_id,
                route_provider=str(route.get("route_provider") or ""),
                route_model=str(route.get("route_model") or ""),
                settings_revision=str(route.get("settings_revision") or ""),
                sidecar_pid=int(route.get("sidecar_pid") or os.getpid()),
                route_fingerprint=str(route.get("route_fingerprint") or ""),
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
            try:
                self._touch(task)
            except QueryTaskPersistenceError as error:
                self._record_persistence_failure(task_id, error)
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
            task.turn_id,
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
                try:
                    self._touch(task)
                except QueryTaskPersistenceError as error:
                    self._record_persistence_failure(task_id, error)
            else:
                self._finish_task(task, outcome.status, error=outcome.error)

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

    def _finish_task(
        self,
        task: _QueryTask,
        outcome: str,
        *,
        error: QueryFailureContract | Exception | None = None,
    ) -> None:
        task.status = "cancelled" if outcome == "cancelled" else "failed"
        task.stage = "completed"
        task.error = _query_outcome_error(outcome, error)
        LOGGER.error(
            "Query task failed task_id=%s error_code=%s stage=%s error_type=%s",
            task.task_id,
            task.error["code"],
            task.stage,
            type(error).__name__ if error is not None else "QueryTaskOutcome",
        )
        self._touch(task)

    def _require_task(self, task_id: str) -> _QueryTask:
        task = self._tasks.get(task_id)
        if task is None:
            raise QueryTaskNotFoundError(task_id)
        return task

    def _require_open(self) -> None:
        if self._closed:
            raise QueryTaskConflictError("The query task manager is stopping.")


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


def _query_outcome_error(
    outcome: str,
    error: QueryFailureContract | Exception | None = None,
) -> dict[str, Any]:
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
    if isinstance(error, QueryFailureContract):
        return error.as_dict()
    return classify_query_failure(
        error if error is not None else "query runtime failed"
    ).as_dict()


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


def _persistence_action(code: str) -> str:
    return {
        "query_storage_full": "free_storage",
        "query_state_locked": "close_extra_instance",
        "query_state_permission_denied": "check_data_permissions",
        "query_state_read_only": "check_data_permissions",
        "query_state_corrupt": "repair_state",
    }.get(code, "retry")
