from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
from math import comb
from typing import Any

from .canonical_proposition_evidence_plan_contract import (
    canonical_plan_digest,
    canonical_selector_sort_key,
)

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
    local_candidates, local_policy = _event_local_candidates(pool)
    relation_analysis_count = 0
    complete_by_event: dict[str, list[tuple[dict[str, Any], ...]]] = defaultdict(list)
    for canonical_selected in local_candidates:
        for relation in valid:
            analysis = {
                **analyze(canonical_selected, relation),
                "candidate_origin": "event_local",
            }
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

    cross_event_candidates, cross_event_policy = _bounded_cross_event_candidates(
        complete_by_event
    )
    for canonical_selected in cross_event_candidates:
        relation = "explicit_contradiction"
        analysis = {
            **analyze(canonical_selected, relation),
            "candidate_origin": "cross_event_contradiction",
        }
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
        enumeration_policy={
            "local": local_policy,
            "cross_event": cross_event_policy,
        },
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
) -> tuple[list[tuple[dict[str, Any], ...]], dict[str, Any]]:
    """Enumerate only sets that may become one complete event subplan."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, selector in enumerate(selectors):
        event_id = str(selector.get("event_id") or f"__missing_event__:{index}")
        grouped[event_id].append(selector)
    output: list[tuple[dict[str, Any], ...]] = []
    event_decisions: list[dict[str, Any]] = []
    for event_id in sorted(grouped):
        values = grouped[event_id]
        enumerated_count = sum(
            comb(len(values), count) for count in range(1, min(4, len(values)) + 1)
        )
        not_attempted_count = sum(
            comb(len(values), count) for count in range(5, len(values) + 1)
        )
        for count in range(1, min(4, len(values)) + 1):
            output.extend(
                tuple(sorted(selected, key=canonical_selector_sort_key))
                for selected in combinations(values, count)
            )
        event_decisions.append(
            {
                "event_id": event_id,
                "selector_refs": [
                    str(selector.get("selector_id") or "") for selector in values
                ],
                "selector_count": len(values),
                "enumerated_candidate_count": enumerated_count,
                "not_attempted_candidate_count": not_attempted_count,
                "not_attempted_reason": (
                    "per_event_selector_combination_limit"
                    if not_attempted_count
                    else ""
                ),
            }
        )
    return output, {
        "contract_id": "canonical_local_candidate_enumeration_policy.v1",
        "complete": True,
        "max_selectors_per_candidate": 4,
        "event_count": len(event_decisions),
        "enumerated_candidate_count": len(output),
        "not_attempted_candidate_count": sum(
            decision["not_attempted_candidate_count"] for decision in event_decisions
        ),
        "event_decisions": event_decisions,
    }


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
) -> tuple[list[tuple[dict[str, Any], ...]], dict[str, Any]]:
    """Pair independently complete event plans for typed contradiction only."""

    candidates: list[tuple[dict[str, Any], ...]] = []
    over_width_count = 0
    pair_count = 0
    event_ids = sorted(complete_by_event)
    for first_index, first_event in enumerate(event_ids):
        for second_event in event_ids[first_index + 1 :]:
            for first in complete_by_event[first_event]:
                for second in complete_by_event[second_event]:
                    pair_count += 1
                    if len(first) + len(second) > 4:
                        over_width_count += 1
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
    selected = candidates[:_MAX_CROSS_EVENT_CANDIDATES]
    return selected, {
        "contract_id": "canonical_cross_event_candidate_enumeration_policy.v1",
        "complete": True,
        "max_selectors_per_candidate": 4,
        "candidate_limit": _MAX_CROSS_EVENT_CANDIDATES,
        "event_pair_candidate_count": pair_count,
        "over_width_not_attempted_count": over_width_count,
        "eligible_candidate_count": len(candidates),
        "enumerated_candidate_count": len(selected),
        "limit_not_attempted_count": len(candidates) - len(selected),
    }


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
    *,
    enumeration_policy: dict[str, Any],
) -> dict[str, Any]:
    candidate_decisions = _candidate_decisions(valid, rejected)
    selector_pool_decisions = _selector_pool_decisions(selectors, pool)
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
        "enumeration_policy_complete": True,
        "enumeration_policy_digest": canonical_plan_digest(enumeration_policy),
        "enumeration_policy": enumeration_policy,
        "selector_pool_decisions_complete": True,
        "selector_pool_decision_count": len(selector_pool_decisions),
        "selector_pool_decisions_digest": canonical_plan_digest(
            selector_pool_decisions
        ),
        "selector_pool_decisions": selector_pool_decisions,
        "candidate_decisions_complete": len(candidate_decisions)
        == relation_analysis_count,
        "candidate_decision_count": len(candidate_decisions),
        "candidate_decisions_digest": canonical_plan_digest(candidate_decisions),
        "candidate_decisions": candidate_decisions,
        "selected_candidate_ids": {
            relation: (
                _candidate_decision(relation, values[0], accepted=True)["candidate_id"]
                if values
                else ""
            )
            for relation, values in valid.items()
        },
    }


def _selector_pool_decisions(
    selectors: Sequence[dict[str, Any]],
    pool: Sequence[dict[str, Any]],
) -> list[dict[str, Any]]:
    pool_ranks = {
        str(selector.get("selector_id") or ""): rank
        for rank, selector in enumerate(pool, start=1)
    }
    return [
        {
            "selector_ref": str(selector.get("selector_id") or ""),
            "event_id": str(selector.get("event_id") or ""),
            "evidence_id": str(selector.get("evidence_id") or ""),
            "selected": str(selector.get("selector_id") or "") in pool_ranks,
            "pool_rank": pool_ranks.get(str(selector.get("selector_id") or "")),
            "decision": (
                "selected_for_candidate_enumeration"
                if str(selector.get("selector_id") or "") in pool_ranks
                else "bounded_selector_pool_limit"
            ),
        }
        for selector in selectors
    ]


def _candidate_decisions(
    valid: Mapping[str, Sequence[EvidenceCandidate]],
    rejected: Mapping[str, Sequence[EvidenceCandidate]],
) -> list[dict[str, Any]]:
    decisions = [
        _candidate_decision(relation, value, accepted=True)
        for relation in sorted(valid)
        for value in valid[relation]
    ]
    decisions.extend(
        _candidate_decision(relation, value, accepted=False)
        for relation in sorted(rejected)
        for value in rejected[relation]
    )
    decisions.sort(
        key=lambda value: (
            value["relation"],
            value["span_refs"],
            value["candidate_id"],
        )
    )
    return decisions


def _candidate_decision(
    relation: str,
    value: EvidenceCandidate,
    *,
    accepted: bool,
) -> dict[str, Any]:
    rank, selected, analysis = value
    span_refs = [str(selector.get("selector_id") or "") for selector in selected]
    identity = {"relation": relation, "span_refs": span_refs}
    return {
        "candidate_id": canonical_plan_digest(identity),
        **identity,
        "event_ids": list(analysis.get("event_ids") or []),
        "evidence_ids": list(
            dict.fromkeys(
                str(selector.get("evidence_id") or "")
                for selector in selected
                if str(selector.get("evidence_id") or "")
            )
        ),
        "origin": str(analysis.get("candidate_origin") or ""),
        "decision": "accepted" if accepted else "rejected",
        "reason": str(analysis.get("reason") or ""),
        "rejection_reasons": list(analysis.get("rejection_reasons") or []),
        "required_slots": list(analysis.get("required_slots") or []),
        "covered_slots": list(analysis.get("covered_slots") or []),
        "required_object_tokens": list(analysis.get("required_object_tokens") or []),
        "covered_object_tokens": list(analysis.get("covered_object_tokens") or []),
        "event_subplans": list(analysis.get("event_subplans") or []),
        "comparison_relation": analysis.get("comparison_relation"),
        "rank_digest": canonical_plan_digest(rank),
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
