from __future__ import annotations

from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan import (
    AMBIGUOUS_CONFLICT,
    UNRESOLVED,
    CanonicalPropositionEvidencePlan,
)
from ktem.docqa.qasper_boolean_no_evidence import qasper_no_evidence_set_analysis
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_lexical import (
    canonical_proposition_object_token_set,
)

from .mara_qasper_candidate_evidence_projection import (
    span_set_refs,
    span_set_slot_refs,
    span_set_spans,
)
from .mara_qasper_candidate_evidence_sets import selector_sort_key
from .mara_qasper_candidate_selector_semantics import candidate_structural_features

_PROPOSITION_SLOTS = ("actor", "predicate", "object", "quantifier")
_MAX_SELECTOR_UNIVERSE = 16


def candidate_evidence_set_result(
    records: list[dict[str, Any]],
    question: str,
    applicable_slots: tuple[str, ...],
    selectors: list[dict[str, Any]],
    plan: CanonicalPropositionEvidencePlan,
    support: tuple[dict[str, Any], ...] | None,
    contradiction: tuple[dict[str, Any], ...] | None,
    *,
    construction_trace: dict[str, Any],
) -> dict[str, Any]:
    selected_lookup = {
        str(selector.get("selector_id") or ""): selector for selector in selectors
    }
    selected = tuple(
        selected_lookup[ref] for ref in plan.span_refs if ref in selected_lookup
    )
    support_refs = span_set_refs(support)
    contradiction_refs = span_set_refs(contradiction)
    selected_refs = span_set_refs(selected)
    selected_slots = span_set_slot_refs(selected)
    selector_refs, selector_status = _selector_universe(
        question,
        applicable_slots,
        selectors,
        support_refs,
        contradiction_refs,
        selected_refs,
        construction_trace=construction_trace,
    )
    slot_states = _candidate_slot_states(applicable_slots, selected_slots)
    return {
        "typed_proposition": build_question_proposition(question).as_dict(),
        "evidence_ids": _selected_evidence_ids(selected),
        "required_slots": list(applicable_slots),
        "applicable_slots": list(applicable_slots),
        "not_applicable_slots": [
            slot for slot in _PROPOSITION_SLOTS if slot not in applicable_slots
        ],
        "covered_slots": [
            slot for slot in _PROPOSITION_SLOTS if slot in selected_slots
        ],
        "slot_states": slot_states,
        "quantifier_evidence_state": slot_states["quantifier"],
        "binding_status": (
            "missing"
            if plan.binding_state in {AMBIGUOUS_CONFLICT, UNRESOLVED}
            else "bound"
        ),
        "binding_state": plan.binding_state,
        "binding_reason": _candidate_binding_reason(records, selected, plan),
        "canonical_evidence_plan": plan.as_dict(),
        "canonical_evidence_plan_id": plan.plan_id,
        "canonical_evidence_plan_digest": plan.plan_digest,
        "plan_construction_trace": construction_trace,
        "event_binding_id": plan.event_binding_id,
        "evidence_refs": selected_refs,
        "selector_universe_refs": selector_refs,
        "selector_universe_status": selector_status,
        "evidence_set_spans": span_set_spans(selected),
        "slot_evidence_refs": selected_slots,
        "proposition_slot_spans": _span_set_slot_spans(selected),
        **_polarity_observations(question, support, contradiction),
        "polarity_signal": _polarity_signal(plan.polarity_relation),
        "relation_anchor_refs": [
            str(selector["selector_id"])
            for selector in selected
            if "predicate" in selector.get("slot_hints", [])
        ],
        "structural_features": candidate_structural_features(
            question,
            selected,
            applicable_slots=applicable_slots,
        ),
    }


def _polarity_observations(
    question: str,
    support: tuple[dict[str, Any], ...] | None,
    contradiction: tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    return {
        "support": support is not None,
        "support_evidence_refs": span_set_refs(support),
        "support_evidence_set_spans": span_set_spans(support),
        "support_slot_evidence_refs": span_set_slot_refs(support),
        "explicit_contradiction": contradiction is not None,
        "explicit_contradiction_evidence_refs": span_set_refs(contradiction),
        "explicit_contradiction_evidence_set_spans": span_set_spans(contradiction),
        "explicit_contradiction_slot_evidence_refs": span_set_slot_refs(contradiction),
        "no_evidence_semantics": qasper_no_evidence_set_analysis(
            question,
            contradiction or (),
        ),
    }


def _polarity_signal(polarity_relation: str) -> str:
    return {
        "proposition_support": "support",
        "explicit_contradiction": "explicit_contradiction",
        "ambiguous": "undetermined",
        "unresolved": "undetermined",
    }[polarity_relation]


def _selected_evidence_ids(
    selected: tuple[dict[str, Any], ...] | None,
) -> list[str]:
    return list(
        dict.fromkeys(
            str(selector["evidence_id"])
            for selector in selected or ()
            if str(selector["evidence_id"])
        )
    )


def _candidate_slot_states(
    applicable_slots: tuple[str, ...],
    selected_slots: dict[str, list[str]],
) -> dict[str, str]:
    return {
        slot: (
            "not_applicable"
            if slot == "quantifier" and slot not in applicable_slots
            else "bound"
            if slot in selected_slots
            else "missing"
        )
        for slot in _PROPOSITION_SLOTS
    }


def _selector_universe(
    question: str,
    applicable_slots: tuple[str, ...],
    selectors: list[dict[str, Any]],
    support_refs: list[str],
    contradiction_refs: list[str],
    selected_refs: list[str],
    *,
    construction_trace: dict[str, Any],
) -> tuple[list[str], str]:
    valid_refs = construction_trace.get("valid_candidate_refs")
    if isinstance(valid_refs, dict):
        proposition_bearing = list(
            dict.fromkeys(
                str(ref)
                for relation in (
                    "proposition_support",
                    "explicit_contradiction",
                )
                for ref in valid_refs.get(relation) or []
                if str(ref)
            )
        )
        if proposition_bearing:
            return proposition_bearing, "bounded"
    polarized = list(dict.fromkeys([*support_refs, *contradiction_refs]))
    refs = (
        polarized
        or selected_refs
        or _relation_aligned_selector_refs(
            question,
            selectors,
            applicable_slots,
        )
    )
    return refs, "bounded"


def _span_set_slot_spans(
    selectors: tuple[dict[str, Any], ...] | None,
) -> dict[str, list[dict[str, Any]]]:
    return {
        slot: [
            dict(selector["proposition_slot_spans"][slot])
            for selector in selectors or ()
            if slot in dict(selector.get("proposition_slot_spans") or {})
        ]
        for slot in _PROPOSITION_SLOTS
        if any(
            slot in dict(selector.get("proposition_slot_spans") or {})
            for selector in selectors or ()
        )
    }


def _relation_aligned_selector_refs(
    question: str,
    selectors: list[dict[str, Any]],
    required_slots: tuple[str, ...],
) -> list[str]:
    required_object_tokens = canonical_proposition_object_token_set(
        build_question_proposition(question)
    )
    anchors = [
        selector
        for selector in selectors
        if "predicate" in selector.get("slot_hints", [])
        and selector.get("relation_bearing") is True
    ]
    anchors.sort(
        key=lambda selector: (
            -len(required_object_tokens & set(selector.get("object_tokens") or [])),
            -len(selector.get("slot_hints") or []),
            selector_sort_key(selector),
        )
    )
    if not anchors:
        return []
    selected = anchors[:_MAX_SELECTOR_UNIVERSE]
    covered = {slot for value in selected for slot in value.get("slot_hints", [])}
    covered_object_tokens = {
        token
        for value in selected
        for token in set(value.get("object_tokens") or []) & required_object_tokens
    }
    anchor_records = {str(value.get("evidence_id") or "") for value in selected}
    ranked = sorted(
        selectors,
        key=lambda selector: (
            -len(
                (set(required_slots) - covered) & set(selector.get("slot_hints") or [])
            ),
            -len(required_object_tokens & set(selector.get("object_tokens") or [])),
            selector_sort_key(selector),
        ),
    )
    for selector in ranked:
        if selector in selected or len(selected) >= _MAX_SELECTOR_UNIVERSE:
            continue
        slots = set(selector.get("slot_hints") or [])
        object_overlap = required_object_tokens & set(
            selector.get("object_tokens") or []
        )
        new_object_tokens = object_overlap - covered_object_tokens
        same_record = str(selector.get("evidence_id") or "") in anchor_records
        if object_overlap and (slots - covered or new_object_tokens or same_record):
            selected.append(selector)
            covered.update(slots)
            covered_object_tokens.update(object_overlap)
    return [str(value["selector_id"]) for value in selected]


def _candidate_binding_reason(
    records: list[dict[str, Any]],
    selected: tuple[dict[str, Any], ...],
    plan: CanonicalPropositionEvidencePlan,
) -> str:
    if plan.binding_state == AMBIGUOUS_CONFLICT:
        return "ambiguous_support_contradiction"
    if selected:
        return "exact_span_set"
    if any(
        str(record.get("evidence_id") or "").strip() or record.get("selectors")
        for record in records
    ):
        return "record_identity_only"
    return "no_exact_selectors"
