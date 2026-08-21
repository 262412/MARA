from __future__ import annotations

import re

from .boolean_empirical_actions import empirical_action_present
from .boolean_proposition_context import (
    bounded_proposition_context,
    normalized_object_tokens,
)
from .boolean_proposition_evidence import exact_span_completes_boolean_proposition
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation

_EXPLICIT_CLASSIFICATION_RE = re.compile(
    r"\b(?:is|are|was|were)\s+"
    r"(?:(?:explicitly|commonly|generally)\s+)?"
    r"(?:treated|classified|considered|regarded)\s+as\b",
    flags=re.IGNORECASE,
)
_QUALIFIED_CATEGORY_TOKENS = {"corpus", "dataset", "language", "task"}
_GENERIC_BRIDGE_TOKENS = {
    "approach",
    "baseline",
    "component",
    "data",
    "dataset",
    "experiment",
    "language",
    "method",
    "model",
    "performance",
    "result",
    "system",
    "task",
    "toolkit",
}


def direct_experiment_relation(question: str, span: str, context: str) -> bool:
    """Bind an empirical action to its target within one local proposition."""

    if primary_boolean_relation(question) != "evaluate":
        return True
    if not empirical_action_present(question):
        return True
    local_context = bounded_proposition_context(context, span, question=question)
    clauses = re.split(
        r"(?:\r?\n)+|(?<=[.!?;])\s+|\s+(?:but|however|whereas)\s+",
        local_context,
        flags=re.IGNORECASE,
    )
    empirical_clauses = [
        clause for clause in clauses if empirical_action_present(clause)
    ]
    if any(
        exact_span_completes_boolean_proposition(question, clause)
        for clause in empirical_clauses
    ):
        return True
    relation_tokens = _relation_surface_tokens(primary_boolean_relation(question))
    for empirical_clause in empirical_clauses:
        empirical_tokens = normalized_object_tokens(empirical_clause, relation_tokens)
        for context_clause in clauses:
            if context_clause == empirical_clause:
                continue
            context_tokens = normalized_object_tokens(context_clause, relation_tokens)
            shared = (empirical_tokens & context_tokens) - _GENERIC_BRIDGE_TOKENS
            qualified_category = _qualified_category_bridge(
                question,
                empirical_tokens,
                context_tokens,
                context_clause,
                relation_tokens,
            )
            if (
                shared or qualified_category
            ) and exact_span_completes_boolean_proposition(
                question,
                f"{empirical_clause} {context_clause}",
            ):
                return True
    return False


def _qualified_category_bridge(
    question: str,
    empirical_tokens: set[str],
    context_tokens: set[str],
    context_clause: str,
    relation_tokens: set[str],
) -> bool:
    question_tokens = normalized_object_tokens(question, relation_tokens)
    category = (
        question_tokens & empirical_tokens & context_tokens & _QUALIFIED_CATEGORY_TOKENS
    )
    qualifiers = (
        (question_tokens & context_tokens) - empirical_tokens - _GENERIC_BRIDGE_TOKENS
    )
    return bool(
        category and qualifiers and _EXPLICIT_CLASSIFICATION_RE.search(context_clause)
    )
