from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from typing import Any

from .canonical_proposition_evidence_plan_contract import canonical_selector_sort_key

EvidenceCandidate = tuple[
    tuple[Any, ...],
    tuple[dict[str, Any], ...],
    dict[str, Any],
]
EvidenceAnalyzer = Callable[
    [tuple[dict[str, Any], ...], str],
    dict[str, Any],
]

_MAX_CROSS_EVENT_CANDIDATES = 256


@dataclass(frozen=True, slots=True)
class CanonicalEvidenceCandidateEnumeration:
    support: tuple[EvidenceCandidate, ...]
    contradiction: tuple[EvidenceCandidate, ...]
    trace: dict[str, Any]


def enumerate_canonical_evidence_candidates(
    selectors: Sequence[dict[str, Any]],
    required_slots: Sequence[str],
    required_object_tokens: Sequence[str],
    *,
    analyze: EvidenceAnalyzer,
) -> CanonicalEvidenceCandidateEnumeration:
    pool = _bounded_selector_pool(list(selectors), required_slots)
    valid: dict[str, list[EvidenceCandidate]] = {
        "proposition_support": [],
        "explicit_contradiction": [],
    }
    rejected: dict[str, list[EvidenceCandidate]] = {
        "proposition_support": [],
        "explicit_contradiction": [],
    }
    local_candidates = _event_local_candidates(pool)
    relation_analysis_count = 0
    complete_by_event: dict[str, list[tuple[dict[str, Any], ...]]] = defaultdict(list)
    for canonical_selected in local_candidates:
        for relation in valid:
            analysis = analyze(canonical_selected, relation)
            relation_analysis_count += 1
            destination = valid if analysis.get("valid") is True else rejected
            destination[relation].append(
                (
                    _evidence_set_rank(canonical_selected, analysis),
                    canonical_selected,
                    analysis,
                )
            )
        if _event_candidate_complete(
            canonical_selected,
            required_slots,
            required_object_tokens,
        ):
            event_id = str(canonical_selected[0].get("event_id") or "")
            if event_id:
                complete_by_event[event_id].append(canonical_selected)

    cross_event_candidates = _bounded_cross_event_candidates(complete_by_event)
    for canonical_selected in cross_event_candidates:
        relation = "explicit_contradiction"
        analysis = analyze(canonical_selected, relation)
        relation_analysis_count += 1
        destination = valid if analysis.get("valid") is True else rejected
        destination[relation].append(
            (
                _evidence_set_rank(canonical_selected, analysis),
                canonical_selected,
                analysis,
            )
        )
    for values in valid.values():
        values.sort(key=lambda value: value[0])
    trace = _construction_trace(
        selectors,
        pool,
        len(local_candidates) + len(cross_event_candidates),
        relation_analysis_count,
        valid,
        rejected,
    )
    return CanonicalEvidenceCandidateEnumeration(
        support=tuple(valid["proposition_support"]),
        contradiction=tuple(valid["explicit_contradiction"]),
        trace=trace,
    )


def _bounded_selector_pool(
    selectors: list[dict[str, Any]],
    required_slots: Sequence[str],
) -> list[dict[str, Any]]:
    ranked = sorted(
        selectors,
        key=lambda selector: (
            0 if selector.get("predicate_match_kind") == "exact" else 1,
            -len(selector.get("object_tokens") or []),
            -len(set(required_slots) & set(selector.get("slot_hints") or [])),
            canonical_selector_sort_key(selector),
        ),
    )
    return ranked[:16]


def _event_local_candidates(
    selectors: Sequence[dict[str, Any]],
) -> list[tuple[dict[str, Any], ...]]:
    """Enumerate only sets that may become one complete event subplan."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, selector in enumerate(selectors):
        event_id = str(selector.get("event_id") or f"__missing_event__:{index}")
        grouped[event_id].append(selector)
    output: list[tuple[dict[str, Any], ...]] = []
    for event_id in sorted(grouped):
        values = grouped[event_id]
        for count in range(1, min(4, len(values)) + 1):
            output.extend(
                tuple(sorted(selected, key=canonical_selector_sort_key))
                for selected in combinations(values, count)
            )
    return output


def _event_candidate_complete(
    selected: Sequence[Mapping[str, Any]],
    required_slots: Sequence[str],
    required_object_tokens: Sequence[str],
) -> bool:
    covered_slots = {
        str(slot) for selector in selected for slot in selector.get("slot_hints") or []
    }
    covered_object = {
        str(token)
        for selector in selected
        if "object" in (selector.get("slot_hints") or [])
        for token in selector.get("object_tokens") or []
    }
    return set(required_slots) <= covered_slots and set(required_object_tokens) <= (
        covered_object
    )


def _bounded_cross_event_candidates(
    complete_by_event: Mapping[str, Sequence[tuple[dict[str, Any], ...]]],
) -> list[tuple[dict[str, Any], ...]]:
    """Pair independently complete event plans for typed contradiction only."""

    candidates: list[tuple[dict[str, Any], ...]] = []
    event_ids = sorted(complete_by_event)
    for first_index, first_event in enumerate(event_ids):
        for second_event in event_ids[first_index + 1 :]:
            for first in complete_by_event[first_event]:
                for second in complete_by_event[second_event]:
                    if len(first) + len(second) > 4:
                        continue
                    candidates.append(
                        tuple(
                            sorted(
                                (*first, *second),
                                key=canonical_selector_sort_key,
                            )
                        )
                    )
    candidates.sort(
        key=lambda selected: (
            len(selected),
            -sum(
                selector.get("predicate_match_kind") == "exact" for selector in selected
            ),
            tuple(canonical_selector_sort_key(value) for value in selected),
        )
    )
    return candidates[:_MAX_CROSS_EVENT_CANDIDATES]


def _evidence_set_rank(
    selected: tuple[dict[str, Any], ...],
    analysis: Mapping[str, Any],
) -> tuple[Any, ...]:
    anchor_slot_count = max(
        (
            len(selector.get("slot_hints") or [])
            for selector in selected
            if "predicate" in (selector.get("slot_hints") or [])
        ),
        default=0,
    )
    return (
        -int(analysis.get("exact_predicate_count") or 0),
        0 if analysis.get("comparison_relation") else 1,
        -anchor_slot_count,
        0 if analysis.get("same_event") is True else 1,
        _predicate_argument_coherence(selected),
        len(selected),
        tuple(canonical_selector_sort_key(selector) for selector in selected),
    )


def _predicate_argument_coherence(
    selected: Sequence[Mapping[str, Any]],
) -> tuple[int, int]:
    anchors = [
        value for value in selected if "predicate" in (value.get("slot_hints") or [])
    ]
    companions = [
        value
        for value in selected
        if "predicate" not in (value.get("slot_hints") or [])
        and set(value.get("slot_hints") or []) & {"object", "quantifier"}
    ]
    if not anchors or not companions:
        return (0, 0)
    backwards = 0
    distance = 0
    for companion in companions:
        start = int(companion.get("span_start") or 0)
        end = int(companion.get("span_end") or start)
        choices = []
        for anchor in anchors:
            anchor_start = int(anchor.get("span_start") or 0)
            anchor_end = int(anchor.get("span_end") or anchor_start)
            choices.append(
                (
                    1 if end <= anchor_start else 0,
                    min(abs(start - anchor_end), abs(anchor_start - end)),
                )
            )
        direction, gap = min(choices)
        backwards += direction
        distance += gap
    return backwards, distance


def _construction_trace(
    selectors: Sequence[dict[str, Any]],
    pool: Sequence[dict[str, Any]],
    candidate_count: int,
    relation_analysis_count: int,
    valid: Mapping[str, Sequence[EvidenceCandidate]],
    rejected: Mapping[str, Sequence[EvidenceCandidate]],
) -> dict[str, Any]:
    return {
        "contract_id": "canonical_plan_construction_trace.v1",
        "selector_count": len(selectors),
        "bounded_selector_count": len(pool),
        "bounded_selector_refs": [
            str(selector.get("selector_id") or "") for selector in pool
        ],
        "candidate_count": candidate_count,
        "relation_analysis_count": relation_analysis_count,
        "selector_universe_refs": [
            str(selector.get("selector_id") or "") for selector in selectors
        ],
        "event_ids": sorted(
            {
                str(selector.get("event_id") or "")
                for selector in selectors
                if str(selector.get("event_id") or "")
            }
        ),
        "valid_candidate_counts": {
            relation: len(values) for relation, values in valid.items()
        },
        "valid_candidate_refs": {
            relation: list(
                dict.fromkeys(
                    str(selector.get("selector_id") or "")
                    for _rank, selected, _analysis in values
                    for selector in selected
                    if str(selector.get("selector_id") or "")
                )
            )
            for relation, values in valid.items()
        },
        "best_rejected": {
            relation: _best_rejected(values) for relation, values in rejected.items()
        },
    }


def _best_rejected(values: Sequence[EvidenceCandidate]) -> dict[str, Any]:
    if not values:
        return {}
    _rank, selected, analysis = min(
        values,
        key=lambda value: _rejected_rank(value[1], value[2]),
    )
    return {
        "span_refs": [str(value.get("selector_id") or "") for value in selected],
        "event_ids": list(analysis.get("event_ids") or []),
        "reason": str(analysis.get("reason") or ""),
        "rejection_reasons": list(analysis.get("rejection_reasons") or []),
        "required_slots": list(analysis.get("required_slots") or []),
        "covered_slots": list(analysis.get("covered_slots") or []),
        "required_object_tokens": list(analysis.get("required_object_tokens") or []),
        "covered_object_tokens": list(analysis.get("covered_object_tokens") or []),
        "event_subplans": list(analysis.get("event_subplans") or []),
    }


def _rejected_rank(
    selected: Sequence[Mapping[str, Any]],
    analysis: Mapping[str, Any],
) -> tuple[Any, ...]:
    return (
        -len(analysis.get("covered_slots") or []),
        -len(analysis.get("covered_object_tokens") or []),
        len(analysis.get("rejection_reasons") or []),
        len(selected),
        tuple(canonical_selector_sort_key(value) for value in selected),
    )
