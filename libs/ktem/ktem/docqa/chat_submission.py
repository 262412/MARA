"""Chat submission data preparation without page, Gradio, or database imports.

Source parsing has one implementation here. Narrow operations let the Web adapter
preserve its indexing hooks and the timing of existing module-level patches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ktem.utils import get_file_names_regex, get_urls
from ktem.utils.commands import WEB_SEARCH_COMMAND

logger = logging.getLogger(__name__)
SELECTION_MARKER = "[Selected text from current page]"
FileIndexingFn = Callable[[list[Any], bool, dict, Any], list[str]]
UrlIndexingFn = Callable[..., list[str]]
MergeGraphSourceIdsFn = Callable[[Any, list[str]], list[str]]


@dataclass
class ChatSubmissionContent:
    chat_input_text: str
    file_ids: list[str]
    used_command: str | None
    selected_page_text: Any
    merged_graph_source_ids: list[str]


class EmptyChatError(ValueError):
    """Neither a message nor existing history can be submitted."""


def chat_uploaded_file_names(files: list[Any]) -> list[str]:
    names = []
    for file_value in files:
        if isinstance(file_value, dict):
            raw_name = (
                file_value.get("orig_name")
                or file_value.get("name")
                or file_value.get("path")
            )
        else:
            raw_name = (
                getattr(file_value, "orig_name", None)
                or getattr(file_value, "name", None)
                or file_value
            )
        names.append(Path(str(raw_name or "")).name)
    return names


def merge_unique_file_ids(file_ids: list[str]) -> list[str]:
    merged = []
    seen = set()
    for file_id in file_ids:
        item = str(file_id or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged


def inject_selected_page_text(
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


def resolve_chat_submit_sources(
    *,
    chat_input: dict[str, Any],
    chat_input_text: str,
    first_selector_choices: Any,
    settings: dict,
    user_id: Any,
    first_indexing_file_fn: FileIndexingFn | None,
    first_indexing_url_fn: UrlIndexingFn | None,
    parse_file_names: Callable = get_file_names_regex,
    parse_urls: Callable = get_urls,
    uploaded_file_names: Callable = chat_uploaded_file_names,
    merge_file_ids: Callable = merge_unique_file_ids,
    log_debug: Callable = logger.debug,
) -> tuple[str, list[str], list[tuple[str, str]], str | None]:
    file_ids: list[str] = []
    selector_choices_to_add: list[tuple[str, str]] = []
    used_command = None
    choices = list(first_selector_choices or [])
    first_selector_choices_map = {item[0]: item[1] for item in choices}

    uploaded_files = list(chat_input.get("files") or [])
    if uploaded_files and first_indexing_file_fn:
        log_debug("Detected uploaded chat files: %s", uploaded_files)
        uploaded_file_ids = first_indexing_file_fn(
            uploaded_files,
            True,
            settings,
            user_id,
        )
        file_ids.extend(uploaded_file_ids)
        selector_choices_to_add.extend(
            zip(uploaded_file_names(uploaded_files), uploaded_file_ids)
        )

    file_names, chat_input_text = parse_file_names(chat_input_text)
    if WEB_SEARCH_COMMAND in file_names:
        used_command = WEB_SEARCH_COMMAND

    urls, chat_input_text = parse_urls(chat_input_text)
    if urls and first_indexing_url_fn:
        log_debug("Detected URLs: %s", urls)
        url_file_ids = first_indexing_url_fn(
            "\n".join(urls),
            True,
            settings,
            user_id,
            request=None,
        )
        file_ids.extend(url_file_ids)
        selector_choices_to_add.extend(zip(urls, url_file_ids))
    elif file_names:
        for file_name in file_names:
            file_id = first_selector_choices_map.get(file_name)
            if file_id:
                file_ids.append(file_id)

    return (
        chat_input_text,
        merge_file_ids(file_ids),
        selector_choices_to_add,
        used_command,
    )


def prepare_submission_content(
    *,
    chat_input: dict[str, Any],
    chat_history: list,
    user_id: Any,
    settings: dict,
    first_selector_choices: list,
    graph_source_ids: Any,
    selected_page_text: Any,
    default_question: str,
    merge_graph_source_ids: MergeGraphSourceIdsFn,
    first_indexing_file_fn: FileIndexingFn | None,
    first_indexing_url_fn: UrlIndexingFn | None,
    resolve_sources: Callable = resolve_chat_submit_sources,
    inject_selection: Callable = inject_selected_page_text,
) -> ChatSubmissionContent:
    if not chat_input:
        raise ValueError("Input is empty")

    chat_input_text = chat_input.get("text", "")
    (
        chat_input_text,
        file_ids,
        selector_choices_to_add,
        used_command,
    ) = resolve_sources(
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

    chat_input_text, selected_page_text = inject_selection(
        chat_input_text,
        selected_page_text,
    )

    return ChatSubmissionContent(
        chat_input_text=chat_input_text,
        file_ids=file_ids,
        used_command=used_command,
        selected_page_text=selected_page_text,
        merged_graph_source_ids=merged_graph_source_ids,
    )


def complete_chat_history(chat_input_text: str, chat_history: list) -> list:
    """Complete after selector adaptation to preserve the original error order."""
    if chat_input_text:
        return chat_history + [(chat_input_text, None)]
    if not chat_history:
        raise EmptyChatError("Empty chat")
    return chat_history
