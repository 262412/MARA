"""Generation store for background/streaming chat updates per page."""

from __future__ import annotations

import threading
import time
import uuid
from copy import deepcopy
from typing import Any, Optional

CACHE_LOCK = threading.Lock()

# request_key -> payload
GENERATION_CACHE: dict[str, dict[str, Any]] = {}
# session_key -> {page_key: request_key}
ACTIVE_REQUESTS: dict[str, dict[str, str]] = {}
# session_key -> page_key (current view)
CURRENT_VIEW: dict[str, str] = {}


def make_request_key(session_key: str, page_key: str) -> str:
    return f"{session_key}:{page_key}:{uuid.uuid4().hex}"


def make_page_key(file_id: str | None, page_number: int | None) -> str:
    safe_page = max(1, int(page_number or 1))
    return f"{file_id or 'default'}_{safe_page}"


def set_current_view(session_key: str, page_key: str) -> None:
    if not session_key:
        return
    with CACHE_LOCK:
        CURRENT_VIEW[session_key] = page_key


def get_current_view(session_key: str) -> Optional[str]:
    if not session_key:
        return None
    with CACHE_LOCK:
        return CURRENT_VIEW.get(session_key)


def init_cache_entry(
    *,
    request_key: str,
    session_key: str,
    page_key: str,
    file_id: str,
    page_number: int,
    last_question: str,
    preserved_history: list,
) -> None:
    now = time.time()
    payload = {
        "request_key": request_key,
        "session_key": session_key,
        "page_key": page_key,
        "file_id": file_id,
        "page_number": int(page_number or 1),
        "last_question": last_question,
        "preserved_history": deepcopy(preserved_history) if preserved_history else [],
        "answer_text": "",
        "answer_html": "",
        "mindmap_html": "",
        "plot": None,
        "chat_history": deepcopy(preserved_history) if preserved_history else [],
        "done": False,
        "error": None,
        "version": 0,
        "last_update_ts": now,
        "persisted": False,
    }
    with CACHE_LOCK:
        GENERATION_CACHE[request_key] = payload
        ACTIVE_REQUESTS.setdefault(session_key, {})[page_key] = request_key


def _touch(entry: dict[str, Any]) -> None:
    entry["version"] = int(entry.get("version", 0)) + 1
    entry["last_update_ts"] = time.time()


def update_answer(
    request_key: str,
    *,
    answer_text: str,
    answer_html: str,
    chat_history: list,
) -> None:
    with CACHE_LOCK:
        entry = GENERATION_CACHE.get(request_key)
        if not entry:
            return
        entry["answer_text"] = answer_text or ""
        entry["answer_html"] = answer_html or ""
        entry["chat_history"] = deepcopy(chat_history) if chat_history else []
        _touch(entry)


def update_mindmap(request_key: str, mindmap_html: str) -> None:
    with CACHE_LOCK:
        entry = GENERATION_CACHE.get(request_key)
        if not entry:
            return
        entry["mindmap_html"] = mindmap_html or ""
        _touch(entry)


def update_plot(request_key: str, plot: Any) -> None:
    with CACHE_LOCK:
        entry = GENERATION_CACHE.get(request_key)
        if not entry:
            return
        entry["plot"] = plot
        _touch(entry)


def update_reasoning_state(request_key: str, reasoning_state: dict | None) -> None:
    with CACHE_LOCK:
        entry = GENERATION_CACHE.get(request_key)
        if not entry:
            return
        entry["reasoning_state"] = (
            deepcopy(reasoning_state) if reasoning_state else None
        )
        _touch(entry)


def mark_done(request_key: str) -> None:
    with CACHE_LOCK:
        entry = GENERATION_CACHE.get(request_key)
        if not entry:
            return
        entry["done"] = True
        _touch(entry)


def mark_error(request_key: str, error: str) -> None:
    with CACHE_LOCK:
        entry = GENERATION_CACHE.get(request_key)
        if not entry:
            return
        entry["error"] = error
        entry["done"] = True
        _touch(entry)


def mark_persisted(request_key: str) -> None:
    with CACHE_LOCK:
        entry = GENERATION_CACHE.get(request_key)
        if not entry:
            return
        entry["persisted"] = True


def get_snapshot(request_key: str) -> Optional[dict[str, Any]]:
    with CACHE_LOCK:
        entry = GENERATION_CACHE.get(request_key)
        return deepcopy(entry) if entry else None


def get_snapshot_by_page(session_key: str, page_key: str) -> Optional[dict[str, Any]]:
    if not session_key:
        return None
    with CACHE_LOCK:
        request_key = ACTIVE_REQUESTS.get(session_key, {}).get(page_key)
        if not request_key:
            return None
        entry = GENERATION_CACHE.get(request_key)
        return deepcopy(entry) if entry else None


def has_in_progress(session_key: str, page_key: str) -> bool:
    snapshot = get_snapshot_by_page(session_key, page_key)
    if not snapshot:
        return False
    return not snapshot.get("done", False)


def cleanup_expired(ttl_seconds: int = 900) -> None:
    cutoff = time.time() - ttl_seconds
    with CACHE_LOCK:
        stale_keys = [
            key
            for key, entry in GENERATION_CACHE.items()
            if entry.get("done") and entry.get("last_update_ts", 0) < cutoff
        ]
        for key in stale_keys:
            entry = GENERATION_CACHE.pop(key, None)
            if not entry:
                continue
            session_key = entry.get("session_key")
            page_key = entry.get("page_key")
            if session_key and page_key:
                active = ACTIVE_REQUESTS.get(session_key, {})
                if active.get(page_key) == key:
                    active.pop(page_key, None)
