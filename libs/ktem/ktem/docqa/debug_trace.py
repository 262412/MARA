from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import traceback
from itertools import count
from typing import Any

_DEBUG_VALUES = {"1", "true", "yes", "on"}
_EVENT_COUNTER = count(1)


def enabled() -> bool:
    return str(os.environ.get("MARA_CHAT_STREAM_DEBUG", "")).lower() in _DEBUG_VALUES


def stack_enabled() -> bool:
    value = os.environ.get("MARA_CHAT_STREAM_DEBUG_STACK")
    if value is None:
        return True
    return str(value).lower() in _DEBUG_VALUES


def summarize_text(value: Any, *, limit: int = 220) -> dict[str, Any]:
    text = "" if value is None else str(value)
    compact = re.sub(r"\s+", " ", text).strip()
    digest = hashlib.sha1(text.encode("utf-8", errors="replace")).hexdigest()[:12]
    summary = {
        "len": len(text),
        "sha1": digest,
        "head": compact[:limit],
    }
    if len(compact) > limit:
        summary["tail"] = compact[-limit:]
    return summary


def summarize_html(value: Any) -> dict[str, Any]:
    text = "" if value is None else str(value)
    stripped = re.sub(r"<[^>]+>", " ", text)
    return {
        "html": summarize_text(text),
        "text": summarize_text(stripped),
    }


def summarize_messages(messages: Any) -> dict[str, Any]:
    if not isinstance(messages, list):
        return {"type": type(messages).__name__, "value": summarize_text(messages)}
    last = messages[-1] if messages else None
    last_question = ""
    last_answer = ""
    if isinstance(last, (list, tuple)) and len(last) >= 2:
        last_question = "" if last[0] is None else str(last[0])
        last_answer = "" if last[1] is None else str(last[1])
    elif isinstance(last, dict):
        last_question = str(last.get("role") or "")
        last_answer = str(last.get("content") or "")
    return {
        "count": len(messages),
        "last_question": summarize_text(last_question),
        "last_answer": summarize_text(last_answer),
    }


def log_event(
    event: str,
    *,
    include_stack: bool = False,
    **fields: Any,
) -> None:
    if not enabled():
        return

    payload = {
        "seq": next(_EVENT_COUNTER),
        "event": event,
        "time": round(time.time(), 6),
        "thread": threading.current_thread().name,
        **fields,
    }
    if include_stack and stack_enabled():
        payload["stack"] = [
            frame.strip() for frame in traceback.format_stack(limit=10)[:-1]
        ]
    print(
        "[MARA_CHAT_STREAM_DEBUG] "
        + json.dumps(payload, ensure_ascii=False, default=str),
        flush=True,
    )


def log_generation_update(
    event: str,
    *,
    request_key: str,
    previous_answer_text: Any = "",
    next_answer_text: Any = "",
    previous_answer_html: Any = "",
    next_answer_html: Any = "",
    previous_chat_history: Any = None,
    next_chat_history: Any = None,
    version: Any = None,
    include_stack: bool = True,
) -> None:
    log_event(
        event,
        request_key=request_key,
        version=version,
        previous_answer_text=summarize_text(previous_answer_text),
        next_answer_text=summarize_text(next_answer_text),
        previous_answer_html=summarize_html(previous_answer_html),
        next_answer_html=summarize_html(next_answer_html),
        previous_chat_history=summarize_messages(previous_chat_history or []),
        next_chat_history=summarize_messages(next_chat_history or []),
        include_stack=include_stack,
    )


def log_page_cache_return(
    event: str,
    *,
    page_key: str,
    last_question: Any = "",
    answer_value: Any = "",
    chat_history: Any = None,
    session_key: str | None = None,
    done: Any = None,
) -> None:
    log_event(
        event,
        page_key=page_key,
        session_key=session_key,
        done=done,
        last_question=summarize_text(last_question),
        answer_value=summarize_html(answer_value),
        chat_history=summarize_messages(chat_history or []),
        include_stack=True,
    )


def log_page_cache_write(
    *,
    page_key: str,
    page_number: Any,
    file_id: str,
    previous: Any,
    answer_text: Any,
    chat_history: Any,
) -> None:
    previous = previous if isinstance(previous, dict) else {}
    log_event(
        "page_preview.cache_page_outputs",
        page_key=page_key,
        page_number=page_number,
        file_id=file_id,
        previous_answer_text=summarize_html(previous.get("answer_text", "")),
        next_answer_text=summarize_html(answer_text),
        previous_chat_history=summarize_messages(previous.get("chat_history", [])),
        next_chat_history=summarize_messages(chat_history or []),
        include_stack=True,
    )


def log_answer_panel_render(
    event: str,
    *,
    is_thinking: bool,
    user_input: Any = "",
    ai_response: Any = "",
    preserved_history: Any = None,
    reasoning_html: Any = "",
    messages_html: Any = "",
) -> None:
    log_event(
        event,
        is_thinking=is_thinking,
        user_input=summarize_text(user_input),
        ai_response=summarize_text(ai_response),
        preserved_history=summarize_messages(preserved_history or []),
        reasoning_html=summarize_html(reasoning_html),
        messages_html=summarize_html(messages_html),
        include_stack=not is_thinking,
    )


def log_chat_fn_start(**fields: Any) -> None:
    log_event(
        "chat_page.chat_fn.start",
        conversation_id=fields.get("conversation_id"),
        chat_input=summarize_text(fields.get("chat_input")),
        chat_output=summarize_text(fields.get("chat_output")),
        chat_history=summarize_messages(fields.get("chat_history", [])),
        active_file_id=fields.get("active_file_id"),
        active_file_name=fields.get("active_file_name"),
        page_number=fields.get("page_number"),
        qa_scope=fields.get("qa_scope"),
        controller_mode=fields.get("controller_mode"),
        route_policy=fields.get("route_policy"),
        verification_mode=fields.get("verification_mode"),
        include_stack=True,
    )


def log_chat_fn_runtime_response(request_key: str, response: Any) -> None:
    log_event(
        "chat_page.chat_fn.runtime_response",
        request_key=request_key,
        response_answer=summarize_text(getattr(response, "answer", "")),
        response_messages=summarize_messages(getattr(response, "messages", [])),
        route_decision=getattr(response, "route_decision", None),
        retrieve_decision=getattr(response, "retrieve_decision", None),
        verify_decision=getattr(response, "verify_decision", None),
        include_stack=True,
    )


def log_stream_final_received(
    request_key: str,
    *,
    displayed_answer: Any,
    turn_update: Any,
    response: Any,
) -> None:
    log_event(
        "chat_docqa_streaming.turn_update_final_received",
        request_key=request_key,
        displayed_answer=summarize_text(displayed_answer),
        final_update_answer=summarize_text(getattr(turn_update, "answer", "")),
        response_answer=summarize_text(getattr(response, "answer", "")),
        response_messages=summarize_messages(getattr(response, "messages", [])),
        include_stack=True,
    )


def log_stream_start(
    *,
    request_key: str,
    chat_input: Any,
    active_file_id: str,
    page_number: Any,
    preserved_history: Any,
) -> None:
    log_event(
        "chat_docqa_streaming.stream_start",
        request_key=request_key,
        chat_input=summarize_text(chat_input),
        active_file_id=active_file_id,
        page_number=page_number,
        preserved_history=summarize_messages(preserved_history),
        include_stack=True,
    )


def log_stream_turn_update(
    *,
    request_key: str,
    turn_update: Any,
    displayed_answer: Any,
) -> None:
    log_event(
        "chat_docqa_streaming.turn_update",
        request_key=request_key,
        stream_event=getattr(turn_update, "event", None),
        raw_answer=summarize_text(getattr(turn_update, "answer", "")),
        displayed_answer=summarize_text(displayed_answer),
        stream_event_count=len(getattr(turn_update, "stream_events", []) or []),
    )


def log_typewriter_frame(
    *,
    request_key: str,
    frame_index: int,
    display_answer: Any,
) -> None:
    log_event(
        "chat_docqa_streaming.typewriter_frame",
        request_key=request_key,
        frame_index=frame_index,
        display_answer=summarize_text(display_answer),
    )


def log_stream_return(
    *,
    request_key: str,
    displayed_answer: Any,
    final_response: Any,
) -> None:
    log_event(
        "chat_docqa_streaming.stream_return",
        request_key=request_key,
        displayed_answer=summarize_text(displayed_answer),
        response_answer=summarize_text(getattr(final_response, "answer", "")),
        response_messages=summarize_messages(getattr(final_response, "messages", [])),
        include_stack=True,
    )


def log_live_output(
    event: str,
    *,
    request_key: str,
    active_view: bool,
    answer_text: Any,
    answer_html: Any,
    chat_history: Any,
    extra: dict[str, Any] | None = None,
) -> None:
    log_event(
        event,
        request_key=request_key,
        active_view=active_view,
        answer_text=summarize_text(answer_text),
        answer_html=summarize_html(answer_html),
        chat_history=summarize_messages(chat_history),
        **(extra or {}),
        include_stack=True,
    )


def log_final_docqa_output(
    *,
    request_key: str,
    active_view: bool,
    response: Any,
    answer_text: Any,
    answer_html: Any,
    chat_history: Any,
) -> None:
    log_live_output(
        "chat_docqa_streaming.final_output",
        request_key=request_key,
        active_view=active_view,
        answer_text=answer_text,
        answer_html=answer_html,
        chat_history=chat_history,
        extra={
            "response_messages": summarize_messages(getattr(response, "messages", [])),
            "route_decision": getattr(response, "route_decision", None),
            "retrieve_decision": getattr(response, "retrieve_decision", None),
            "verify_decision": getattr(response, "verify_decision", None),
        },
    )


def log_response_override(
    *,
    previous_response_answer: Any,
    displayed_answer: Any,
    previous_response_messages: Any,
    next_response_messages: Any,
) -> None:
    log_event(
        "chat_docqa_streaming.with_displayed_final_answer",
        previous_response_answer=summarize_text(previous_response_answer),
        displayed_answer=summarize_text(displayed_answer),
        previous_response_messages=summarize_messages(previous_response_messages),
        next_response_messages=summarize_messages(next_response_messages),
        include_stack=True,
    )


def log_runtime_stream_start(request: Any) -> None:
    log_event(
        "docqa_runtime.stream_turn.start",
        conversation_id=getattr(request, "conversation_id", None),
        prompt=summarize_text(getattr(request, "prompt", "")),
        origin=getattr(request, "origin", None),
        active_file_id=getattr(request, "active_file_id", None),
        page_number=getattr(request, "page_number", None),
        qa_scope=getattr(request, "qa_scope", None),
        verification_mode=getattr(request, "verification_mode", None),
        include_stack=True,
    )


def log_runtime_finalize_response(
    event: str,
    *,
    conversation_id: str,
    stream_text: Any = "",
    messages: Any = None,
    refs: Any = "",
    response: Any = None,
    retrieval_history: Any = None,
    plot_history: Any = None,
) -> None:
    log_event(
        event,
        conversation_id=conversation_id,
        stream_text=summarize_text(stream_text),
        messages=summarize_messages(messages or []),
        refs=summarize_html(refs),
        response_answer=summarize_text(getattr(response, "answer", "")),
        response_messages=summarize_messages(getattr(response, "messages", [])),
        retrieval_history_count=len(retrieval_history or []),
        plot_history_count=len(plot_history or []),
        include_stack=True,
    )


def log_persist_state(
    event: str,
    *,
    conversation_id: str,
    messages: Any = None,
    retrieval_message: Any = "",
    existing_messages: Any = None,
    committed_messages: Any = None,
    **fields: Any,
) -> None:
    log_event(
        event,
        conversation_id=conversation_id,
        messages=summarize_messages(messages or []),
        retrieval_message=summarize_html(retrieval_message),
        existing_messages=summarize_messages(existing_messages or []),
        committed_messages=summarize_messages(committed_messages or []),
        **fields,
        include_stack=True,
    )
