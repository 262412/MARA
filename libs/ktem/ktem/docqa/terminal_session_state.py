from __future__ import annotations

from typing import Any

from ktem_contracts import terminal_session_state as _session_contract

MAX_TERMINAL_SESSION_COMMITS = _session_contract.MAX_TERMINAL_SESSION_COMMITS
TERMINAL_SESSION_STATE_CONTRACT = _session_contract.TERMINAL_SESSION_STATE_CONTRACT
TERMINAL_SESSION_STATE_KEY = _session_contract.TERMINAL_SESSION_STATE_KEY
terminal_semantic_commit_for_message = (
    _session_contract.terminal_semantic_commit_for_message
)
with_terminal_semantic_commit = _session_contract.with_terminal_semantic_commit

__all__ = [
    "MAX_TERMINAL_SESSION_COMMITS",
    "TERMINAL_SESSION_STATE_CONTRACT",
    "TERMINAL_SESSION_STATE_KEY",
    "state_with_stream_terminal_commit",
    "terminal_semantic_commit_for_message",
    "with_terminal_semantic_commit",
]


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
