from __future__ import annotations

import re
from typing import Any

from .boolean_current_experiment import (
    current_experiment_slot_score,
    is_current_experiment_question,
    is_direct_current_empirical_action,
)
from .boolean_evidence_scope import (
    _actor,
    _closed_quantifier,
    _english_closed_scope,
    _has_closed_quantifier,
    _language_data_question,
    _non_english_counterexample,
    _prior_work_scope_question,
    _requires_current_paper_scope,
    _scope_rejection,
    _section_role,
    evidence_item_text,
    validate_boolean_scope,
)
from .boolean_proposition_context import (
    actor_scope_scores,
    bounded_proposition_context,
    contextual_actor,
    normalized_object_tokens,
    proposition_spans,
)
from .boolean_proposition_context import semantic_resolution_text as _resolution_text
from .boolean_proposition_polarity import answer_polarity as _answer_polarity
from .boolean_proposition_polarity import evidence_polarity as _evidence_polarity
from .boolean_proposition_qualifiers import proposition_qualifier
from .boolean_proposition_schema import (
    BooleanEvidenceAssessment,
    BooleanEvidenceSet,
    BooleanProposition,
)
from .boolean_proposition_tokens import _content_tokens, _relation_surface_tokens
from .boolean_quality_control_evidence import quality_control_evidence_kind
from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation
from .evidence_identity import identity_of
from .query_phrase_extraction import semantic_boolean_proposition_question


def classify_boolean_evidence(
    question: str,
    answer: str,
    item: dict[str, Any],
) -> BooleanEvidenceAssessment:
    assessments = list(classify_boolean_evidence_candidates(question, answer, item))
    if not assessments:
        text = evidence_item_text(item)
        assessments = [
            _assess_proposition_span(
                question,
                _answer_polarity(answer),
                item,
                text,
                span_index=1,
            )
        ]
    return max(assessments, key=_assessment_rank)


def classify_boolean_evidence_candidates(
    question: str,
    answer: str,
    item: dict[str, Any],
) -> tuple[BooleanEvidenceAssessment, ...]:
    desired_polarity = _answer_polarity(answer)
    spans = proposition_spans(question, evidence_item_text(item))
    assessments = tuple(
        _assess_proposition_span(
            question,
            desired_polarity,
            item,
            span,
            span_index=index,
        )
        for index, span in enumerate(spans, start=1)
    )
    return _deduplicated_assessments(assessments)


def _assess_proposition_span(
    question: str,
    desired_polarity: str,
    item: dict[str, Any],
    span: str,
    *,
    span_index: int,
) -> BooleanEvidenceAssessment:
    (
        proposition,
        section_role,
        scope_rejection,
        relation_score,
        object_score,
    ) = _proposition_frame(question, desired_polarity, item, span)
    actor_score, scope_score = actor_scope_scores(
        proposition.actor,
        question,
        section_role,
        scope_rejection,
    )
    classification, reason = _classify_proposition_span(
        question,
        desired_polarity,
        proposition.polarity,
        item,
        span,
        actor=proposition.actor,
        section_role=section_role,
        quantifier=proposition.quantifier,
        relation_score=relation_score,
        object_score=object_score,
        scope_rejection=scope_rejection,
    )
    return BooleanEvidenceAssessment(
        item=item,
        classification=classification,
        proposition=proposition,
        relation_score=relation_score,
        object_score=object_score,
        reason=reason,
        span_id=f"{identity_of(item).key}#proposition:{span_index}",
        span_text=span,
        actor_score=actor_score,
        scope_score=scope_score,
    )


def _proposition_frame(
    question: str,
    desired_polarity: str,
    item: dict[str, Any],
    span: str,
) -> tuple[BooleanProposition, str, str, float, float]:
    semantic_question = semantic_boolean_proposition_question(question)
    context = bounded_proposition_context(
        evidence_item_text(item),
        span,
        question=semantic_question,
    )
    resolution_text = _resolution_text(semantic_question, span, context)
    section_role = _section_role(item, span)
    actor = contextual_actor(span, context, section_role)
    quantifier = _closed_quantifier(semantic_question)
    qualifier = proposition_qualifier(context)
    polarity_text = (
        context
        if qualifier in {"non_significant", "not_required"}
        and _context_matches_proposition(semantic_question, context)
        else span
    )
    evidence_polarity = _evidence_polarity(
        semantic_question,
        polarity_text,
        desired_polarity=desired_polarity,
    )
    relation_score = _relation_compatibility(semantic_question, resolution_text)
    object_score, proposition_object = _object_compatibility(
        semantic_question,
        resolution_text,
    )
    proposition = BooleanProposition(
        actor=actor,
        action=(
            primary_boolean_relation(span) or primary_boolean_relation(resolution_text)
        ),
        object=proposition_object,
        section_scope=(
            "current_paper"
            if actor == "current_paper"
            and semantic_question != str(question or "").strip()
            else section_role
        ),
        polarity=evidence_polarity,
        quantifier=quantifier,
        qualifier=qualifier,
    )
    scope_rejection = _scope_rejection(
        question,
        actor=actor,
        section_role=section_role,
        structured_scope_available=True,
        quote=span,
    )
    if (
        not scope_rejection
        and is_current_experiment_question(question)
        and not is_direct_current_empirical_action(span)
    ):
        scope_rejection = "current_experiment_action_not_established"
    return proposition, section_role, scope_rejection, relation_score, object_score


def _deduplicated_assessments(
    assessments: tuple[BooleanEvidenceAssessment, ...],
) -> tuple[BooleanEvidenceAssessment, ...]:
    output: dict[tuple[str, tuple[str, ...]], BooleanEvidenceAssessment] = {}
    for assessment in assessments:
        key = (assessment.classification, assessment.proposition.key)
        current = output.get(key)
        if current is None or _assessment_rank(assessment) > _assessment_rank(current):
            output[key] = assessment
    return tuple(output.values())


def _classify_proposition_span(
    question: str,
    desired_polarity: str,
    evidence_polarity: str,
    item: dict[str, Any],
    span: str,
    *,
    actor: str,
    section_role: str,
    quantifier: str,
    relation_score: float,
    object_score: float,
    scope_rejection: str,
) -> tuple[str, str]:
    if (
        (actor in {"cited_work", "other_authors"} or section_role == "related_work")
        and not _prior_work_scope_question(question)
        or section_role == "future_work"
        or scope_rejection
    ):
        classification = "insufficient_scope"
        reason = scope_rejection or f"excluded_{section_role or actor}_scope"
    elif relation_score <= 0 or object_score < 0.6:
        classification = "unrelated"
        reason = "claim_relation_or_object_incompatible"
    elif (
        quantifier != "none"
        and not validate_boolean_scope(
            question,
            span,
            evidence_polarity or desired_polarity,
            evidence_items=[item],
        ).scope_valid
    ):
        classification = "unrelated"
        reason = "quantified_object_scope_incomplete"
    elif not desired_polarity or not evidence_polarity:
        classification = "unrelated"
        reason = "missing_typed_polarity"
    elif desired_polarity == evidence_polarity:
        classification = "supports"
        reason = "claim_scope_relation_and_polarity_compatible"
    else:
        classification = "contradicts"
        reason = "scope_valid_opposite_proposition"
    return classification, reason


def _assessment_rank(assessment: BooleanEvidenceAssessment) -> tuple[int, float, float]:
    class_rank = {
        "supports": 3,
        "contradicts": 3,
        "insufficient_scope": 2,
        "unrelated": 1,
    }
    return (
        class_rank[assessment.classification],
        assessment.relation_score * assessment.object_score,
        assessment.object_score,
    )


def classify_boolean_evidence_set(
    question: str,
    answer: str,
    items: list[dict[str, Any]],
) -> BooleanEvidenceSet:
    grouped: dict[str, list[BooleanEvidenceAssessment]] = {
        "supports": [],
        "contradicts": [],
        "unrelated": [],
        "insufficient_scope": [],
    }
    for item in items:
        assessments = classify_boolean_evidence_candidates(question, answer, item) or (
            classify_boolean_evidence(question, answer, item),
        )
        for assessment in assessments:
            grouped[assessment.classification].append(assessment)
    return BooleanEvidenceSet(
        supports=tuple(grouped["supports"]),
        contradicts=tuple(grouped["contradicts"]),
        unrelated=tuple(grouped["unrelated"]),
        insufficient_scope=tuple(grouped["insufficient_scope"]),
    )


def boolean_proposition_evidence_score(
    question: str,
    item: dict[str, Any],
) -> float:
    question = semantic_boolean_proposition_question(question)
    text = evidence_item_text(item)
    if not text:
        return 0.0
    quality_kind = quality_control_evidence_kind(question, text)
    if quality_kind == "quality_validation":
        return 3.0
    if quality_kind == "annotation_artifact_control":
        return 1.0
    current_experiment_score = current_experiment_slot_score(question, item)
    if current_experiment_score is not None:
        return current_experiment_score
    assessments = classify_boolean_evidence_candidates(question, "", item)
    compatible = [
        assessment
        for assessment in assessments
        if assessment.actor_score > 0
        and assessment.scope_score > 0
        and assessment.relation_score > 0
        and assessment.object_score >= 0.6
    ]
    if not compatible:
        return 0.0
    assessment = max(compatible, key=_assessment_rank)
    section_role = assessment.proposition.section_scope
    actor = assessment.proposition.actor
    if _language_data_question(question) and _has_closed_quantifier(question):
        return 2.0 + assessment.object_score
    if re.search(r"\b(?:experiment|evaluate|test|task)\w*\b", question.lower()):
        if actor == "current_paper" and section_role in {
            "experiments",
            "methods",
            "results",
        }:
            return 1.0 + assessment.relation_score + assessment.object_score
        return 0.0
    question_tokens = _proposition_content_tokens(question)
    evidence_tokens = _content_tokens(text)
    if not question_tokens:
        return 0.0
    coverage = len(question_tokens & evidence_tokens) / len(question_tokens)
    if coverage < 0.35:
        return 0.0
    return 1.0 + coverage + 0.5 * assessment.relation_score


def boolean_proposition_authority_level(
    question: str,
    item: dict[str, Any],
) -> str:
    """Classify retrieval support before answer-specific verification."""

    question = semantic_boolean_proposition_question(question)
    text = evidence_item_text(item)
    if not text:
        return "none"
    quality_kind = quality_control_evidence_kind(question, text)
    if quality_kind == "annotation_artifact_control":
        return "partial"
    return (
        "complete" if boolean_proposition_evidence_score(question, item) > 0 else "none"
    )


def _proposition_content_tokens(value: str) -> set[str]:
    relation_tokens = {
        token
        for relation in boolean_relation_lemmas(value)
        for token in _relation_surface_tokens(relation)
    }
    return (
        _content_tokens(value)
        - relation_tokens
        - {
            "author",
            "authors",
            "paper",
            "study",
            "work",
        }
    )


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
    return {
        "proposition_candidate_id": value.span_id,
        "evidence_id": identity_of(value.item).key,
        "span": value.span_text,
        "normalized_relation": value.proposition.action,
        "predicate": value.proposition.predicate,
        "actor": value.proposition.actor,
        "object": value.proposition.object,
        "qualifier": value.proposition.qualifier,
        "quantifier": value.proposition.quantifier,
        "scope": value.proposition.scope,
        "relation_match_reason": (
            "normalized_relation_family_match"
            if value.relation_score > 0
            else "normalized_relation_mismatch"
        ),
        "actor_score": value.actor_score,
        "scope_score": value.scope_score,
        "object_score": value.object_score,
        "polarity": value.proposition.polarity,
        "classification": value.classification,
        "reason": value.reason,
    }


def _context_matches_proposition(question: str, context: str) -> bool:
    relation_score = _relation_compatibility(question, context)
    object_score, _object = _object_compatibility(question, context)
    return relation_score > 0 and object_score >= 0.6


def _assessment_evidence_ids(
    values: list[BooleanEvidenceAssessment],
) -> list[str]:
    return list(dict.fromkeys(identity_of(value.item).key for value in values))


def _relation_compatibility(question: str, text: str) -> float:
    if _language_data_question(question) and _has_closed_quantifier(question):
        if _english_closed_scope(text) or _non_english_counterexample(text):
            return 1.0
    question_relations = boolean_relation_lemmas(question)
    evidence_relations = boolean_relation_lemmas(text)
    if not question_relations:
        return 1.0
    if question_relations & evidence_relations:
        return 1.0
    return 0.0


def _object_compatibility(question: str, text: str) -> tuple[float, str]:
    question_relations = boolean_relation_lemmas(question)
    evidence_relations = boolean_relation_lemmas(text)
    relation_tokens = {
        token
        for relation in question_relations | evidence_relations
        for token in _relation_surface_tokens(relation)
    }
    question_tokens = normalized_object_tokens(question, relation_tokens)
    evidence_tokens = normalized_object_tokens(text, relation_tokens)
    question_tokens.discard("")
    evidence_tokens.discard("")
    if (
        "task" in question_tokens
        and re.search(r"\b(?:these|those|aforementioned)\s+tasks?\b", question, re.I)
        and evidence_relations
        and evidence_tokens
    ):
        return 1.0, "deictic_task_set"
    if not question_tokens:
        return 1.0, ""
    proposition_object = " ".join(sorted(question_tokens))
    if _language_data_question(question) and _has_closed_quantifier(question):
        if _english_closed_scope(text) or _non_english_counterexample(text):
            return 1.0, proposition_object
    shared = question_tokens & evidence_tokens
    score = len(shared) / len(question_tokens)
    return score, proposition_object


def boolean_proposition_object_identity(question: str) -> str:
    """Return the normalized object/argument identity required by a question."""

    return _object_compatibility(question, question)[1]
