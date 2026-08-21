from __future__ import annotations

import re
from typing import Any

from .boolean_evidence_scope import _prior_work_scope_question, evidence_item_text
from .boolean_proposition_conditions import non_authoritative_proposition_span
from .boolean_proposition_evidence import (
    _assessment_rank,
    _proposition_content_tokens,
    boolean_proposition_authority_level,
    classify_boolean_evidence_candidates,
)
from .boolean_proposition_tokens import _content_tokens
from .boolean_quality_control_evidence import quality_control_evidence_kind
from .boolean_retrieval_queries import boolean_retrieval_query
from .boolean_structured_authority import structured_boolean_authority
from .query_phrase_extraction import semantic_boolean_proposition_question


def boolean_proposition_candidate_score(
    question: str,
    item: dict[str, Any],
    *,
    metric: str = "",
    classified_candidates: tuple[Any, ...] | None = None,
) -> float:
    """Rank local proposition candidates without asserting authority."""

    combined_question = " ".join(
        value for value in (question, metric) if str(value or "").strip()
    )
    context_question = _normalize_requirement_terms(combined_question)
    proposition_question = semantic_boolean_proposition_question(
        _normalize_requirement_terms(_semantic_proposition_question(question, metric))
    )
    candidate_item = _normalized_requirement_item(item)
    text = evidence_item_text(candidate_item)
    if not text:
        return 0.0
    quality_score = _quality_candidate_score(
        context_question,
        proposition_question,
        text,
    )
    if quality_score is not None:
        return quality_score
    if structured_boolean_authority(proposition_question, candidate_item) is not None:
        return 3.0
    assessments = (
        classified_candidates
        if classified_candidates is not None
        else classify_boolean_evidence_candidates(
            proposition_question,
            "",
            candidate_item,
        )
    )
    compatible = _compatible_candidates(
        assessments,
        context_question=context_question,
        evidence_text=text,
    )
    if not compatible:
        return 0.0
    assessment = max(compatible, key=_assessment_rank)
    context_tokens = _proposition_content_tokens(context_question)
    evidence_tokens = _content_tokens(text)
    context_coverage = (
        len(context_tokens & evidence_tokens) / len(context_tokens)
        if context_tokens
        else 0.0
    )
    return (
        1.0
        + assessment.relation_score
        + assessment.object_score
        + (0.25 * context_coverage)
    )


def boolean_proposition_selection_assessment(
    question: str,
    item: dict[str, Any],
    *,
    metric: str = "",
) -> tuple[float, str]:
    """Compute selection relevance and authority from one typed classification."""

    proposition_question = semantic_boolean_proposition_question(
        _normalize_requirement_terms(_semantic_proposition_question(question, metric))
    )
    candidate_item = _normalized_requirement_item(item)
    classified = classify_boolean_evidence_candidates(
        proposition_question,
        "",
        candidate_item,
    )
    score = boolean_proposition_candidate_score(
        question,
        candidate_item,
        metric=metric,
        classified_candidates=classified,
    )
    authority_level = boolean_proposition_authority_level(
        proposition_question,
        candidate_item,
        classified_candidates=classified,
    )
    return score, authority_level


def _quality_candidate_score(
    context_question: str,
    proposition_question: str,
    text: str,
) -> float | None:
    quality_kind = quality_control_evidence_kind(context_question, text)
    if not quality_kind:
        quality_kind = quality_control_evidence_kind(proposition_question, text)
    if quality_kind == "quality_validation":
        return 3.0
    if quality_kind == "annotation_artifact_control":
        return 1.0
    return None


def _compatible_candidates(
    assessments: tuple[Any, ...],
    *,
    context_question: str,
    evidence_text: str,
) -> list[Any]:
    prior_work_scope = _prior_work_scope_question(context_question)
    requirement_context = bool(_REQUIREMENT_CONTEXT_RE.search(context_question))
    requirement_evidence = bool(_REQUIREMENT_CONTEXT_RE.search(evidence_text))
    minimum_object_score = 0.2 if requirement_context and requirement_evidence else 0.6
    return [
        assessment
        for assessment in assessments
        if assessment.relation_score > 0
        and assessment.object_score >= minimum_object_score
        and (
            prior_work_scope
            or assessment.proposition.actor not in {"cited_work", "other_authors"}
        )
        and (
            prior_work_scope
            and assessment.proposition.section_scope != "future_work"
            or assessment.proposition.section_scope
            not in {"related_work", "future_work"}
        )
        and not non_authoritative_proposition_span(
            context_question,
            assessment.span_text,
        )
    ]


_REQUIREMENT_TERM_RE = re.compile(r"\brequirements?\b", re.IGNORECASE)
_REQUIREMENT_CONTEXT_RE = re.compile(
    r"\b(?:require|required|requires|requirement|requirements|necessary|must)\b",
    re.IGNORECASE,
)


def _semantic_proposition_question(question: str, metric: str) -> str:
    """Use the compact metric when ``question`` is a retrieval expansion."""

    question_text = str(question or "").strip()
    metric_text = str(metric or "").strip()
    if (
        metric_text
        and question_text
        and question_text != boolean_retrieval_query(question_text)
    ):
        return metric_text
    return question_text or metric_text


def _normalize_requirement_terms(value: str) -> str:
    return _REQUIREMENT_TERM_RE.sub("require", str(value or ""))


def _normalized_requirement_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    for field in ("text", "ocr_text", "vlm_text", "caption"):
        if field in normalized:
            normalized[field] = _normalize_requirement_terms(normalized[field])
    return normalized
