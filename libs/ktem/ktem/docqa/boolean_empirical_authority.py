from __future__ import annotations

import re

from .boolean_empirical_actions import empirical_action_present
from .boolean_proposition_context import (
    bounded_proposition_context,
    normalized_object_tokens,
    qualified_category_bridge,
    specific_empirical_bridge_tokens,
)
from .boolean_proposition_evidence import exact_span_completes_boolean_proposition
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation


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
            shared = specific_empirical_bridge_tokens(
                empirical_tokens,
                context_tokens,
            )
            qualified_category = qualified_category_bridge(
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
