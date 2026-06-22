from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Callable

from ...utils import get_file_names_regex, get_urls
from ...utils.commands import WEB_SEARCH_COMMAND

logger = logging.getLogger(__name__)

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
    file_ids: list[str] = []
    selector_choices_to_add: list[tuple[str, str]] = []
    used_command = None
    choices = list(first_selector_choices or [])
    first_selector_choices_map = {item[0]: item[1] for item in choices}

    uploaded_files = list(chat_input.get("files") or [])
    if uploaded_files and first_indexing_file_fn:
        logger.debug("Detected uploaded chat files: %s", uploaded_files)
        uploaded_file_ids = first_indexing_file_fn(
            uploaded_files,
            True,
            settings,
            user_id,
        )
        file_ids.extend(uploaded_file_ids)
        selector_choices_to_add.extend(
            zip(_chat_uploaded_file_names(uploaded_files), uploaded_file_ids)
        )

    file_names, chat_input_text = get_file_names_regex(chat_input_text)
    if WEB_SEARCH_COMMAND in file_names:
        used_command = WEB_SEARCH_COMMAND

    urls, chat_input_text = get_urls(chat_input_text)
    if urls and first_indexing_url_fn:
        logger.debug("Detected URLs: %s", urls)
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
        _merge_unique_file_ids(file_ids),
        selector_choices_to_add,
        used_command,
    )


def _chat_uploaded_file_names(files: list[Any]) -> list[str]:
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


def _merge_unique_file_ids(file_ids: list[str]) -> list[str]:
    merged = []
    seen = set()
    for file_id in file_ids:
        item = str(file_id or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        merged.append(item)
    return merged
