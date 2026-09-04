from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from .canonical_proposition_evidence_plan_contract import (
    canonical_plan_digest,
    canonical_selector_sort_key,
)
from .qasper_boolean_no_evidence import qasper_no_evidence_set_analysis
from .question_proposition import QuestionProposition

_COMPARISON_RELATIONS = {
    "partial_scope_only": "partial_scope",
    "role_incompatibility": "role_incompatibility",
}


def canonical_event_structure_analysis(
    proposition: QuestionProposition,
    selected: Sequence[Mapping[str, Any]],
    required_slots: Sequence[str],
    required_object_tokens: set[str],
    *,
    polarity_relation: str,
    contradiction_classification: str,
) -> dict[str, Any]:
    """Describe independently complete event plans and their typed relation."""

    grouped, missing_identity = _selectors_by_event(selected)
    subplans = [
        _event_subplan(
            proposition,
            event_id,
            selectors,
            required_object_tokens,
        )
        for event_id, selectors in grouped.items()
    ]
    reasons = _event_structure_reasons(
        subplans,
        required_slots,
        polarity_relation=polarity_relation,
        classification=contradiction_classification,
        missing_identity=missing_identity,
    )
    comparison = _comparison_relation(
        proposition,
        grouped,
        subplans,
        classification=contradiction_classification,
    )
    if (
        polarity_relation == "explicit_contradiction"
        and len(subplans) > 1
        and contradiction_classification in _COMPARISON_RELATIONS
        and comparison is None
    ):
        reasons.append("event_comparison_relation_unbound")
    event_binding_id = canonical_plan_digest(
        {
            "proposition_id": proposition.proposition_id,
            "event_subplans": subplans,
            "comparison_relation": comparison,
        }
    )
    return {
        "event_binding_id": event_binding_id,
        "event_ids": [value["event_id"] for value in subplans],
        "event_subplans": subplans,
        "comparison_relation": comparison,
        "rejection_reasons": list(dict.fromkeys(reasons)),
    }


def _selectors_by_event(
    selected: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, tuple[Mapping[str, Any], ...]], bool]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    missing_identity = False
    for selector in sorted(selected, key=canonical_selector_sort_key):
        event_id = str(selector.get("event_id") or "")
        if not event_id:
            missing_identity = True
            continue
        grouped[event_id].append(selector)
    return (
        {event_id: tuple(values) for event_id, values in sorted(grouped.items())},
        missing_identity,
    )


def _event_subplan(
    proposition: QuestionProposition,
    event_id: str,
    selectors: Sequence[Mapping[str, Any]],
    required_object_tokens: set[str],
) -> dict[str, Any]:
    span_refs = tuple(str(value.get("selector_id") or "") for value in selectors)
    slot_refs = _slot_refs(selectors)
    covered = sorted(
        {
            str(token)
            for selector in selectors
            if "object" in (selector.get("slot_hints") or [])
            for token in selector.get("object_tokens") or []
            if str(token) in required_object_tokens
        }
    )
    binding_id = canonical_plan_digest(
        {
            "proposition_id": proposition.proposition_id,
            "event_id": event_id,
            "span_refs": span_refs,
            "slot_refs": slot_refs,
        }
    )
    return {
        "event_id": event_id,
        "event_binding_id": binding_id,
        "span_refs": list(span_refs),
        "slot_refs": {slot: list(refs) for slot, refs in slot_refs},
        "required_object_tokens": sorted(required_object_tokens),
        "covered_object_tokens": covered,
    }


def _event_structure_reasons(
    subplans: Sequence[Mapping[str, Any]],
    required_slots: Sequence[str],
    *,
    polarity_relation: str,
    classification: str,
    missing_identity: bool,
) -> list[str]:
    reasons: list[str] = []
    if missing_identity or not subplans:
        reasons.append("event_identity_missing")
    if polarity_relation == "proposition_support" and len(subplans) != 1:
        reasons.append("event_binding_inconsistent")
    elif polarity_relation == "explicit_contradiction":
        if classification == "explicit_negation" and len(subplans) != 1:
            reasons.append("event_binding_inconsistent")
        elif classification in _COMPARISON_RELATIONS and len(subplans) not in {
            1,
            2,
        }:
            reasons.append("event_comparison_arity_invalid")
    incomplete = [
        value
        for value in subplans
        if not set(required_slots) <= set(value.get("slot_refs") or {})
        or set(value.get("covered_object_tokens") or ())
        != set(value.get("required_object_tokens") or ())
    ]
    if incomplete:
        reasons.append("event_subplan_incomplete")
    if any(
        not set(required_slots) <= set(value.get("slot_refs") or {})
        for value in subplans
    ):
        reasons.append("predicate_argument_binding_incomplete")
    return reasons


def _comparison_relation(
    proposition: QuestionProposition,
    grouped: Mapping[str, Sequence[Mapping[str, Any]]],
    subplans: Sequence[Mapping[str, Any]],
    *,
    classification: str,
) -> dict[str, str] | None:
    relation_type = _COMPARISON_RELATIONS.get(classification)
    if relation_type is None or len(subplans) != 2:
        return None
    matching_event_ids = [
        event_id
        for event_id, selectors in grouped.items()
        if qasper_no_evidence_set_analysis(
            proposition.surface,
            selectors,
        ).get("classification")
        == classification
    ]
    if len(matching_event_ids) != 1:
        return None
    by_event = {str(value["event_id"]): value for value in subplans}
    contradicting = by_event[matching_event_ids[0]]
    reference = next(
        value for value in subplans if value["event_id"] != matching_event_ids[0]
    )
    return {
        "relation_type": relation_type,
        "contradicting_event_binding_id": str(contradicting["event_binding_id"]),
        "reference_event_binding_id": str(reference["event_binding_id"]),
    }


def _slot_refs(
    selected: Sequence[Mapping[str, Any]],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    slots = ("actor", "predicate", "object", "quantifier")
    return tuple(
        (
            slot,
            tuple(
                str(selector.get("selector_id") or "")
                for selector in selected
                if slot in (selector.get("slot_hints") or [])
            ),
        )
        for slot in slots
        if any(slot in (selector.get("slot_hints") or []) for selector in selected)
    )
