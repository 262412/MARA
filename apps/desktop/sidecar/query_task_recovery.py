from __future__ import annotations

import logging
from typing import Any

from .query_task_journal import QueryTaskJournal, QueryTaskPersistenceError
from .query_task_state import QueryTaskState
from .query_task_state import now as _now
from .query_task_state import task_from_dict
from .query_terminal_outcome import terminal_commit_projection_present

QUERY_JOURNAL_VERSION = 3
SUPPORTED_QUERY_JOURNAL_VERSIONS = {1, 2, QUERY_JOURNAL_VERSION}
ACTIVE_QUERY_STATUSES = {"queued", "running"}
LOGGER = logging.getLogger("mara.desktop.query_tasks")


def persistence_action(code: str) -> str:
    return {
        "query_storage_full": "free_storage",
        "query_state_locked": "close_extra_instance",
        "query_state_replace_blocked": "retry",
        "query_state_permission_denied": "check_data_permissions",
        "query_state_read_only": "check_data_permissions",
        "query_state_corrupt": "repair_state",
    }.get(code, "retry")


def load_recoverable_tasks(
    journal: QueryTaskJournal,
    service: Any,
) -> tuple[list[QueryTaskState], bool]:
    payload = journal.load()
    if payload is None:
        return [], False
    journal_version = payload.get("journal_version")
    if journal_version not in SUPPORTED_QUERY_JOURNAL_VERSIONS:
        raise QueryTaskPersistenceError(
            "query_state_corrupt",
            "MARA answer state uses an unsupported format and was left unchanged.",
            retryable=False,
            operation="load",
            error_type="UnsupportedJournalVersion",
        )
    raw_tasks = payload.get("tasks", [])
    if not isinstance(raw_tasks, list):
        raise QueryTaskPersistenceError(
            "query_state_corrupt",
            "MARA answer state is damaged and was left unchanged for recovery.",
            retryable=False,
            operation="load",
            error_type="InvalidJournalShape",
        )
    try:
        tasks = [task_from_dict(item) for item in raw_tasks]
    except (KeyError, TypeError, ValueError) as error:
        raise QueryTaskPersistenceError(
            "query_state_corrupt",
            "MARA answer state is damaged and was left unchanged for recovery.",
            retryable=False,
            operation="load",
            error_type=type(error).__name__,
        ) from None
    changed = journal_version != QUERY_JOURNAL_VERSION
    successful_turn_ids = {task.turn_id for task in tasks if task.status == "success"}
    for task in tasks:
        recovered = task.turn_id not in successful_turn_ids and restore_committed_turn(
            service,
            task,
        )
        if recovered:
            successful_turn_ids.add(task.turn_id)
            changed = True
        elif task.status in ACTIVE_QUERY_STATUSES:
            _mark_interrupted(task)
            changed = True
    return tasks, changed


def restore_committed_turn(service: Any, task: QueryTaskState) -> bool:
    recover = getattr(service, "recover_committed_turn", None)
    if not callable(recover) or not task.turn_id:
        return False
    try:
        committed = recover(task.conversation_id, task.turn_id)
    except Exception as error:
        LOGGER.error(
            "Query task recovery check failed task_id=%s stage=session_recovery "
            "error_type=%s",
            task.task_id,
            type(error).__name__,
        )
        return False
    if not isinstance(committed, dict):
        return False
    task.answer = str(committed.get("answer") or "")
    task.answer_saved = True
    task.citations = [
        dict(item) for item in committed.get("citations", []) if isinstance(item, dict)
    ]
    terminal_commit = committed.get("terminal_semantic_commit")
    task.terminal_semantic_commit = (
        dict(terminal_commit)
        if isinstance(terminal_commit, dict)
        and terminal_commit_projection_present(terminal_commit)
        else {}
    )
    task.terminal_outcome = str(
        task.terminal_semantic_commit.get("outcome")
        or committed.get("terminal_outcome")
        or ""
    )
    task.terminal_outcome_reason = str(
        task.terminal_semantic_commit.get("outcome_reason")
        or committed.get("terminal_outcome_reason")
        or ""
    )
    task.status = "success"
    task.stage = "completed"
    task.error = None
    task.cancel_requested = False
    task.version += 1
    task.updated_at = _now()
    return True


def _mark_interrupted(task: QueryTaskState) -> None:
    task.status = "failed"
    task.stage = "interrupted"
    task.error = {
        "code": "query_interrupted",
        "message": "Answer generation was interrupted when MARA Desktop stopped. The last saved partial answer is preserved.",
        "retryable": True,
    }
    task.version += 1
    task.updated_at = _now()
