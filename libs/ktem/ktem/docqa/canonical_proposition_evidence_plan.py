from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from itertools import combinations
from typing import Any

from .canonical_proposition_evidence_plan_contract import (
    AMBIGUOUS_CONFLICT,
    RELATION_BOUND_CONTRADICTION,
    RELATION_BOUND_SUPPORT,
    UNRESOLVED,
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
from .semantic_relation_clause_lexical import semantic_content_token_set

_NEGATION_RE = re.compile(r"\b(?:no|not|never|without)\b|n't\b", re.IGNORECASE)

_EvidenceCandidate = tuple[
    tuple[Any, ...],
    tuple[dict[str, Any], ...],
    dict[str, Any],
]


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
    pool = _bounded_selector_pool(ordered, required_slots)
    support_candidates, contradiction_candidates = _evidence_candidates(
        question,
        pool,
        required_slots,
    )
    support, support_analysis = _best_candidate(support_candidates)
    contradiction, contradiction_analysis = _best_candidate(contradiction_candidates)
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
    return CanonicalPropositionEvidenceSelection(
        plan=plan,
        support=support,
        contradiction=contradiction,
    )


def _evidence_candidates(
    question: str,
    selectors: Sequence[dict[str, Any]],
    required_slots: Sequence[str],
) -> tuple[list[_EvidenceCandidate], list[_EvidenceCandidate]]:
    candidates: dict[str, list[_EvidenceCandidate]] = {
        "proposition_support": [],
        "explicit_contradiction": [],
    }
    for count in range(1, min(4, len(selectors)) + 1):
        for selected in combinations(selectors, count):
            canonical_selected = tuple(
                sorted(selected, key=canonical_selector_sort_key)
            )
            for relation, destination in candidates.items():
                analysis = canonical_evidence_set_analysis(
                    question,
                    canonical_selected,
                    required_slots,
                    polarity_relation=relation,
                )
                if analysis["valid"] is True:
                    destination.append(
                        (
                            _evidence_set_rank(canonical_selected, analysis),
                            canonical_selected,
                            analysis,
                        )
                    )
    return candidates["proposition_support"], candidates["explicit_contradiction"]


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
            sorted(semantic_content_token_set(proposition.object_surface))
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
    reason = _structural_reason(ordered, required_slots)
    required_object_tokens = semantic_content_token_set(proposition.object_surface)
    covered_object_tokens = _covered_object_tokens(
        ordered,
        required_object_tokens,
    )
    no_semantics = qasper_no_evidence_set_analysis(question, ordered)
    if not reason and polarity_relation == "explicit_contradiction":
        if no_semantics["admissible_as_explicit_contradiction"] is not True:
            reason = "explicit_contradiction_missing"
        elif no_semantics["classification"] in {
            "partial_scope_only",
            "role_incompatibility",
        }:
            covered_object_tokens = set(required_object_tokens)
    if not reason and covered_object_tokens != required_object_tokens:
        reason = "object_coverage_incomplete"
    if not reason and not _quantifier_attachment_valid(
        proposition,
        ordered,
        required_object_tokens,
    ):
        reason = "quantifier_attachment_invalid"
    if not reason and not _event_binding_valid(ordered, no_semantics):
        reason = "event_binding_inconsistent"
    if not reason and not _predicate_argument_binding_valid(
        ordered,
        required_slots,
        required_object_tokens,
        no_semantics,
    ):
        reason = "predicate_argument_binding_incomplete"
    if not reason and polarity_relation == "proposition_support":
        if no_semantics["admissible_as_explicit_contradiction"] is True:
            reason = "support_conflicts_with_explicit_contradiction"
        elif not qasper_support_evidence_binding_complete(question, ordered):
            reason = "support_role_binding_incomplete"
        elif not _affirmative_relation_present(ordered):
            reason = "support_relation_unresolved"
    event_binding_id = _event_binding_id(proposition, ordered)
    return {
        "valid": not reason,
        "reason": reason,
        "required_object_tokens": tuple(sorted(required_object_tokens)),
        "covered_object_tokens": tuple(sorted(covered_object_tokens)),
        "event_binding_id": event_binding_id,
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


def _best_candidate(
    candidates: list[
        tuple[tuple[Any, ...], tuple[dict[str, Any], ...], dict[str, Any]]
    ],
) -> tuple[tuple[dict[str, Any], ...] | None, dict[str, Any]]:
    if not candidates:
        return None, {}
    _rank, selected, analysis = min(candidates, key=lambda value: value[0])
    return selected, analysis


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
        -anchor_slot_count,
        0 if analysis.get("same_event") is True else 1,
        len(selected),
        tuple(canonical_selector_sort_key(selector) for selector in selected),
    )


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
    payload: dict[str, Any] = {
        "proposition_id": proposition.proposition_id,
        "event_binding_id": event_binding_id,
        "polarity_relation": relation,
        "span_refs": span_refs,
        "slot_refs": slot_refs,
        "required_object_tokens": required_object_tokens,
        "covered_object_tokens": covered_object_tokens,
    }
    return CanonicalEvidenceSetPlan(
        plan_id=_digest(payload),
        event_binding_id=event_binding_id,
        polarity_relation=relation,
        span_refs=span_refs,
        slot_refs=slot_refs,
        required_object_tokens=required_object_tokens,
        covered_object_tokens=covered_object_tokens,
    )


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


def _event_binding_valid(
    selected: Sequence[Mapping[str, Any]],
    no_semantics: Mapping[str, Any],
) -> bool:
    if no_semantics.get("classification") in {
        "partial_scope_only",
        "role_incompatibility",
    }:
        return True
    if no_semantics.get("classification") == "explicit_negation":
        relation_events = {
            str(selector.get("event_id") or "")
            for selector in selected
            if set(selector.get("slot_hints") or [])
            & {"predicate", "object", "quantifier"}
        }
        evidence_ids = {str(selector.get("evidence_id") or "") for selector in selected}
        if len(relation_events) == 1 and len(evidence_ids) == 1:
            return True
    event_ids = _event_ids(selected)
    if len(event_ids) <= 1:
        return True
    # Lexical overlap between two clauses is not an event identity.  A plan may
    # compose exact spans within one canonical event, while explicit partial-
    # scope and role-incompatibility contradictions are handled above because
    # their semantics necessarily compare two locally auditable bindings.
    return False


def _predicate_argument_binding_valid(
    selected: Sequence[Mapping[str, Any]],
    required_slots: Sequence[str],
    required_object_tokens: set[str],
    no_semantics: Mapping[str, Any],
) -> bool:
    if no_semantics.get("classification") in {
        "partial_scope_only",
        "role_incompatibility",
    }:
        return True
    if len(_event_ids(selected)) <= 1:
        return True
    alias_anchors = [
        selector
        for selector in selected
        if "predicate" in (selector.get("slot_hints") or [])
        and selector.get("predicate_match_kind") == "alias"
    ]
    if not alias_anchors:
        return True
    required = set(required_slots)
    return any(
        required <= set(anchor.get("slot_hints") or [])
        and required_object_tokens <= set(anchor.get("object_tokens") or [])
        for anchor in alias_anchors
    )


def _affirmative_relation_present(selected: Sequence[Mapping[str, Any]]) -> bool:
    for selector in selected:
        if "predicate" not in (selector.get("slot_hints") or []):
            continue
        state = str(selector.get("local_relation_state") or "")
        if state == "affirmative_assertion":
            return True
        if state == "explicit_contradiction":
            continue
        if not _NEGATION_RE.search(str(selector.get("text") or "")):
            return True
    return False


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


def _event_binding_id(
    proposition: QuestionProposition,
    selected: Sequence[Mapping[str, Any]],
) -> str:
    return _digest(
        {
            "proposition_id": proposition.proposition_id,
            "event_ids": sorted(_event_ids(selected)),
            "span_refs": [
                str(selector.get("selector_id") or "") for selector in selected
            ],
            "slot_refs": _slot_refs(selected),
        }
    )


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
