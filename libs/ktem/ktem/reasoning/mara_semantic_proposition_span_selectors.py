from __future__ import annotations

import hashlib
import json
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
    selectors, _trace = canonical_span_selector_projection(
        evidence_label,
        text,
        text_start,
        canonical_start,
        selector_max_chars=selector_max_chars,
        question=question,
        max_selectors=max_selectors,
    )
    return selectors


def canonical_span_selector_projection(
    evidence_label: str,
    text: str,
    text_start: int,
    canonical_start: int | None,
    *,
    selector_max_chars: int,
    question: str | None = None,
    max_selectors: int | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return unchanged selectors plus every pre-limit span decision."""

    spans = _candidate_spans(text, selector_max_chars)
    selected_indices, selection_ranks = _relevant_span_selection(
        text,
        spans,
        question=question,
        max_selectors=max_selectors,
    )
    selected_spans = [
        span for index, span in enumerate(spans) if index in selected_indices
    ]
    selectors = _selectors_for_spans(
        evidence_label,
        text,
        selected_spans,
        text_start=text_start,
        canonical_start=canonical_start,
    )
    decisions = _span_projection_decisions(
        evidence_label,
        text,
        spans,
        selectors,
        selected_indices=selected_indices,
        selection_ranks=selection_ranks,
        text_start=text_start,
        max_selectors=max_selectors,
    )
    return selectors, {
        "contract_id": "canonical_span_selector_projection.v1",
        "complete": True,
        "input_span_count": len(spans),
        "selected_span_count": len(selectors),
        "decision_count": len(decisions),
        "decisions_digest": _digest(decisions),
        "decisions": decisions,
    }


def _candidate_spans(text: str, selector_max_chars: int) -> list[tuple[int, int]]:
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
    return spans


def _selectors_for_spans(
    evidence_label: str,
    text: str,
    spans: list[tuple[int, int]],
    *,
    text_start: int,
    canonical_start: int | None,
) -> list[dict[str, Any]]:
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


def _span_projection_decisions(
    evidence_label: str,
    text: str,
    spans: list[tuple[int, int]],
    selectors: list[dict[str, Any]],
    *,
    selected_indices: set[int],
    selection_ranks: dict[int, int],
    text_start: int,
    max_selectors: int | None,
) -> list[dict[str, Any]]:
    selector_by_span = {
        (selector["span_start"], selector["span_end"]): selector["selector_id"]
        for selector in selectors
    }
    return [
        _span_decision(
            evidence_label,
            text,
            span,
            source_index=index,
            selection_rank=selection_ranks[index],
            selected=index in selected_indices,
            selector_id=selector_by_span.get(
                (text_start + span[0], text_start + span[1]),
                "",
            ),
            text_start=text_start,
            max_selectors=max_selectors,
            limited=bool(
                max_selectors is not None
                and max_selectors > 0
                and len(spans) > max_selectors
            ),
        )
        for index, span in enumerate(spans)
    ]


def _select_relevant_spans(
    text: str,
    spans: list[tuple[int, int]],
    *,
    question: str | None,
    max_selectors: int | None,
) -> list[tuple[int, int]]:
    """Keep a bounded, question-aware span universe without rewriting spans."""

    selected, _ranks = _relevant_span_selection(
        text,
        spans,
        question=question,
        max_selectors=max_selectors,
    )
    return [span for index, span in enumerate(spans) if index in selected]


def _relevant_span_selection(
    text: str,
    spans: list[tuple[int, int]],
    *,
    question: str | None,
    max_selectors: int | None,
) -> tuple[set[int], dict[int, int]]:
    """Return selected source indexes and their deterministic selection ranks."""

    if max_selectors is None or max_selectors <= 0 or len(spans) <= max_selectors:
        indexes = list(range(len(spans)))
        return set(indexes), {index: rank for rank, index in enumerate(indexes, 1)}
    if not question:
        indexes = list(range(len(spans)))
        return set(indexes[:max_selectors]), {
            index: rank for rank, index in enumerate(indexes, 1)
        }
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
    return (
        {index for index, _span in ranked[:max_selectors]},
        {index: rank for rank, (index, _span) in enumerate(ranked, 1)},
    )


def _span_decision(
    evidence_label: str,
    text: str,
    span: tuple[int, int],
    *,
    source_index: int,
    selection_rank: int,
    selected: bool,
    selector_id: str,
    text_start: int,
    max_selectors: int | None,
    limited: bool,
) -> dict[str, Any]:
    start, end = span
    span_text = text[start:end]
    absolute_start = text_start + start
    absolute_end = text_start + end
    identity = {
        "evidence_label": evidence_label,
        "span_start": absolute_start,
        "span_end": absolute_end,
        "text_digest": hashlib.sha256(span_text.encode("utf-8")).hexdigest(),
    }
    return {
        "span_identity_digest": _digest(identity),
        **identity,
        "source_span_index": source_index + 1,
        "selection_rank": selection_rank,
        "selected": selected,
        "selector_id": selector_id,
        "decision": (
            "selected_within_limit"
            if selected and limited
            else "selected_without_limit"
            if selected
            else "per_record_selector_limit"
        ),
        "max_selectors": max_selectors,
    }


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


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
