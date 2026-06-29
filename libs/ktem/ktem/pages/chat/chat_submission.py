from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import gradio as gr

from .chat_submit_sources import resolve_chat_submit_sources

SELECTION_MARKER = "[Selected text from current page]"

MergeGraphSourceIdsFn = Callable[[Any, list[str]], list[str]]


@dataclass
class PreparedChatSubmission:
    chat_input_text: str
    chat_history: list
    selector_output: list[Any]
    used_command: str | None
    selected_page_text: Any
    selected_graph_context: Any
    merged_graph_source_ids: list[str]


def prepare_chat_submission(
    *,
    chat_input: dict[str, Any],
    chat_history: list,
    user_id: Any,
    settings: dict,
    first_selector_choices: list,
    graph_source_ids: Any,
    selected_page_text: Any,
    selected_graph_context: Any,
    default_question: str,
    merge_graph_source_ids: MergeGraphSourceIdsFn,
    first_indexing_file_fn: Callable[..., list[str]] | None,
    first_indexing_url_fn: Callable[..., list[str]] | None,
) -> PreparedChatSubmission:
    if not chat_input:
        raise ValueError("Input is empty")

    chat_input_text = chat_input.get("text", "")
    (
        chat_input_text,
        file_ids,
        selector_choices_to_add,
        used_command,
    ) = resolve_chat_submit_sources(
        chat_input=chat_input,
        chat_input_text=chat_input_text,
        first_selector_choices=first_selector_choices,
        settings=settings,
        user_id=user_id,
        first_indexing_file_fn=first_indexing_file_fn,
        first_indexing_url_fn=first_indexing_url_fn,
    )

    first_selector_choices.extend(selector_choices_to_add)
    merged_graph_source_ids = merge_graph_source_ids(graph_source_ids, file_ids)

    if not chat_input_text and file_ids:
        chat_input_text = default_question

    if not chat_input_text and not chat_history:
        chat_input_text = default_question

    chat_input_text, selected_page_text = _inject_selected_page_text(
        chat_input_text,
        selected_page_text,
    )

    if file_ids:
        selector_output = [
            "select",
            gr.update(value=file_ids, choices=first_selector_choices),
        ]
    else:
        selector_output = [gr.update(), gr.update()]

    if chat_input_text:
        chat_history = chat_history + [(chat_input_text, None)]
    elif not chat_history:
        raise gr.Error("Empty chat")

    return PreparedChatSubmission(
        chat_input_text=chat_input_text,
        chat_history=chat_history,
        selector_output=selector_output,
        used_command=used_command,
        selected_page_text=selected_page_text,
        selected_graph_context=selected_graph_context,
        merged_graph_source_ids=merged_graph_source_ids,
    )


def _inject_selected_page_text(
    chat_input_text: str,
    selected_page_text: Any,
) -> tuple[str, Any]:
    if not selected_page_text or not str(selected_page_text).strip():
        return chat_input_text, selected_page_text

    selected_page_text = " ".join(str(selected_page_text).split())
    if chat_input_text and SELECTION_MARKER in chat_input_text:
        return chat_input_text, selected_page_text
    if chat_input_text:
        return (
            f"{chat_input_text}\n\n{SELECTION_MARKER}\n{selected_page_text}",
            selected_page_text,
        )
    return (
        "Please explain the following selected text from the current page:\n"
        f"{selected_page_text}",
        selected_page_text,
    )
