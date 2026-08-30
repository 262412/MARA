from __future__ import annotations

import re
from typing import Any

from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_lexical import semantic_content_token_set
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
)

from .mara_qasper_candidate_selector_semantics import auditable_target_relation_present


def canonical_span_selectors(
    evidence_label: str,
    text: str,
    text_start: int,
    canonical_start: int | None,
    *,
    selector_max_chars: int,
    question: str | None = None,
    max_selectors: int | None = None,
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
    spans = _select_relevant_spans(
        text,
        spans,
        question=question,
        max_selectors=max_selectors,
    )
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


def _select_relevant_spans(
    text: str,
    spans: list[tuple[int, int]],
    *,
    question: str | None,
    max_selectors: int | None,
) -> list[tuple[int, int]]:
    """Keep a bounded, question-aware span universe without rewriting spans."""

    if max_selectors is None or max_selectors <= 0 or len(spans) <= max_selectors:
        return spans
    if not question:
        return spans[:max_selectors]
    question_tokens = semantic_content_token_set(question)
    ranked = sorted(
        enumerate(spans),
        key=lambda value: (
            *_span_semantic_rank(
                text[value[1][0] : value[1][1]],
                question,
                question_tokens,
            ),
            value[0],
        ),
    )
    selected = {index for index, _span in ranked[:max_selectors]}
    return [span for index, span in enumerate(spans) if index in selected]


def _span_semantic_rank(
    span: str,
    question: str,
    question_tokens: set[str],
) -> tuple[int, int, int, int]:
    proposition = build_question_proposition(question)
    analysis = semantic_relation_clause_analysis(
        {
            "quote": span,
            "binds_proposition_slots": list(
                applicable_proposition_evidence_slots(proposition)
            ),
        },
        proposition,
    )
    return (
        0 if auditable_target_relation_present(question, span) else 1,
        -len(analysis.get("slot_evidence") or {}),
        -len(analysis.get("covered_object_tokens") or []),
        -len(question_tokens & semantic_content_token_set(span)),
    )


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
