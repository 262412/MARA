from __future__ import annotations

import ast
import copy
import re
from collections.abc import Mapping
from typing import Any

_UNIT_BOUNDARY_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "with",
}


def ragtruth_source_context(
    source_info: Any,
    response: Any,
    *,
    budget: int,
    structured: bool,
) -> str:
    text = str(source_info or "").strip()
    if budget <= 0 or not text:
        return ""
    if len(text) <= budget:
        return text
    response_text = str(response or "")
    if structured:
        projected = _structured_projection(source_info, response_text, budget)
        if projected is not None:
            return projected
    return _relevant_text(text, response_text, budget)


def _structured_projection(
    source_info: Any,
    response: str,
    budget: int,
) -> str | None:
    if isinstance(source_info, Mapping):
        payload: Any = dict(source_info)
    else:
        try:
            payload = ast.literal_eval(str(source_info or "").strip())
        except (SyntaxError, ValueError):
            return None
    if not isinstance(payload, Mapping):
        return None

    projected = copy.deepcopy(dict(payload))
    response_tokens = _content_tokens(response)
    while len(repr(projected)) > budget:
        leaves = _string_leaves(projected)
        if not leaves:
            return "{}"
        path, value = max(
            leaves,
            key=lambda item: (
                len(item[1]),
                -len(_content_tokens(item[1]) & response_tokens),
            ),
        )
        overflow = len(repr(projected)) - budget
        target = max(0, len(value) - max(overflow + 16, len(value) // 3))
        replacement = _relevant_text(value, response, target) if target >= 32 else ""
        _set_path(projected, path, replacement)
    return repr(projected)


def _relevant_text(text: str, response: str, budget: int) -> str:
    value = str(text or "").strip()
    if budget <= 0:
        return ""
    if len(value) <= budget:
        return value
    units = [
        unit.strip() for unit in _UNIT_BOUNDARY_RE.split(value) if unit and unit.strip()
    ]
    if not units:
        return value[:budget].rstrip()

    response_tokens = _content_tokens(response)
    ranked = sorted(
        range(len(units)),
        key=lambda index: (
            -_unit_score(units[index], response_tokens),
            index,
        ),
    )
    selected: list[int] = []
    used = 0
    for index in ranked:
        unit = units[index]
        separator = 1 if selected else 0
        remaining = budget - used - separator
        if remaining <= 0:
            break
        if len(unit) > remaining:
            if not selected:
                selected.append(index)
                units[index] = _relevant_window(unit, response_tokens, remaining)
            continue
        selected.append(index)
        used += len(unit) + separator
    if not selected:
        return value[:budget].rstrip()
    return " ".join(units[index] for index in sorted(selected))[:budget].rstrip()


def _relevant_window(text: str, response_tokens: set[str], budget: int) -> str:
    if len(text) <= budget:
        return text
    lowered = text.lower()
    positions = [
        lowered.find(token)
        for token in response_tokens
        if len(token) >= 4 and lowered.find(token) >= 0
    ]
    center = min(positions) if positions else 0
    start = max(0, min(center - budget // 3, len(text) - budget))
    return text[start : start + budget].strip()


def _unit_score(unit: str, response_tokens: set[str]) -> int:
    unit_tokens = _content_tokens(unit)
    shared = unit_tokens & response_tokens
    shared_numbers = {token for token in shared if token.isdigit()}
    return len(shared) + 3 * len(shared_numbers)


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in _TOKEN_RE.findall(str(value or "").lower())
        if token not in _STOPWORDS
    }


def _string_leaves(
    value: Any,
    path: tuple[Any, ...] = (),
) -> list[tuple[tuple[Any, ...], str]]:
    if isinstance(value, str):
        return [(path, value)]
    output: list[tuple[tuple[Any, ...], str]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            output.extend(_string_leaves(nested, (*path, key)))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            output.extend(_string_leaves(nested, (*path, index)))
    return output


def _set_path(value: Any, path: tuple[Any, ...], replacement: str) -> None:
    target = value
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = replacement
