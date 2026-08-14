from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.execution_contracts import ABSTAIN_MESSAGE
from ktem.docqa.terminal_semantic_commit import (
    build_terminal_semantic_commit,
    terminal_commit_projection_present,
)

from .query_readiness import QueryFailureContract, classify_query_failure
from .query_task_state import QueryTaskState


def response_terminal_commit(response: Any) -> dict[str, Any]:
    commit = getattr(response, "engine_terminal_commit", None) or getattr(
        response,
        "terminal_semantic_commit",
        None,
    )
    if not isinstance(commit, dict) or not terminal_commit_projection_present(commit):
        return {}
    return dict(commit)


def apply_terminal_update(task: QueryTaskState, update: dict[str, Any]) -> None:
    commit = update.get("terminal_semantic_commit")
    if not isinstance(commit, dict) or not terminal_commit_projection_present(commit):
        return
    task.terminal_semantic_commit = deepcopy(commit)
    task.terminal_outcome = str(commit.get("outcome") or "")
    task.terminal_outcome_reason = str(commit.get("outcome_reason") or "")


def apply_operational_terminal_outcome(
    task: QueryTaskState,
    outcome: str,
    reason: str,
) -> None:
    action = "cancel" if outcome == "cancelled" else "error"
    commit = build_terminal_semantic_commit(
        ABSTAIN_MESSAGE,
        {"status": outcome, "action": action, "reason": reason},
        {"status": outcome, "action": action, "reason": reason},
        {"items": [], "metadata": {}},
        outcome=outcome,
        outcome_reason=reason,
        presentation_answer=task.answer,
    ).as_dict()
    task.terminal_semantic_commit = commit
    task.terminal_outcome = outcome
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
