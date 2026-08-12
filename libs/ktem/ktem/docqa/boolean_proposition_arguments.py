from __future__ import annotations

import re

from .boolean_proposition_context import normalized_object_tokens
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation


def _question_argument_tokens(question: str, relation_tokens: set[str]) -> set[str]:
    """Extract predicate arguments without treating the subject as an object.

    ``the method``/``the authors`` are actors in Boolean questions such as
    ``does the method improve robustness``.  Including those subject nouns in
    the required object set makes a split exact span (``does not improve
    robustness``) look incomplete and previously allowed a neighboring
    positive clause to fill the missing actor.  Prefer the text following the
    first target relation; for passive questions with no meaningful suffix,
    use the text before that relation.
    """

    value = str(question or "")
    target = primary_boolean_relation(value)
    if not target:
        return normalized_object_tokens(value, relation_tokens)
    surfaces = sorted(_relation_surface_tokens(target), key=len, reverse=True)
    relation_pattern = "|".join(re.escape(surface) for surface in surfaces)
    match = re.search(rf"\b(?:{relation_pattern})\b", value, flags=re.IGNORECASE)
    if match is None:
        return normalized_object_tokens(value, relation_tokens)
    suffix = value[match.end() :]
    suffix_tokens = normalized_object_tokens(suffix, relation_tokens)
    prefix = value[: match.start()]
    prefix_tokens: set[str] = set()
    subject_argument = re.search(
        r"\b(?:having|using|with|from|on|through|via)\b(?P<value>.+)$",
        prefix,
        flags=re.IGNORECASE,
    )
    if subject_argument is not None:
        prefix_tokens = normalized_object_tokens(
            subject_argument.group("value"),
            relation_tokens,
        )
    else:
        prefix_tokens = normalized_object_tokens(prefix, relation_tokens) - {
            "method",
            "model",
            "approach",
            "system",
            "author",
            "paper",
            "study",
            "work",
            "they",
            "we",
        }
    arguments = suffix_tokens | prefix_tokens
    arguments -= {"other", "proposed", "than", "with"}
    exclusion = re.search(
        r"\bother\s+than\s+([^,;?.]+)",
        value,
        flags=re.IGNORECASE,
    )
    if exclusion is not None:
        arguments -= normalized_object_tokens(
            exclusion.group(1),
            relation_tokens,
        )
    return arguments or normalized_object_tokens(prefix, relation_tokens)
