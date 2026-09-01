from __future__ import annotations

import re
from typing import Any

from .boolean_current_experiment import is_current_experiment_question
from .boolean_empirical_actions import empirical_action_present
from .boolean_evidence_scope import (
    _closed_quantifier,
    _has_closed_quantifier,
    _language_data_question,
    _prior_work_scope_question,
    _section_role,
    evidence_item_text,
    validate_boolean_scope,
)
from .boolean_proposition_actor import proposition_scope_rejection
from .boolean_proposition_compatibility import (
    _object_compatibility,
    _relation_compatibility,
)
from .boolean_proposition_conditions import non_authoritative_proposition_span
from .boolean_proposition_context import (
    actor_scope_scores,
    bounded_proposition_context,
    contextual_actor,
    proposition_spans,
)
from .boolean_proposition_context import semantic_resolution_text as _resolution_text
from .boolean_proposition_polarity import answer_polarity as _answer_polarity
from .boolean_proposition_polarity import attribute_predicate_is_asserted
from .boolean_proposition_qualifiers import proposition_qualifier
from .boolean_proposition_resolution import (
    closed_alternative_object_score,
    question_aligned_relation,
    resolve_proposition_polarity,
)
from .boolean_proposition_schema import (
    BooleanEvidenceAssessment,
    BooleanEvidenceSet,
    BooleanProposition,
)
from .boolean_proposition_tokens import _content_tokens, _relation_surface_tokens
from .boolean_quality_control_evidence import quality_control_evidence_kind
from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation
from .boolean_structured_authority import structured_boolean_authority
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
        candidate_relevance=_candidate_relevance(
            classification,
            relation_score=relation_score,
            object_score=object_score,
            actor_score=actor_score,
            scope_score=scope_score,
        ),
    )


def _candidate_relevance(
    classification: str,
    *,
    relation_score: float,
    object_score: float,
    actor_score: float,
    scope_score: float,
) -> bool:
    return bool(
        classification != "insufficient_scope"
        and relation_score > 0
        and object_score >= 0.6
        and actor_score > 0
        and scope_score > 0
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
    actor = _resolved_actor(semantic_question, item, span, context, section_role)
    quantifier = _closed_quantifier(semantic_question)
    span_matches = _context_matches_proposition(semantic_question, span)
    span_qualifier = proposition_qualifier(span, question=semantic_question)
    context_qualifier = proposition_qualifier(
        context,
        question=semantic_question,
    )
    qualifier = _resolved_qualifier(
        question,
        span_qualifier,
        context_qualifier,
        span_matches=span_matches,
    )
    evidence_polarity = resolve_proposition_polarity(
        question,
        span,
        context,
        qualifier,
        desired_polarity,
        context_matches=_context_matches_proposition(semantic_question, context),
        span_matches=span_matches,
        qualifier_is_local=(span_qualifier != "none" and qualifier == span_qualifier),
    )
    relation_score = _relation_compatibility(semantic_question, resolution_text)
    object_score, proposition_object = _object_compatibility(
        semantic_question,
        # A bounded context is an exact, continuous evidence window.  It may
        # complete a proposition split across adjacent sentences (for example
        # a setup sentence followed by a qualified result), while unrelated
        # question nouns still cannot enter because ``_object_compatibility``
        # requires evidence-side tokens.
        resolution_text,
    )
    object_score = closed_alternative_object_score(
        question,
        item,
        span,
        evidence_polarity,
        quantifier,
        object_score,
    )
    proposition = BooleanProposition(
        actor=actor,
        action=question_aligned_relation(semantic_question, span, resolution_text),
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
    scope_rejection = proposition_scope_rejection(
        question,
        span,
        context,
        actor=actor,
        section_role=section_role,
    )
    return proposition, section_role, scope_rejection, relation_score, object_score


def _resolved_actor(
    question: str,
    item: dict[str, Any],
    span: str,
    context: str,
    section_role: str,
) -> str:
    return contextual_actor(
        span,
        context,
        section_role,
        question=question,
        document_text=evidence_item_text(item),
    )


def _deduplicated_assessments(
    assessments: tuple[BooleanEvidenceAssessment, ...],
) -> tuple[BooleanEvidenceAssessment, ...]:
    output: dict[
        tuple[str, tuple[str, ...], str],
        BooleanEvidenceAssessment,
    ] = {}
    for assessment in assessments:
        key = (
            assessment.classification,
            assessment.proposition.key,
            assessment.span_id,
        )
        current = output.get(key)
        if current is None or _assessment_rank(assessment) > _assessment_rank(current):
            output[key] = assessment
    return tuple(output.values())


def _resolved_qualifier(
    question: str,
    span_qualifier: str,
    context_qualifier: str,
    *,
    span_matches: bool,
) -> str:
    if re.search(r"^\s*overall\b", question, re.IGNORECASE):
        priority = {
            "none": 0,
            "minor": 1,
            "marginal": 1,
            "small": 1,
            "limited_information": 2,
            "non_significant": 3,
            "not_required": 4,
            "required_condition": 4,
        }
        if priority.get(context_qualifier, 0) > priority.get(span_qualifier, 0):
            return context_qualifier
    if span_qualifier != "none":
        return span_qualifier
    return "none" if span_matches else context_qualifier


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
    if non_authoritative_proposition_span(question, span):
        classification = "insufficient_scope"
        reason = "prospective_proposition_not_current_authority"
    elif (
        (actor in {"cited_work", "other_authors"} or section_role == "related_work")
        and not _prior_work_scope_question(question)
        or section_role == "future_work"
        or scope_rejection
    ):
        classification = "insufficient_scope"
        reason = scope_rejection or f"excluded_{section_role or actor}_scope"
    elif not exact_span_asserts_boolean_relation(question, span):
        classification = "unrelated"
        reason = "target_relation_not_asserted_in_exact_span"
    elif _metalinguistic_relation_mention(question, span):
        classification = "unrelated"
        reason = "target_relation_mentioned_but_not_asserted"
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


def exact_span_asserts_boolean_relation(question: str, span: str) -> bool:
    """Return whether the exact span asserts a compatible Boolean relation."""

    semantic_question = semantic_boolean_proposition_question(question)
    target = primary_boolean_relation(semantic_question)
    if not target:
        return False
    if target == "attribute":
        return bool(
            attribute_predicate_is_asserted(semantic_question, span)
            or re.search(r"\b(?:is|are|was|were|has|have|with)\b", span, re.I)
            or boolean_relation_lemmas(span)
            & {"contain", "create", "evaluate", "provide", "train", "use"}
        )
    return _relation_compatibility(semantic_question, span) > 0


def exact_span_completes_boolean_proposition(question: str, span: str) -> bool:
    """Return whether authority can use the exact span without context fill."""

    semantic_question = semantic_boolean_proposition_question(question)
    object_score, _object = _object_compatibility(semantic_question, span)
    return bool(
        exact_span_asserts_boolean_relation(semantic_question, span)
        and object_score >= 0.6
    )


def _metalinguistic_relation_mention(question: str, span: str) -> bool:
    relation = primary_boolean_relation(question)
    if not relation:
        return False
    surfaces = sorted(_relation_surface_tokens(relation), key=len, reverse=True)
    relation_pattern = "|".join(re.escape(value) for value in surfaces)
    return bool(
        re.search(
            rf"\b(?:{relation_pattern})\s+"
            r"(?:assertion|claim|description|discussion|mention|statement)\b",
            str(span or ""),
            flags=re.IGNORECASE,
        )
    )


def _assessment_rank(
    assessment: BooleanEvidenceAssessment,
) -> tuple[int, int, float, float]:
    class_rank = {
        "supports": 3,
        "contradicts": 3,
        "insufficient_scope": 2,
        "unrelated": 1,
    }
    empirical_action = int(
        assessment.proposition.action == "evaluate"
        and empirical_action_present(assessment.span_text)
    )
    return (
        class_rank[assessment.classification],
        empirical_action,
        assessment.relation_score * assessment.object_score,
        assessment.object_score,
    )


def classify_boolean_evidence_set(
    question: str,
    answer: str,
    items: list[dict[str, Any]],
    *,
    preserve_support_spans: bool = False,
) -> BooleanEvidenceSet:
    """Classify evidence, retaining exact support spans only when requested."""

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
    for classification, group_assessments in grouped.items():
        strongest: dict[
            tuple[str, tuple[str, ...], str],
            BooleanEvidenceAssessment,
        ] = {}
        for assessment in group_assessments:
            key = (
                identity_of(assessment.item).key,
                assessment.proposition.key,
                (
                    assessment.span_id
                    if preserve_support_spans
                    and classification in {"supports", "contradicts"}
                    else ""
                ),
            )
            current = strongest.get(key)
            if current is None or (
                _assessment_rank(assessment),
                -len(assessment.span_text),
                assessment.span_id,
            ) > (
                _assessment_rank(current),
                -len(current.span_text),
                current.span_id,
            ):
                strongest[key] = assessment
        grouped[classification] = list(strongest.values())
    return BooleanEvidenceSet(
        supports=tuple(grouped["supports"]),
        contradicts=tuple(grouped["contradicts"]),
        unrelated=tuple(grouped["unrelated"]),
        insufficient_scope=tuple(grouped["insufficient_scope"]),
    )


def boolean_proposition_evidence_score(
    question: str,
    item: dict[str, Any],
    *,
    classified_candidates: tuple[BooleanEvidenceAssessment, ...] | None = None,
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
    if structured_boolean_authority(question, item) is not None:
        return 3.0
    if is_current_experiment_question(question):
        return 0.0
    assessments = (
        classified_candidates
        if classified_candidates is not None
        else classify_boolean_evidence_candidates(question, "", item)
    )
    compatible = [
        assessment for assessment in assessments if assessment.candidate_relevance
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
    *,
    classified_candidates: tuple[BooleanEvidenceAssessment, ...] | None = None,
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
        "complete"
        if boolean_proposition_evidence_score(
            question,
            item,
            classified_candidates=classified_candidates,
        )
        > 0
        else "none"
    )


def boolean_proposition_candidate_authority_level(
    question: str,
    item: dict[str, Any],
    candidate_score: float,
) -> str:
    """Map a cached retrieval assessment to its pre-verification slot state."""

    text = evidence_item_text(item)
    if not text:
        return "none"
    if quality_control_evidence_kind(question, text) == "annotation_artifact_control":
        return "partial"
    return "complete" if candidate_score > 0 else "none"


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
    from .boolean_proposition_trace import boolean_proposition_binding_trace as trace

    return trace(question, answer, items)


def _context_matches_proposition(question: str, context: str) -> bool:
    relation_score = _relation_compatibility(question, context)
    object_score, _object = _object_compatibility(question, context)
    return relation_score > 0 and object_score >= 0.6


def boolean_proposition_object_identity(question: str) -> str:
    """Return the normalized object/argument identity required by a question."""

    return _object_compatibility(question, question)[1]
