from __future__ import annotations

import re
from typing import Any

from .boolean_evidence_scope import validate_boolean_scope
from .boolean_proposition_conditions import without_target_has_negative_outcome
from .boolean_proposition_polarity import evidence_polarity
from .boolean_relations import (
    boolean_relation_lemmas,
    boolean_relations_align,
    primary_boolean_relation,
)


def resolve_proposition_polarity(
    question: str,
    span: str,
    context: str,
    qualifier: str,
    desired_polarity: str,
    *,
    context_matches: bool,
    span_matches: bool,
    qualifier_is_local: bool,
) -> str:
    contextual_qualifier = qualifier in {
        "limited_information",
        "non_significant",
        "not_required",
        "required_condition",
    } or (
        qualifier in {"small", "minor", "marginal"}
        and re.search(r"^\s*overall\b", question, re.IGNORECASE)
    )
    polarity_text = (
        context
        if contextual_qualifier
        and context_matches
        and (not qualifier_is_local or not span_matches)
        else span
    )
    return evidence_polarity(
        question,
        polarity_text,
        desired_polarity=desired_polarity,
    )


def closed_alternative_object_score(
    question: str,
    item: dict[str, Any],
    span: str,
    evidence_polarity: str,
    quantifier: str,
    object_score: float,
) -> float:
    if object_score >= 0.6 or quantifier != "other":
        return object_score
    if evidence_polarity not in {"yes", "no"}:
        return object_score
    decision = validate_boolean_scope(
        question,
        span,
        evidence_polarity,
        evidence_items=[item],
    )
    return 1.0 if decision.scope_valid else object_score


def question_aligned_relation(question: str, span: str, context: str) -> str:
    target = primary_boolean_relation(question)
    if target == "attribute":
        return target
    if (
        target in boolean_relation_lemmas(context)
        or boolean_relations_align(question, context)
        or without_target_has_negative_outcome(question, context)
    ):
        return target
    return primary_boolean_relation(span) or primary_boolean_relation(context)
