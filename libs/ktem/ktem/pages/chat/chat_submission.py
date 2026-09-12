from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import gradio as gr
from ktem.docqa import chat_submission as submission_core

from .chat_submit_sources import resolve_chat_submit_sources

SELECTION_MARKER = submission_core.SELECTION_MARKER

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
    content = submission_core.prepare_submission_content(
        chat_input=chat_input,
        chat_history=chat_history,
        user_id=user_id,
        settings=settings,
        first_selector_choices=first_selector_choices,
        graph_source_ids=graph_source_ids,
        selected_page_text=selected_page_text,
        default_question=default_question,
        merge_graph_source_ids=merge_graph_source_ids,
        first_indexing_file_fn=first_indexing_file_fn,
        first_indexing_url_fn=first_indexing_url_fn,
        resolve_sources=lambda **kwargs: resolve_chat_submit_sources(**kwargs),
        inject_selection=lambda text, selected: _inject_selected_page_text(
            text, selected
        ),
    )
    if content.file_ids:
        selector_output = [
            "select",
            gr.update(value=content.file_ids, choices=first_selector_choices),
        ]
    else:
        selector_output = [gr.update(), gr.update()]

    # Gradio updates precede history concatenation and the empty-chat error.
    try:
        chat_history = submission_core.complete_chat_history(
            content.chat_input_text, chat_history
        )
    except submission_core.EmptyChatError as error:
        raise gr.Error(str(error)) from None

    return PreparedChatSubmission(
        chat_input_text=content.chat_input_text,
        chat_history=chat_history,
        selector_output=selector_output,
        used_command=content.used_command,
        selected_page_text=content.selected_page_text,
        selected_graph_context=selected_graph_context,
        merged_graph_source_ids=content.merged_graph_source_ids,
    )


def _inject_selected_page_text(
    chat_input_text: str,
    selected_page_text: Any,
) -> tuple[str, Any]:
    return submission_core.inject_selected_page_text(
        chat_input_text, selected_page_text
    )
