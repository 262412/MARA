from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .canonical_proposition_evidence_candidates import (
    EvidenceCandidate,
    enumerate_canonical_evidence_candidates,
)
from .canonical_proposition_evidence_event import canonical_event_structure_analysis
from .canonical_proposition_evidence_plan_contract import (
    AMBIGUOUS_CONFLICT,
    RELATION_BOUND_CONTRADICTION,
    RELATION_BOUND_SUPPORT,
    UNRESOLVED,
    CanonicalEventComparisonRelation,
    CanonicalEventPropositionPlan,
    CanonicalEvidenceSetPlan,
    CanonicalPropositionEvidencePlan,
    CanonicalPropositionEvidenceSelection,
)
from .canonical_proposition_evidence_plan_contract import (
    canonical_plan_digest as _digest,
)
from .canonical_proposition_evidence_plan_contract import (
    canonical_selector_sort_key,
    canonical_selector_spans_overlap,
    canonical_span_universe_digest,
)
from .qasper_boolean_no_evidence import (
    qasper_no_evidence_set_analysis,
    qasper_support_evidence_binding_complete,
)
from .question_proposition import QuestionProposition, build_question_proposition
from .semantic_relation_clause_lexical import (
    canonical_proposition_object_token_set,
    semantic_content_token_set,
)


def canonical_proposition_evidence_selection(
    question: str,
    selectors: Sequence[dict[str, Any]],
    required_slots: Sequence[str],
    *,
    candidate_transaction_id: str = "",
    span_universe_digest: str = "",
) -> CanonicalPropositionEvidenceSelection:
    proposition = build_question_proposition(question)
    ordered = sorted(selectors, key=canonical_selector_sort_key)
    enumeration = enumerate_canonical_evidence_candidates(
        ordered,
        required_slots,
        sorted(canonical_proposition_object_token_set(proposition)),
        analyze=lambda selected, relation: canonical_evidence_set_analysis(
            question,
            selected,
            required_slots,
            polarity_relation=relation,
        ),
    )
    support, support_analysis = _best_candidate(enumeration.support)
    contradiction, contradiction_analysis = _best_candidate(enumeration.contradiction)
    support_plan = _evidence_set_plan(
        proposition,
        support,
        support_analysis,
        relation="proposition_support",
    )
    contradiction_plan = _evidence_set_plan(
        proposition,
        contradiction,
        contradiction_analysis,
        relation="explicit_contradiction",
    )
    binding_state, polarity_relation = _binding_state(
        support_plan,
        contradiction_plan,
    )
    plan = _proposition_evidence_plan(
        proposition,
        ordered,
        support,
        contradiction,
        support_plan,
        contradiction_plan,
        support_analysis,
        contradiction_analysis,
        binding_state=binding_state,
        polarity_relation=polarity_relation,
        candidate_transaction_id=candidate_transaction_id,
        span_universe_digest=span_universe_digest,
    )
    construction_trace = {
        **enumeration.trace,
        "binding_state": binding_state,
        "selected": {
            "support": _selected_candidate_trace(support, support_plan),
            "contradiction": _selected_candidate_trace(
                contradiction,
                contradiction_plan,
            ),
        },
        "canonical_plan_id": plan.plan_id,
    }
    return CanonicalPropositionEvidenceSelection(
        plan=plan,
        support=support,
        contradiction=contradiction,
        construction_trace=construction_trace,
    )


def canonical_ranked_evidence_sets(
    question: str,
    selectors: Sequence[dict[str, Any]],
    required_slots: Sequence[str],
    *,
    polarity_relation: str,
) -> tuple[tuple[dict[str, Any], ...], ...]:
    """Return every locally valid span set in deterministic semantic rank order."""

    enumeration = enumerate_canonical_evidence_candidates(
        sorted(selectors, key=canonical_selector_sort_key),
        required_slots,
        sorted(
            canonical_proposition_object_token_set(build_question_proposition(question))
        ),
        analyze=lambda selected, relation: canonical_evidence_set_analysis(
            question,
            selected,
            required_slots,
            polarity_relation=relation,
        ),
    )
    candidates = (
        enumeration.support
        if polarity_relation == "proposition_support"
        else enumeration.contradiction
    )
    return tuple(selected for _rank, selected, _analysis in candidates)


def _proposition_evidence_plan(
    proposition: QuestionProposition,
    selectors: Sequence[dict[str, Any]],
    support: tuple[dict[str, Any], ...] | None,
    contradiction: tuple[dict[str, Any], ...] | None,
    support_plan: CanonicalEvidenceSetPlan | None,
    contradiction_plan: CanonicalEvidenceSetPlan | None,
    support_analysis: Mapping[str, Any],
    contradiction_analysis: Mapping[str, Any],
    *,
    binding_state: str,
    polarity_relation: str,
    candidate_transaction_id: str,
    span_universe_digest: str,
) -> CanonicalPropositionEvidencePlan:
    selected = _selected_span_set(support, contradiction)
    analysis = _selected_analysis(
        binding_state,
        support_analysis,
        contradiction_analysis,
    )
    refs = tuple(
        dict.fromkeys(
            str(selector.get("selector_id") or "")
            for selector in selected
            if str(selector.get("selector_id") or "")
        )
    )
    return CanonicalPropositionEvidencePlan(
        proposition_id=proposition.proposition_id,
        candidate_transaction_id=str(candidate_transaction_id or ""),
        event_binding_id=_overall_event_binding_id(
            proposition,
            support_plan,
            contradiction_plan,
        ),
        span_refs=refs,
        slot_refs=_slot_refs(selected),
        required_object_tokens=tuple(
            sorted(canonical_proposition_object_token_set(proposition))
        ),
        covered_object_tokens=tuple(analysis.get("covered_object_tokens") or ()),
        polarity_relation=polarity_relation,
        binding_state=binding_state,
        span_universe_digest=(
            span_universe_digest or canonical_span_universe_digest(selectors)
        ),
        support_plan=support_plan,
        contradiction_plan=contradiction_plan,
    )


def canonical_evidence_set_analysis(
    question: str,
    selected: Sequence[Mapping[str, Any]],
    required_slots: Sequence[str],
    *,
    polarity_relation: str,
) -> dict[str, Any]:
    proposition = build_question_proposition(question)
    ordered = tuple(sorted(selected, key=canonical_selector_sort_key))
    rejection_reasons: list[str] = []
    structural_reason = _structural_reason(ordered, required_slots)
    if structural_reason:
        rejection_reasons.append(structural_reason)
    required_object_tokens = canonical_proposition_object_token_set(proposition)
    covered_object_tokens = _covered_object_tokens(
        ordered,
        required_object_tokens,
    )
    no_semantics = qasper_no_evidence_set_analysis(question, ordered)
    if (
        polarity_relation == "explicit_contradiction"
        and no_semantics["admissible_as_explicit_contradiction"] is not True
    ):
        rejection_reasons.append("explicit_contradiction_missing")
    if (
        polarity_relation == "explicit_contradiction"
        and no_semantics["classification"] == "explicit_negation"
        and any(
            "predicate" in (selector.get("slot_hints") or [])
            and selector.get("local_relation_state") == "affirmative_assertion"
            for selector in ordered
        )
    ):
        rejection_reasons.append("explicit_contradiction_relation_conflict")
    if covered_object_tokens != required_object_tokens:
        rejection_reasons.append("object_coverage_incomplete")
    if not _quantifier_attachment_valid(
        proposition,
        ordered,
        required_object_tokens,
    ):
        rejection_reasons.append("quantifier_attachment_invalid")
    event_analysis = canonical_event_structure_analysis(
        proposition,
        ordered,
        required_slots,
        required_object_tokens,
        polarity_relation=polarity_relation,
        contradiction_classification=str(no_semantics["classification"]),
    )
    rejection_reasons.extend(event_analysis["rejection_reasons"])
    if polarity_relation == "proposition_support":
        if no_semantics["admissible_as_explicit_contradiction"] is True:
            rejection_reasons.append("support_conflicts_with_explicit_contradiction")
        elif not qasper_support_evidence_binding_complete(question, ordered):
            rejection_reasons.append("support_role_binding_incomplete")
        elif not _affirmative_relation_present(ordered):
            rejection_reasons.append("support_relation_unresolved")
    rejection_reasons = list(dict.fromkeys(rejection_reasons))
    covered_slots = sorted(
        {str(slot) for selector in ordered for slot in selector.get("slot_hints") or []}
    )
    return {
        "valid": not rejection_reasons,
        "reason": rejection_reasons[0] if rejection_reasons else "",
        "rejection_reasons": rejection_reasons,
        "required_slots": list(required_slots),
        "covered_slots": covered_slots,
        "required_object_tokens": tuple(sorted(required_object_tokens)),
        "covered_object_tokens": tuple(sorted(covered_object_tokens)),
        "event_binding_id": event_analysis["event_binding_id"],
        "event_ids": event_analysis["event_ids"],
        "event_subplans": event_analysis["event_subplans"],
        "comparison_relation": event_analysis["comparison_relation"],
        "no_evidence_semantics": no_semantics,
        "exact_predicate_count": sum(
            selector.get("predicate_match_kind") == "exact" for selector in ordered
        ),
        "same_event": len(_event_ids(ordered)) <= 1,
    }


def _structural_reason(
    selected: tuple[Mapping[str, Any], ...],
    required_slots: Sequence[str],
) -> str:
    if not selected:
        return "evidence_set_missing"
    identities = [
        (
            str(selector.get("evidence_id") or ""),
            str(selector.get("selector_id") or ""),
        )
        for selector in selected
    ]
    if any(
        not evidence_id or not selector_id for evidence_id, selector_id in identities
    ):
        return "selector_identity_missing"
    if len(set(identities)) != len(identities):
        return "selector_identity_duplicate"
    if canonical_selector_spans_overlap(selected):
        return "selector_spans_overlap"
    covered_slots = {
        str(slot) for selector in selected for slot in selector.get("slot_hints") or []
    }
    if not set(required_slots) <= covered_slots:
        return "slot_coverage_incomplete"
    if not any(
        "predicate" in (selector.get("slot_hints") or []) for selector in selected
    ):
        return "predicate_missing"
    return ""


def _best_candidate(
    candidates: Sequence[EvidenceCandidate],
) -> tuple[tuple[dict[str, Any], ...] | None, dict[str, Any]]:
    if not candidates:
        return None, {}
    _rank, selected, analysis = candidates[0]
    return selected, analysis


def _evidence_set_plan(
    proposition: QuestionProposition,
    selected: tuple[dict[str, Any], ...] | None,
    analysis: Mapping[str, Any],
    *,
    relation: str,
) -> CanonicalEvidenceSetPlan | None:
    if selected is None:
        return None
    span_refs = tuple(str(selector["selector_id"]) for selector in selected)
    slot_refs = _slot_refs(selected)
    event_binding_id = str(analysis.get("event_binding_id") or "")
    required_object_tokens = tuple(
        str(token) for token in analysis.get("required_object_tokens") or ()
    )
    covered_object_tokens = tuple(
        str(token) for token in analysis.get("covered_object_tokens") or ()
    )
    event_subplans = _event_subplans(analysis)
    comparison_relation = _comparison_relation(analysis)
    payload: dict[str, Any] = {
        "proposition_id": proposition.proposition_id,
        "event_binding_id": event_binding_id,
        "polarity_relation": relation,
        "span_refs": span_refs,
        "slot_refs": slot_refs,
        "required_object_tokens": required_object_tokens,
        "covered_object_tokens": covered_object_tokens,
        "event_subplans": [value.as_dict() for value in event_subplans],
        "comparison_relation": (
            comparison_relation.as_dict() if comparison_relation is not None else None
        ),
    }
    return CanonicalEvidenceSetPlan(
        plan_id=_digest(payload),
        event_binding_id=event_binding_id,
        polarity_relation=relation,
        span_refs=span_refs,
        slot_refs=slot_refs,
        required_object_tokens=required_object_tokens,
        covered_object_tokens=covered_object_tokens,
        event_subplans=event_subplans,
        comparison_relation=comparison_relation,
    )


def _event_subplans(
    analysis: Mapping[str, Any],
) -> tuple[CanonicalEventPropositionPlan, ...]:
    return tuple(
        CanonicalEventPropositionPlan(
            event_id=str(value.get("event_id") or ""),
            event_binding_id=str(value.get("event_binding_id") or ""),
            span_refs=tuple(str(ref) for ref in value.get("span_refs") or ()),
            slot_refs=tuple(
                (str(slot), tuple(str(ref) for ref in refs))
                for slot, refs in (value.get("slot_refs") or {}).items()
            ),
            required_object_tokens=tuple(
                str(token) for token in value.get("required_object_tokens") or ()
            ),
            covered_object_tokens=tuple(
                str(token) for token in value.get("covered_object_tokens") or ()
            ),
        )
        for value in analysis.get("event_subplans") or ()
    )


def _comparison_relation(
    analysis: Mapping[str, Any],
) -> CanonicalEventComparisonRelation | None:
    value = analysis.get("comparison_relation")
    if not isinstance(value, Mapping):
        return None
    return CanonicalEventComparisonRelation(
        relation_type=str(value.get("relation_type") or ""),
        contradicting_event_binding_id=str(
            value.get("contradicting_event_binding_id") or ""
        ),
        reference_event_binding_id=str(value.get("reference_event_binding_id") or ""),
    )


def _selected_candidate_trace(
    selected: tuple[dict[str, Any], ...] | None,
    plan: CanonicalEvidenceSetPlan | None,
) -> dict[str, Any]:
    if selected is None or plan is None:
        return {}
    return {
        "plan_id": plan.plan_id,
        "span_refs": [str(value.get("selector_id") or "") for value in selected],
        "event_ids": [value.event_id for value in plan.event_subplans],
    }


def _binding_state(
    support: CanonicalEvidenceSetPlan | None,
    contradiction: CanonicalEvidenceSetPlan | None,
) -> tuple[str, str]:
    if support is not None and contradiction is not None:
        return AMBIGUOUS_CONFLICT, "ambiguous"
    if support is not None:
        return RELATION_BOUND_SUPPORT, "proposition_support"
    if contradiction is not None:
        return RELATION_BOUND_CONTRADICTION, "explicit_contradiction"
    return UNRESOLVED, "unresolved"


def _selected_span_set(
    support: tuple[dict[str, Any], ...] | None,
    contradiction: tuple[dict[str, Any], ...] | None,
) -> tuple[dict[str, Any], ...]:
    by_identity: dict[tuple[str, str], dict[str, Any]] = {}
    for selector in (*tuple(support or ()), *tuple(contradiction or ())):
        key = (
            str(selector.get("evidence_id") or ""),
            str(selector.get("selector_id") or ""),
        )
        by_identity[key] = selector
    return tuple(sorted(by_identity.values(), key=canonical_selector_sort_key))


def _selected_analysis(
    binding_state: str,
    support: Mapping[str, Any],
    contradiction: Mapping[str, Any],
) -> Mapping[str, Any]:
    if binding_state == RELATION_BOUND_SUPPORT:
        return support
    if binding_state == RELATION_BOUND_CONTRADICTION:
        return contradiction
    if binding_state == AMBIGUOUS_CONFLICT:
        required = set(support.get("required_object_tokens") or ())
        covered = set(support.get("covered_object_tokens") or ()) | set(
            contradiction.get("covered_object_tokens") or ()
        )
        return {"covered_object_tokens": tuple(sorted(required & covered))}
    return {}


def _covered_object_tokens(
    selected: Sequence[Mapping[str, Any]],
    required: set[str],
) -> set[str]:
    return {
        str(token)
        for selector in selected
        if "object" in (selector.get("slot_hints") or [])
        for token in selector.get("object_tokens") or []
        if str(token) in required
    }


def _quantifier_attachment_valid(
    proposition: QuestionProposition,
    selected: Sequence[Mapping[str, Any]],
    required_object_tokens: set[str],
) -> bool:
    if proposition.quantifier in {"", "none"}:
        return True
    quantifier_tokens = semantic_content_token_set(proposition.quantifier)
    object_core = required_object_tokens - quantifier_tokens
    for selector in selected:
        if "quantifier" not in (selector.get("slot_hints") or []):
            continue
        event_id = str(selector.get("event_id") or "")
        selector_object = {
            str(token)
            for candidate in selected
            if str(candidate.get("event_id") or "") == event_id
            for token in candidate.get("object_tokens") or []
        } & object_core
        slot_spans = dict(selector.get("proposition_slot_spans") or {})
        object_span = slot_spans.get("object")
        quantifier_span = slot_spans.get("quantifier")
        same_clause = (
            not isinstance(object_span, Mapping)
            or not isinstance(quantifier_span, Mapping)
            or object_span.get("clause_ref") == quantifier_span.get("clause_ref")
        )
        if selector_object and same_clause:
            return True
    return False


def _affirmative_relation_present(selected: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        "predicate" in (selector.get("slot_hints") or [])
        and selector.get("local_relation_state") == "affirmative_assertion"
        for selector in selected
    )


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


def _event_ids(selected: Sequence[Mapping[str, Any]]) -> set[str]:
    return {
        str(selector.get("event_id") or "")
        for selector in selected
        if str(selector.get("event_id") or "")
    }


def _overall_event_binding_id(
    proposition: QuestionProposition,
    support: CanonicalEvidenceSetPlan | None,
    contradiction: CanonicalEvidenceSetPlan | None,
) -> str:
    return _digest(
        {
            "proposition_id": proposition.proposition_id,
            "support_event_binding_id": (
                support.event_binding_id if support is not None else ""
            ),
            "contradiction_event_binding_id": (
                contradiction.event_binding_id if contradiction is not None else ""
            ),
        }
    )
