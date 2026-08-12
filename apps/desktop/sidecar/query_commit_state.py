from __future__ import annotations

from copy import deepcopy
from typing import Any

DESKTOP_QUERY_COMMIT_STATE_KEY = "_mara_desktop_query_commits"
DESKTOP_QUERY_COMMIT_STATE_VERSION = 1
MAX_DESKTOP_QUERY_COMMIT_MARKERS = 128


def state_with_query_commit_marker(session: Any, turn_id: str) -> dict[str, Any]:
    state = deepcopy(getattr(session, "state", {}) or {})
    if not turn_id:
        return state
    raw_commit_state = state.get(DESKTOP_QUERY_COMMIT_STATE_KEY)
    commit_state = (
        deepcopy(raw_commit_state) if isinstance(raw_commit_state, dict) else {}
    )
    raw_turns = commit_state.get("turns")
    turns = deepcopy(raw_turns) if isinstance(raw_turns, dict) else {}
    turns[turn_id] = {
        "message_index": len(list(getattr(session, "messages", []) or []))
    }
    while len(turns) > MAX_DESKTOP_QUERY_COMMIT_MARKERS:
        turns.pop(next(iter(turns)))
    state[DESKTOP_QUERY_COMMIT_STATE_KEY] = {
        "version": DESKTOP_QUERY_COMMIT_STATE_VERSION,
        "turns": turns,
    }
    return state


def recover_committed_answer(
    runtime: Any,
    conversation_id: str,
    turn_id: str,
) -> dict[str, object] | None:
    if not turn_id:
        return None
    session = runtime.load_session(conversation_id)
    if session is None:
        return None
    marker = _query_commit_marker(session.state, turn_id)
    if marker is None:
        return None
    message_index = marker.get("message_index")
    messages = list(session.messages or [])
    if not isinstance(message_index, int) or not 0 <= message_index < len(messages):
        return None
    message = messages[message_index]
    if not isinstance(message, (list, tuple)) or len(message) < 2:
        return None
    return {"answer": str(message[1] or ""), "citations": []}


def _query_commit_marker(state: Any, turn_id: str) -> dict[str, Any] | None:
    if not isinstance(state, dict):
        return None
    commit_state = state.get(DESKTOP_QUERY_COMMIT_STATE_KEY)
    if not isinstance(commit_state, dict):
        return None
    if commit_state.get("version") != DESKTOP_QUERY_COMMIT_STATE_VERSION:
        return None
    turns = commit_state.get("turns")
    if not isinstance(turns, dict):
        return None
    marker = turns.get(turn_id)
    return dict(marker) if isinstance(marker, dict) else None
