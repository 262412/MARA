from __future__ import annotations

from typing import Any

from .boolean_evidence_scope import (
    _actor,
    _closed_quantifier,
    _requires_current_paper_scope,
    _section_role,
)
from .boolean_proposition_compatibility import _object_compatibility
from .boolean_proposition_evidence import classify_boolean_evidence_candidates
from .boolean_proposition_polarity import answer_polarity as _answer_polarity
from .boolean_proposition_qualifiers import proposition_qualifier
from .boolean_proposition_schema import BooleanEvidenceAssessment
from .boolean_relations import primary_boolean_relation
from .evidence_identity import identity_of
from .query_phrase_extraction import semantic_boolean_proposition_question


def boolean_proposition_binding_trace(
    question: str,
    answer: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    semantic_question = semantic_boolean_proposition_question(question)
    question_relation = primary_boolean_relation(semantic_question)
    question_object = _object_compatibility(semantic_question, semantic_question)[1]
    question_actor = (
        "current_paper"
        if _requires_current_paper_scope(question)
        else _actor(question, _section_role({}, question))
    )
    candidates = [
        assessment
        for item in items
        for assessment in classify_boolean_evidence_candidates(question, answer, item)
    ]
    supports = [value for value in candidates if value.classification == "supports"]
    contradictions = [
        value for value in candidates if value.classification == "contradicts"
    ]
    rejected = [
        value
        for value in candidates
        if value.classification in {"unrelated", "insufficient_scope"}
    ]
    return {
        "question_proposition": {
            "actor": question_actor,
            "predicate": question_relation,
            "relation": question_relation,
            "object": question_object,
            "scope": (
                "current_paper" if question_actor == "current_paper" else "document"
            ),
            "polarity": _answer_polarity(answer),
            "qualifier": proposition_qualifier(semantic_question),
            "quantifier": _closed_quantifier(semantic_question),
        },
        "proposition_candidate_ids": [value.span_id for value in candidates],
        "normalized_relation": question_relation,
        "relation_match_reason": (
            "normalized_relation_family_match" if supports or contradictions else ""
        ),
        "proposition_candidates": [_assessment_trace(value) for value in candidates],
        "bound_support_span_ids": [value.span_id for value in supports],
        "bound_contradiction_span_ids": [value.span_id for value in contradictions],
        "bound_support_evidence_ids": _assessment_evidence_ids(supports),
        "bound_contradiction_evidence_ids": _assessment_evidence_ids(contradictions),
        "rejected_candidates": [_assessment_trace(value) for value in rejected],
        "final_support_evidence_ids": _assessment_evidence_ids(supports),
        "final_contradiction_evidence_ids": _assessment_evidence_ids(contradictions),
        "binding_status": "filled" if supports else "missing",
    }


def _assessment_trace(value: BooleanEvidenceAssessment) -> dict[str, Any]:
    assessment = value.as_dict()
    return {
        **assessment,
        "proposition_candidate_id": value.span_id,
        "span": value.span_text,
        "normalized_relation": value.proposition.action,
        "relation_match_reason": (
            "normalized_relation_family_match"
            if value.relation_score > 0
            else "normalized_relation_mismatch"
        ),
    }


def _assessment_evidence_ids(
    values: list[BooleanEvidenceAssessment],
) -> list[str]:
    return list(dict.fromkeys(identity_of(value.item).key for value in values))
