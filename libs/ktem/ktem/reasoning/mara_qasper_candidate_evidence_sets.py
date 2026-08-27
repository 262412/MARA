from __future__ import annotations

from itertools import combinations
from typing import Any

from ktem.docqa.qasper_boolean_no_evidence import (
    qasper_no_evidence_set_analysis,
    qasper_support_evidence_binding_complete,
)
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_lexical import semantic_content_token_set

from .mara_qasper_candidate_selector_semantics import (
    selector_direct_polarity_evidence,
    selector_polarity_signal,
    spans_overlap,
)


def candidate_span_set(
    question: str,
    selectors: list[dict[str, Any]],
    required_slots: tuple[str, ...],
    *,
    polarity: str | None,
) -> tuple[dict[str, Any], ...] | None:
    ordered = sorted(selectors, key=selector_sort_key)
    if polarity is None:
        pool = _bounded_selector_pool(ordered, required_slots, ())
        for count in range(1, min(4, len(pool)) + 1):
            for selected in combinations(pool, count):
                candidate = _valid_candidate_span_set(
                    question,
                    selected,
                    required_slots,
                    polarity=None,
                )
                if candidate is not None:
                    return candidate
        return None
    anchors = [
        selector
        for selector in ordered
        if "predicate" in selector.get("slot_hints", [])
        and selector_polarity_signal(
            selector,
            question,
            str(selector["text"]),
        )
        == ("support" if polarity == "yes" else "explicit_contradiction")
    ]
    for anchor in anchors:
        pool = _bounded_selector_pool(ordered, required_slots, (anchor,))
        remaining = [selector for selector in pool if selector is not anchor]
        for count in range(0, min(3, len(remaining)) + 1):
            for extra in combinations(remaining, count):
                candidate = _valid_candidate_span_set(
                    question,
                    (anchor, *extra),
                    required_slots,
                    polarity=polarity,
                )
                if candidate is not None:
                    return candidate
    if polarity == "no":
        pool = _bounded_selector_pool(ordered, required_slots, ())
        for count in range(1, min(4, len(pool)) + 1):
            for selected in combinations(pool, count):
                candidate = _valid_candidate_span_set(
                    question,
                    selected,
                    required_slots,
                    polarity="no",
                )
                if candidate is not None:
                    return candidate
    return None


def selector_sort_key(value: dict[str, Any]) -> tuple[str, int, int, str]:
    return (
        str(value["evidence_id"]),
        int(value["span_start"]),
        int(value["span_end"]),
        str(value["selector_id"]),
    )


def _bounded_selector_pool(
    selectors: list[dict[str, Any]],
    required_slots: tuple[str, ...],
    anchors: tuple[dict[str, Any], ...],
) -> list[dict[str, Any]]:
    ranked = sorted(
        selectors,
        key=lambda value: (-len(value["slot_hints"]), selector_sort_key(value)),
    )
    pool: list[dict[str, Any]] = []
    for selector in anchors:
        if selector not in pool:
            pool.append(selector)
    for slot in required_slots:
        for selector in ranked:
            if slot in selector["slot_hints"] and selector not in pool:
                pool.append(selector)
                break
    for selector in ranked:
        if selector not in pool:
            pool.append(selector)
    return pool


def _valid_candidate_span_set(
    question: str,
    selected: tuple[dict[str, Any], ...],
    required_slots: tuple[str, ...],
    *,
    polarity: str | None,
) -> tuple[dict[str, Any], ...] | None:
    ordered = tuple(sorted(selected, key=selector_sort_key))
    if (
        any(
            not str(value["evidence_id"]).strip()
            or not str(value["selector_id"]).strip()
            for value in ordered
        )
        or len(
            {
                (str(value["evidence_id"]), str(value["selector_id"]))
                for value in ordered
            }
        )
        != len(ordered)
        or spans_overlap(ordered)
    ):
        return None
    covered = {slot for value in ordered for slot in value["slot_hints"]}
    if not set(required_slots) <= covered:
        return None
    if not _object_coverage_sufficient(question, ordered):
        return None
    if not any("predicate" in value.get("slot_hints", []) for value in ordered):
        return None
    if not any(
        selector_direct_polarity_evidence(
            value,
            question,
            str(value.get("text") or ""),
        )
        for value in ordered
    ):
        return None
    if polarity is not None and not _polarity_span_set_valid(
        question,
        ordered,
        required_slots,
        polarity=polarity,
    ):
        return None
    return ordered


def _object_coverage_sufficient(
    question: str,
    selected: tuple[dict[str, Any], ...],
) -> bool:
    required = semantic_content_token_set(
        build_question_proposition(question).object_surface
    )
    if not required:
        return False
    covered = {
        str(token)
        for selector in selected
        if "object" in selector.get("slot_hints", [])
        for token in selector.get("object_tokens") or []
        if str(token) in required
    }
    minimum = len(required) if len(required) <= 3 else (len(required) + 1) // 2
    return len(covered) >= minimum


def _polarity_span_set_valid(
    question: str,
    selected: tuple[dict[str, Any], ...],
    required_slots: tuple[str, ...],
    *,
    polarity: str,
) -> bool:
    no_semantics = qasper_no_evidence_set_analysis(question, selected)
    if polarity == "no":
        return bool(no_semantics["admissible_as_explicit_contradiction"])
    if no_semantics["admissible_as_explicit_contradiction"]:
        return False
    if not qasper_support_evidence_binding_complete(question, selected):
        return False
    anchors = [
        selector
        for selector in selected
        if "predicate" in selector.get("slot_hints", [])
        and selector_polarity_signal(
            selector,
            question,
            str(selector["text"]),
        )
        == "support"
    ]
    for anchor in anchors:
        same_record = all(
            selector["evidence_id"] == anchor["evidence_id"] for selector in selected
        )
        anchor_slots = set(anchor.get("slot_hints") or [])
        if same_record or set(required_slots) - {"actor"} <= anchor_slots:
            return True
    return False
