from __future__ import annotations

from typing import Any, Callable

import gradio as gr
from ktem.docqa import debug_trace

from .generation_store import get_snapshot_by_page, make_page_key


def get_cached_page_outputs(
    page_outputs_cache: dict,
    page_number: int,
    file_id: str,
    *,
    session_key: str | None,
    clear_page_outputs: Callable[[], tuple],
    mindmap_placeholder: str,
    answer_placeholder: str,
) -> tuple:
    page_key = make_page_key(file_id, page_number)
    debug_trace.log_event(
        "page_preview.get_cached_page_outputs.start",
        page_key=page_key,
        page_number=page_number,
        file_id=file_id,
        session_key=session_key,
        include_stack=True,
    )

    if session_key:
        snapshot = get_snapshot_by_page(session_key, page_key)
        if snapshot:
            last_question = snapshot.get("last_question", "") or ""
            mindmap_html = snapshot.get("mindmap_html", "") or mindmap_placeholder
            answer_html = snapshot.get("answer_html", "") or answer_placeholder
            chat_history = snapshot.get("chat_history", []) or []
            debug_trace.log_page_cache_return(
                "page_preview.get_cached_page_outputs.snapshot_return",
                page_key=page_key,
                session_key=session_key,
                done=snapshot.get("done"),
                last_question=last_question,
                answer_value=answer_html,
                chat_history=chat_history,
            )
            return _page_outputs(last_question, mindmap_html, answer_html, chat_history)

    if not isinstance(page_outputs_cache, dict):
        _log_clear(
            "clear_non_dict_cache",
            page_key,
            cache_type=type(page_outputs_cache).__name__,
        )
        return clear_page_outputs()

    page_output = page_outputs_cache.get(page_key, {})
    if not isinstance(page_output, dict):
        _log_clear(
            "clear_non_dict_page_output",
            page_key,
            page_output_type=type(page_output).__name__,
        )
        return clear_page_outputs()

    last_question = page_output.get("last_question", "") or ""
    mindmap_html = page_output.get("mindmap_html", "") or ""
    answer_text = page_output.get("answer_text", "") or ""
    chat_history = page_output.get("chat_history", []) or []
    if not (last_question or mindmap_html or answer_text or chat_history):
        _log_clear("clear_empty_page_output", page_key)
        return clear_page_outputs()

    mindmap_html = mindmap_html or mindmap_placeholder
    answer_text = answer_text or answer_placeholder
    debug_trace.log_page_cache_return(
        "page_preview.get_cached_page_outputs.cache_return",
        page_key=page_key,
        last_question=last_question,
        answer_value=answer_text,
        chat_history=chat_history,
    )
    return _page_outputs(last_question, mindmap_html, answer_text, chat_history)


def cache_page_outputs(
    page_outputs_cache: dict,
    page_number: int,
    last_question: str,
    mindmap_html: str,
    answer_text: str,
    file_id: str,
    chat_history: list | None,
) -> dict:
    if not isinstance(page_outputs_cache, dict):
        page_outputs_cache = {}

    page_key = f"{file_id or 'default'}_{max(1, int(page_number or 1))}"
    previous = page_outputs_cache.get(page_key, {})
    updated_cache = dict(page_outputs_cache)
    updated_cache[page_key] = {
        "last_question": last_question or "",
        "mindmap_html": mindmap_html or "",
        "answer_text": answer_text or "",
        "chat_history": chat_history or [],
    }
    debug_trace.log_page_cache_write(
        page_key=page_key,
        page_number=page_number,
        file_id=file_id,
        previous=previous,
        answer_text=answer_text,
        chat_history=chat_history or [],
    )
    return updated_cache


def _page_outputs(
    last_question: str,
    mindmap_html: str,
    answer_text: str,
    chat_history: list,
) -> tuple:
    return (
        last_question,
        mindmap_html,
        gr.skip(),
        gr.skip(),
        answer_text,
        chat_history,
    )


def _log_clear(reason: str, page_key: str, **fields: Any) -> None:
    debug_trace.log_event(
        f"page_preview.get_cached_page_outputs.{reason}",
        page_key=page_key,
        **fields,
        include_stack=True,
    )
