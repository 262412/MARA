from __future__ import annotations

import logging
from typing import Any, Callable

from ktem.docqa import chat_submission as submission_core

from ...utils import get_file_names_regex, get_urls

logger = logging.getLogger(__name__)
WEB_SEARCH_COMMAND = submission_core.WEB_SEARCH_COMMAND

FileIndexingFn = Callable[[list[Any], bool, dict, Any], list[str]]
UrlIndexingFn = Callable[..., list[str]]


def resolve_chat_submit_sources(
    *,
    chat_input: dict[str, Any],
    chat_input_text: str,
    first_selector_choices: Any,
    settings: dict,
    user_id: Any,
    first_indexing_file_fn: FileIndexingFn | None,
    first_indexing_url_fn: UrlIndexingFn | None,
) -> tuple[str, list[str], list[tuple[str, str]], str | None]:
    return submission_core.resolve_chat_submit_sources(
        chat_input=chat_input,
        chat_input_text=chat_input_text,
        first_selector_choices=first_selector_choices,
        settings=settings,
        user_id=user_id,
        first_indexing_file_fn=first_indexing_file_fn,
        first_indexing_url_fn=first_indexing_url_fn,
        parse_file_names=lambda text: get_file_names_regex(text),
        parse_urls=lambda text: get_urls(text),
        uploaded_file_names=lambda files: _chat_uploaded_file_names(files),
        merge_file_ids=lambda ids: _merge_unique_file_ids(ids),
        log_debug=lambda *args: logger.debug(*args),
    )


def _chat_uploaded_file_names(files: list[Any]) -> list[str]:
    return submission_core.chat_uploaded_file_names(files)


def _merge_unique_file_ids(file_ids: list[str]) -> list[str]:
    return submission_core.merge_unique_file_ids(file_ids)
