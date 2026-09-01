from __future__ import annotations

import hashlib
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
    windowed, _decisions = windowed_evidence_records_with_trace(
        records,
        question,
        item_char_limit=item_char_limit,
        max_windows=max_windows,
        selector_max_chars=selector_max_chars,
    )
    return windowed


def windowed_evidence_records_with_trace(
    records: list[dict[str, Any]],
    question: str,
    *,
    item_char_limit: int,
    max_windows: int,
    selector_max_chars: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    groups: list[list[tuple[str, int]]] = []
    decisions: list[dict[str, Any]] = []
    for record in records:
        windows, record_decisions = relevant_evidence_window_projection(
            str(record.get("text") or ""),
            question,
            item_char_limit,
            max_windows=max_windows,
            selector_max_chars=selector_max_chars,
        )
        evidence_id = str(record.get("evidence_id") or "")
        groups.append(windows)
        decisions.extend(
            {**decision, "evidence_id": evidence_id} for decision in record_decisions
        )
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
    return windowed, decisions


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

    windows, _decisions = relevant_evidence_window_projection(
        text,
        question,
        limit,
        max_windows=max_windows,
        selector_max_chars=selector_max_chars,
    )
    return windows


def relevant_evidence_window_projection(
    text: str,
    question: str,
    limit: int,
    *,
    max_windows: int,
    selector_max_chars: int,
) -> tuple[list[tuple[str, int]], list[dict[str, Any]]]:
    """Return unchanged windows plus every candidate-window disposition."""

    early = _early_window_projection(text, limit=limit, max_windows=max_windows)
    if early is not None:
        return early
    starts, scores = _ranked_window_inputs(
        text,
        question,
        limit=limit,
        selector_max_chars=selector_max_chars,
    )
    if not starts:
        return [(text[:limit], 0)], [
            _window_decision(
                text,
                start=0,
                limit=limit,
                score=(),
                selected=True,
                reason="deterministic_prefix_fallback",
            )
        ]
    ranked = sorted(starts, key=lambda start: (*scores[start], start))
    selected = _select_window_starts(
        text,
        question,
        starts=starts,
        ranked=ranked,
        limit=limit,
        max_windows=max_windows,
    )
    decisions = _ranked_window_decisions(
        text,
        ranked,
        selected,
        scores=scores,
        limit=limit,
    )
    return ([(text[start : start + limit], start) for start in selected], decisions)


def _early_window_projection(
    text: str,
    *,
    limit: int,
    max_windows: int,
) -> tuple[list[tuple[str, int]], list[dict[str, Any]]] | None:
    if not text or limit <= 0 or max_windows <= 0:
        return [], [
            _window_decision(
                text,
                start=0,
                limit=max(0, limit),
                score=(),
                selected=False,
                reason="window_input_unavailable",
            )
        ]
    if len(text) <= limit:
        return [(text, 0)], [
            _window_decision(
                text,
                start=0,
                limit=limit,
                score=(),
                selected=True,
                reason="full_source_within_limit",
            )
        ]
    return None


def _ranked_window_inputs(
    text: str,
    question: str,
    *,
    limit: int,
    selector_max_chars: int,
) -> tuple[set[int], dict[int, tuple[int, ...]]]:
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
    scores: dict[int, tuple[int, ...]] = {
        start: _window_score(
            text,
            question,
            tokens,
            start=start,
            limit=limit,
            semantic_starts=semantic_starts,
        )
        for start in starts
    }
    return starts, scores


def _ranked_window_decisions(
    text: str,
    ranked: list[int],
    selected: list[int],
    *,
    scores: dict[int, tuple[int, ...]],
    limit: int,
) -> list[dict[str, Any]]:
    minimum_distance = max(1, limit // 2)
    selected_set = set(selected)
    return [
        _window_decision(
            text,
            start=start,
            limit=limit,
            score=scores[start],
            selected=start in selected_set,
            reason=(
                "selected_for_windowing"
                if start in selected_set
                else "minimum_window_distance"
                if any(abs(start - chosen) < minimum_distance for chosen in selected)
                else "max_windows_limit"
            ),
        )
        for start in ranked
    ]


def _window_decision(
    text: str,
    *,
    start: int,
    limit: int,
    score: tuple[int, ...],
    selected: bool,
    reason: str,
) -> dict[str, Any]:
    window = text[start : start + limit]
    return {
        "window_start": start,
        "window_end": start + len(window),
        "window_text_digest": hashlib.sha256(window.encode("utf-8")).hexdigest(),
        "semantic_score": list(score),
        "selected": selected,
        "decision": "selected" if selected else "rejected",
        "reason": reason,
    }


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
