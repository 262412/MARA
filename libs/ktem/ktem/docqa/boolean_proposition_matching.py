from __future__ import annotations

import re

from .boolean_proposition_compatibility import (
    _object_compatibility,
    _relation_compatibility,
)
from .boolean_proposition_polarity import attribute_predicate_is_asserted
from .boolean_proposition_tokens import _content_tokens, _relation_surface_tokens
from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation
from .query_phrase_extraction import semantic_boolean_proposition_question


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


def _context_matches_proposition(question: str, context: str) -> bool:
    relation_score = _relation_compatibility(question, context)
    object_score, _object = _object_compatibility(question, context)
    return relation_score > 0 and object_score >= 0.6
