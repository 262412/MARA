from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .query_readiness import QueryFailureContract, classify_query_failure
from .query_task_state import QueryTaskState

TERMINAL_COMMIT_CONTRACTS = {
    "terminal_semantic_commit.v2",
    "terminal_semantic_commit.v3",
}
TERMINAL_SESSION_STATE_KEY = "_mara_terminal_semantic_commits"
TERMINAL_SESSION_STATE_CONTRACT = "terminal_semantic_commit_session.v1"


def response_terminal_fields(response: Any) -> dict[str, Any]:
    commit = getattr(response, "engine_terminal_commit", None) or getattr(
        response,
        "terminal_semantic_commit",
        None,
    )
    if not isinstance(commit, dict) or not terminal_commit_projection_present(commit):
        return {}
    return {
        "terminal_semantic_commit": dict(commit),
        "terminal_outcome": str(commit.get("outcome") or ""),
        "terminal_outcome_reason": str(commit.get("outcome_reason") or ""),
    }


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
    decision = {"status": outcome, "action": action, "reason": reason}
    commit = _with_projection_hash(
        {
            "contract_id": "terminal_semantic_commit.v3",
            "semantic_answer": "unanswerable",
            "presentation_answer": task.answer,
            "outcome": outcome,
            "outcome_reason": reason,
            "answer_status": "abstained",
            "verify_decision": dict(decision),
            "guardrail_decision": dict(decision),
            "authoritative_evidence": [],
            "citations": [],
            "state_version": 3,
        }
    )
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


def terminal_commit_projection_present(commit: Any) -> bool:
    if (
        not isinstance(commit, dict)
        or commit.get("contract_id") not in TERMINAL_COMMIT_CONTRACTS
    ):
        return False
    expected = dict(commit)
    projection_hash = str(expected.pop("projection_hash", "") or "")
    return bool(projection_hash and projection_hash == _projection_hash(expected))


def terminal_semantic_commit_for_message(
    state: Any,
    message_index: int,
) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    store = state.get(TERMINAL_SESSION_STATE_KEY)
    if (
        not isinstance(store, dict)
        or store.get("contract_id") != TERMINAL_SESSION_STATE_CONTRACT
    ):
        return {}
    commits = store.get("commits")
    commit = commits.get(str(message_index)) if isinstance(commits, dict) else None
    if not isinstance(commit, dict) or not terminal_commit_projection_present(commit):
        return {}
    return deepcopy(commit)


def _with_projection_hash(payload: dict[str, Any]) -> dict[str, Any]:
    commit = deepcopy(payload)
    commit["projection_hash"] = _projection_hash(commit)
    return commit


def _projection_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
