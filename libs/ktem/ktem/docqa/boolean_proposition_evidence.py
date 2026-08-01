from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .boolean_evidence_scope import (
    _actor,
    _english_closed_scope,
    _has_closed_quantifier,
    _language_data_question,
    _non_english_counterexample,
    _scope_rejection,
    _section_role,
    evidence_item_text,
)
from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation


@dataclass(frozen=True)
class BooleanProposition:
    actor: str
    action: str
    object: str
    section_scope: str
    polarity: str
    quantifier: str


@dataclass(frozen=True)
class BooleanEvidenceAssessment:
    item: dict[str, Any]
    classification: str
    proposition: BooleanProposition
    relation_score: float
    object_score: float
    reason: str


@dataclass(frozen=True)
class BooleanEvidenceSet:
    supports: tuple[BooleanEvidenceAssessment, ...]
    contradicts: tuple[BooleanEvidenceAssessment, ...]
    unrelated: tuple[BooleanEvidenceAssessment, ...]
    insufficient_scope: tuple[BooleanEvidenceAssessment, ...]


def classify_boolean_evidence(
    question: str,
    answer: str,
    item: dict[str, Any],
) -> BooleanEvidenceAssessment:
    text = evidence_item_text(item)
    section_role = _section_role(item, text)
    actor = _actor(text, section_role)
    quantifier = "only" if _has_closed_quantifier(question) else "none"
    desired_polarity = _answer_polarity(answer)
    evidence_polarity = _evidence_polarity(
        question,
        text,
        desired_polarity=desired_polarity,
    )
    relation_score = _relation_compatibility(question, text)
    object_score, proposition_object = _object_compatibility(question, text)
    proposition = BooleanProposition(
        actor=actor,
        action=primary_boolean_relation(text),
        object=proposition_object,
        section_scope=section_role,
        polarity=evidence_polarity,
        quantifier=quantifier,
    )
    scope_rejection = _scope_rejection(
        question,
        actor=actor,
        section_role=section_role,
        structured_scope_available=True,
    )
    if actor == "cited_work" or section_role == "future_work" or scope_rejection:
        classification = "insufficient_scope"
        reason = scope_rejection or f"excluded_{section_role or actor}_scope"
    elif relation_score <= 0 or object_score < 0.2:
        classification = "unrelated"
        reason = "claim_relation_or_object_incompatible"
    elif not desired_polarity or not evidence_polarity:
        classification = "unrelated"
        reason = "missing_typed_polarity"
    elif desired_polarity == evidence_polarity:
        classification = "supports"
        reason = "claim_scope_relation_and_polarity_compatible"
    else:
        classification = "contradicts"
        reason = "scope_valid_opposite_proposition"
    return BooleanEvidenceAssessment(
        item=item,
        classification=classification,
        proposition=proposition,
        relation_score=relation_score,
        object_score=object_score,
        reason=reason,
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
        assessment = classify_boolean_evidence(question, answer, item)
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
    text = evidence_item_text(item)
    if not text:
        return 0.0
    assessment = classify_boolean_evidence(question, "yes", item)
    if assessment.classification in {"unrelated", "insufficient_scope"}:
        return 0.0
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
    question_tokens = _content_tokens(question)
    evidence_tokens = _content_tokens(text)
    if not question_tokens:
        return 0.0
    coverage = len(question_tokens & evidence_tokens) / len(question_tokens)
    if coverage < 0.35:
        return 0.0
    return 1.0 + coverage + 0.5 * assessment.relation_score


def _answer_polarity(answer: str) -> str:
    normalized = str(answer or "").strip().lower()
    if normalized in {"yes", "true"}:
        return "yes"
    if normalized in {"no", "false"}:
        return "no"
    return ""


def _evidence_polarity(
    question: str,
    text: str,
    *,
    desired_polarity: str,
) -> str:
    if _language_data_question(question) and _has_closed_quantifier(question):
        if _non_english_counterexample(text):
            return "no"
        if _english_closed_scope(text):
            return "yes"
        return ""
    lowered = str(text or "").lower()
    negative = bool(
        re.search(
            r"\b(?:doesn't|does not|don't|do not|did not|no|not|never|without)\b",
            lowered,
        )
    )
    if negative:
        return "no"
    return "yes" if desired_polarity else ""


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
    object_score, _object = _object_compatibility(question, text)
    return 0.6 if object_score >= 0.4 else 0.0


def _object_compatibility(question: str, text: str) -> tuple[float, str]:
    question_relations = boolean_relation_lemmas(question)
    evidence_relations = boolean_relation_lemmas(text)
    relation_tokens = {
        token
        for relation in question_relations | evidence_relations
        for token in _relation_surface_tokens(relation)
    }
    question_tokens = {
        _object_token(token)
        for token in _content_tokens(question)
        if token not in relation_tokens
    }
    evidence_tokens = {
        _object_token(token)
        for token in _content_tokens(text)
        if token not in relation_tokens
    }
    question_tokens.discard("")
    evidence_tokens.discard("")
    if not question_tokens:
        return 1.0, ""
    shared = question_tokens & evidence_tokens
    score = len(shared) / len(question_tokens)
    return score, " ".join(sorted(shared))


def _relation_surface_tokens(relation: str) -> set[str]:
    surfaces = {
        "create": {
            "build",
            "built",
            "collect",
            "compile",
            "construct",
            "create",
            "develop",
        },
        "evaluate": {
            "assess",
            "benchmark",
            "conduct",
            "evaluate",
            "experiment",
            "perform",
            "run",
            "test",
        },
        "provide": {"available", "provide", "publish", "release"},
        "use": {"apply", "incorporate", "introduce", "use", "used"},
    }
    return surfaces.get(relation, {relation})


def _object_token(token: str) -> str:
    aliases = {
        "components": "component",
        "systems": "component",
        "system": "component",
        "packaged": "off_the_shelf",
        "shelf": "off_the_shelf",
        "german": "language_data",
        "greek": "language_data",
        "english": "language_data",
        "datasets": "dataset",
        "tasks": "task",
        "authors": "",
        "author": "",
    }
    return aliases.get(token, token.rstrip("s") if token.endswith("s") else token)


def _content_tokens(value: str) -> set[str]:
    stopwords = {
        "are",
        "did",
        "does",
        "only",
        "the",
        "they",
        "was",
        "were",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) > 2 and token not in stopwords
    }
