from __future__ import annotations

import re
from typing import Any

from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
)

from .mara_qasper_selector_semantic_alignment import auditable_target_relation_present
from .mara_semantic_proposition_span_selectors import canonical_span_selectors


def windowed_evidence_records(
    records: list[dict[str, Any]],
    question: str,
    *,
    item_char_limit: int,
    max_windows: int,
    selector_max_chars: int,
) -> list[dict[str, Any]]:
    groups = [
        relevant_evidence_windows(
            str(record.get("text") or ""),
            question,
            item_char_limit,
            max_windows=max_windows,
            selector_max_chars=selector_max_chars,
        )
        for record in records
    ]
    windowed: list[dict[str, Any]] = []
    for window_index in range(max_windows):
        for record, windows in zip(records, groups):
            if window_index >= len(windows):
                continue
            text, text_start = windows[window_index]
            if text:
                windowed.append(
                    {
                        **record,
                        "text": text,
                        "text_start": text_start,
                        "window_index": window_index + 1,
                    }
                )
    return windowed


def relevant_evidence_window(
    text: str,
    question: str,
    limit: int,
    *,
    selector_max_chars: int,
) -> tuple[str, int]:
    windows = relevant_evidence_windows(
        text,
        question,
        limit,
        max_windows=1,
        selector_max_chars=selector_max_chars,
    )
    return windows[0] if windows else ("", 0)


def relevant_evidence_windows(
    text: str,
    question: str,
    limit: int,
    *,
    max_windows: int,
    selector_max_chars: int,
) -> list[tuple[str, int]]:
    """Return bounded, proposition-anchored windows with exact source offsets."""

    if not text or limit <= 0 or max_windows <= 0:
        return []
    if len(text) <= limit:
        return [(text, 0)]
    tokens = _question_window_tokens(question)
    max_start = len(text) - limit
    semantic_starts = _semantic_anchor_window_starts(
        text,
        question,
        limit=limit,
        max_start=max_start,
        selector_max_chars=selector_max_chars,
    )
    starts = semantic_starts | _lexical_window_starts(
        text,
        tokens,
        limit=limit,
        max_start=max_start,
    )
    if not starts:
        return [(text[:limit], 0)]
    ranked = sorted(
        starts,
        key=lambda start: (
            *_window_score(
                text,
                question,
                tokens,
                start=start,
                limit=limit,
                semantic_starts=semantic_starts,
            ),
            start,
        ),
    )
    selected = _select_window_starts(
        text,
        question,
        starts=starts,
        ranked=ranked,
        limit=limit,
        max_windows=max_windows,
    )
    return [(text[start : start + limit], start) for start in selected]


def _question_window_tokens(question: str) -> list[str]:
    return sorted(
        set(re.findall(r"\w[\w-]{3,}", question.casefold())),
        key=lambda value: (-len(value), value),
    )


def _lexical_window_starts(
    text: str,
    tokens: list[str],
    *,
    limit: int,
    max_start: int,
) -> set[int]:
    lowered = text.casefold()
    starts: set[int] = set()
    for token in tokens:
        cursor = lowered.find(token)
        while cursor >= 0:
            starts.add(max(0, min(cursor - (limit // 3), max_start)))
            cursor = lowered.find(token, cursor + 1)
    return starts


def _window_score(
    text: str,
    question: str,
    tokens: list[str],
    *,
    start: int,
    limit: int,
    semantic_starts: set[int],
) -> tuple[int, int, int, int, int, int, int]:
    window = text[start : start + limit]
    lowered = window.casefold()
    analysis = _relation_analysis(question, window)
    target_offsets = [
        int(clause.get("span_start") or 0)
        for clause in analysis.get("clauses") or []
        if _auditable_relation_clause(question, clause)
    ]
    return (
        0 if start in semantic_starts else 1,
        0 if target_offsets else 1,
        min(
            (abs(offset - (limit // 5)) for offset in target_offsets),
            default=limit,
        ),
        -len(analysis.get("slot_evidence") or {}),
        -len(analysis.get("covered_object_tokens") or []),
        -sum(token in lowered for token in tokens),
        -sum(lowered.count(token) for token in tokens),
    )


def _select_window_starts(
    text: str,
    question: str,
    *,
    starts: set[int],
    ranked: list[int],
    limit: int,
    max_windows: int,
) -> list[int]:
    selected = [ranked[0]]
    minimum_distance = max(1, limit // 2)
    target_starts = [
        start
        for start in starts
        if _window_has_target_relation(text[start : start + limit], question)
    ]
    earliest_target = min(target_starts, default=None)
    if earliest_target is not None and all(
        abs(earliest_target - previous) >= minimum_distance for previous in selected
    ):
        selected.append(earliest_target)
    for start in ranked:
        if len(selected) >= max_windows:
            break
        if start not in selected and all(
            abs(start - previous) >= minimum_distance for previous in selected
        ):
            selected.append(start)
    return selected[:max_windows]


def _semantic_anchor_window_starts(
    text: str,
    question: str,
    *,
    limit: int,
    max_start: int,
    selector_max_chars: int,
) -> set[int]:
    selectors = canonical_span_selectors(
        "A",
        text,
        0,
        None,
        selector_max_chars=selector_max_chars,
        question=question,
        max_selectors=8,
    )
    starts = {
        _bounded_window_start(
            int(selector.get("span_start") or 0),
            limit=limit,
            max_start=max_start,
        )
        for selector in selectors
    }
    analysis = _relation_analysis(question, text)
    starts.update(
        _bounded_window_start(
            int(clause.get("span_start") or 0),
            limit=limit,
            max_start=max_start,
        )
        for clause in analysis.get("clauses") or []
        if _auditable_relation_clause(question, clause)
    )
    return starts


def _bounded_window_start(offset: int, *, limit: int, max_start: int) -> int:
    return max(0, min(offset - (limit // 5), max_start))


def _relation_analysis(question: str, text: str) -> dict[str, Any]:
    proposition = build_question_proposition(question)
    return semantic_relation_clause_analysis(
        {
            "quote": text,
            "binds_proposition_slots": ["actor", "predicate", "object"],
        },
        proposition,
    )


def _auditable_relation_clause(question: str, clause: dict[str, Any]) -> bool:
    return bool(
        clause.get("target_relation_present") is True
        and auditable_target_relation_present(question, str(clause.get("text") or ""))
    )


def _window_has_target_relation(window: str, question: str) -> bool:
    return any(
        _auditable_relation_clause(question, clause)
        for clause in _relation_analysis(question, window).get("clauses") or []
    )
