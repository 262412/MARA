from __future__ import annotations

import re

from .boolean_evidence_scope import (
    _english_closed_scope,
    _has_closed_quantifier,
    _language_data_question,
    _non_english_counterexample,
)
from .boolean_proposition_arguments import _question_argument_tokens
from .boolean_proposition_conditions import (
    containment_marker_polarity,
    without_target_has_negative_outcome,
)
from .boolean_proposition_context import normalized_object_tokens
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import (
    boolean_relation_lemmas,
    boolean_relations_align,
    primary_boolean_relation,
)


def _relation_compatibility(question: str, text: str) -> float:
    if _language_data_question(question) and _has_closed_quantifier(question):
        if _english_closed_scope(text) or _non_english_counterexample(text):
            return 1.0
    primary_relation = primary_boolean_relation(question)
    if primary_relation == "attribute":
        return 1.0
    question_relations = boolean_relation_lemmas(question)
    if primary_relation:
        question_relations.add(primary_relation)
    evidence_relations = boolean_relation_lemmas(text)
    if not question_relations:
        return 1.0
    if boolean_relations_align(question, text):
        return 1.0
    if containment_marker_polarity(question, text) is not None:
        return 1.0
    if without_target_has_negative_outcome(question, text):
        return 1.0
    if not primary_relation and question_relations & evidence_relations:
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
    question_tokens = _question_argument_tokens(
        question,
        relation_tokens,
    )
    evidence_tokens = normalized_object_tokens(text, relation_tokens)
    question_tokens.discard("")
    evidence_tokens.discard("")
    if (
        "task" in question_tokens
        and (
            re.search(
                r"\b(?:these|those|aforementioned)\s+tasks?\b",
                question,
                re.I,
            )
            or re.search(r"\btasks?\s+mentioned\b", question, re.I)
        )
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
