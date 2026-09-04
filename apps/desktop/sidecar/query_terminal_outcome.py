from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem_contracts import terminal_session_state as _session_contract
from ktem_contracts.terminal_semantic_commit import (
    build_operational_terminal_commit,
    terminal_commit_outcome,
    terminal_commit_projection_present,
)

from .query_readiness import QueryFailureContract, classify_query_failure
from .query_task_state import QueryTaskState

terminal_semantic_commit_for_message = (
    _session_contract.terminal_semantic_commit_for_message
)


def response_terminal_fields(response: Any) -> dict[str, Any]:
    commit = getattr(response, "engine_terminal_commit", None) or getattr(
        response,
        "terminal_semantic_commit",
        None,
    )
    if not isinstance(commit, dict) or not terminal_commit_projection_present(commit):
        return {}
    return {
        "terminal_semantic_commit": deepcopy(commit),
        "terminal_outcome": terminal_commit_outcome(commit),
        "terminal_outcome_reason": str(commit.get("outcome_reason") or ""),
    }


def apply_terminal_update(task: QueryTaskState, update: dict[str, Any]) -> None:
    commit = update.get("terminal_semantic_commit")
    if not isinstance(commit, dict) or not terminal_commit_projection_present(commit):
        return
    task.terminal_semantic_commit = deepcopy(commit)
    task.terminal_outcome = terminal_commit_outcome(commit)
    task.terminal_outcome_reason = str(commit.get("outcome_reason") or "")


def apply_operational_terminal_outcome(
    task: QueryTaskState,
    outcome: str,
    reason: str,
) -> None:
    commit = build_operational_terminal_commit(
        outcome=outcome,
        reason=reason,
        presentation_answer=task.answer,
    )
    task.terminal_semantic_commit = commit
    task.terminal_outcome = terminal_commit_outcome(commit)
    task.terminal_outcome_reason = reason


def terminal_outcome_for_task_status(outcome: str) -> str:
    if outcome == "cancelled":
        return "cancelled"
    if outcome == "timeout":
        return "timeout"
    return "execution_failed"


def query_outcome_error(
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
