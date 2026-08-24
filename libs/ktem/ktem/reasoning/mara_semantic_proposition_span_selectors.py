from __future__ import annotations

import re
from typing import Any


def canonical_span_selectors(
    evidence_label: str,
    text: str,
    text_start: int,
    canonical_start: int | None,
    *,
    selector_max_chars: int,
) -> list[dict[str, Any]]:
    spans: list[tuple[int, int]] = []
    cursor = 0
    for match in re.finditer(r".+?(?:[.!?](?=\s|$)|\n+|$)", text, re.DOTALL):
        start, end = _trimmed_span(text, match.start(), match.end())
        if start < end:
            spans.extend(_bounded_spans(text, start, end, selector_max_chars))
        cursor = match.end()
    if cursor < len(text):
        start, end = _trimmed_span(text, cursor, len(text))
        spans.extend(_bounded_spans(text, start, end, selector_max_chars))
    return [
        {
            "selector_id": f"{evidence_label}:S{index}",
            "text": text[start:end],
            "span_start": text_start + start,
            "span_end": text_start + end,
            "canonical_start": (
                canonical_start + text_start + start
                if canonical_start is not None
                else None
            ),
            "canonical_end": (
                canonical_start + text_start + end
                if canonical_start is not None
                else None
            ),
        }
        for index, (start, end) in enumerate(spans, start=1)
    ]


def _trimmed_span(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _bounded_spans(
    text: str,
    start: int,
    end: int,
    selector_max_chars: int,
) -> list[tuple[int, int]]:
    output: list[tuple[int, int]] = []
    while end - start > selector_max_chars:
        limit = start + selector_max_chars
        boundary = text.rfind(" ", start, limit + 1)
        split = boundary if boundary > start else limit
        chunk_start, chunk_end = _trimmed_span(text, start, split)
        if chunk_start < chunk_end:
            output.append((chunk_start, chunk_end))
        start = split + (1 if split < end and text[split].isspace() else 0)
        start, _ = _trimmed_span(text, start, end)
    start, end = _trimmed_span(text, start, end)
    if start < end:
        output.append((start, end))
    return output
