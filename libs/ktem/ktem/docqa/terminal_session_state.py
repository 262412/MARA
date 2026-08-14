from __future__ import annotations

from copy import deepcopy
from typing import Any

from .terminal_semantic_commit import terminal_commit_projection_present

TERMINAL_SESSION_STATE_KEY = "_mara_terminal_semantic_commits"
TERMINAL_SESSION_STATE_CONTRACT = "terminal_semantic_commit_session.v1"
MAX_TERMINAL_SESSION_COMMITS = 128


def state_with_stream_terminal_commit(
    stream_result: Any,
    message_index: int,
) -> dict[str, Any]:
    execution = stream_result.capture.execution or {}
    commit = execution.get("engine_terminal_commit") or execution.get(
        "terminal_semantic_commit"
    )
    return with_terminal_semantic_commit(
        stream_result.state,
        message_index=message_index,
        commit=commit,
    )


def with_terminal_semantic_commit(
    state: dict[str, Any],
    *,
    message_index: int,
    commit: Any,
) -> dict[str, Any]:
    output = deepcopy(state)
    if message_index < 0 or not terminal_commit_projection_present(commit):
        return output
    raw_store = output.get(TERMINAL_SESSION_STATE_KEY)
    store = deepcopy(raw_store) if isinstance(raw_store, dict) else {}
    raw_commits = store.get("commits")
    commits = deepcopy(raw_commits) if isinstance(raw_commits, dict) else {}
    commits[str(message_index)] = deepcopy(commit)
    while len(commits) > MAX_TERMINAL_SESSION_COMMITS:
        commits.pop(next(iter(commits)))
    output[TERMINAL_SESSION_STATE_KEY] = {
        "contract_id": TERMINAL_SESSION_STATE_CONTRACT,
        "commits": commits,
    }
    return output


def terminal_semantic_commit_for_message(
    state: Any,
    message_index: int,
) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {}
    store = state.get(TERMINAL_SESSION_STATE_KEY)
    if not isinstance(store, dict) or store.get("contract_id") != (
        TERMINAL_SESSION_STATE_CONTRACT
    ):
        return {}
    commits = store.get("commits")
    commit = commits.get(str(message_index)) if isinstance(commits, dict) else None
    if not isinstance(commit, dict) or not terminal_commit_projection_present(commit):
        return {}
    return deepcopy(commit)
