from __future__ import annotations

from typing import Callable

import gradio as gr

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

    if session_key:
        snapshot = get_snapshot_by_page(session_key, page_key)
        if snapshot:
            last_question = snapshot.get("last_question", "") or ""
            mindmap_html = snapshot.get("mindmap_html", "") or mindmap_placeholder
            answer_html = snapshot.get("answer_html", "") or answer_placeholder
            chat_history = snapshot.get("chat_history", []) or []
            return _page_outputs(last_question, mindmap_html, answer_html, chat_history)

    if not isinstance(page_outputs_cache, dict):
        return clear_page_outputs()

    page_output = page_outputs_cache.get(page_key, {})
    if not isinstance(page_output, dict):
        return clear_page_outputs()

    last_question = page_output.get("last_question", "") or ""
    mindmap_html = page_output.get("mindmap_html", "") or ""
    answer_text = page_output.get("answer_text", "") or ""
    chat_history = page_output.get("chat_history", []) or []
    if not (last_question or mindmap_html or answer_text or chat_history):
        return clear_page_outputs()

    mindmap_html = mindmap_html or mindmap_placeholder
    answer_text = answer_text or answer_placeholder
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
    updated_cache = dict(page_outputs_cache)
    updated_cache[page_key] = {
        "last_question": last_question or "",
        "mindmap_html": mindmap_html or "",
        "answer_text": answer_text or "",
        "chat_history": chat_history or [],
    }
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
