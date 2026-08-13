from __future__ import annotations

import re

from .boolean_proposition_arguments import _question_argument_tokens
from .boolean_proposition_context import normalized_object_tokens
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation


def containment_marker_polarity(question: str, text: str) -> bool | None:
    """Bind ``subject with/without object`` to an asked containment frame."""

    if primary_boolean_relation(question) != "contain":
        return None
    frame = _containment_frame(question)
    if frame is None:
        return None
    subject_tokens, object_tokens = frame
    value = str(text or "")
    for marker in re.finditer(r"\b(with|without)\b", value, re.IGNORECASE):
        prefix = value[max(0, marker.start() - 100) : marker.start()]
        suffix = value[marker.end() : marker.end() + 120]
        prefix_tokens = normalized_object_tokens(prefix, set()) - {""}
        suffix_tokens = normalized_object_tokens(suffix, set()) - {""}
        if object_tokens <= suffix_tokens and (
            not subject_tokens or bool(subject_tokens & prefix_tokens)
        ):
            return marker.group(1).lower() == "without"
    return None


def _containment_frame(question: str) -> tuple[set[str], set[str]] | None:
    value = str(question or "")
    relation = re.search(
        r"\b(?:contain|contains|have|has|include|includes|involve|involves)\b",
        value,
        flags=re.IGNORECASE,
    )
    if relation is None:
        return None
    prefix = re.sub(
        r"^\s*(?:do|does|did|is|are|was|were|has|have|had)\s+",
        "",
        value[: relation.start()],
        flags=re.IGNORECASE,
    )
    subject_tokens = normalized_object_tokens(prefix, set()) - {
        "",
        "author",
        "paper",
        "study",
        "they",
    }
    object_tokens = normalized_object_tokens(value[relation.end() :], set()) - {""}
    return (subject_tokens, object_tokens) if object_tokens else None


def without_condition_targets_question(question: str, text: str) -> bool:
    """Return whether a ``without`` condition names a required argument.

    A proposition can contain an unrelated experimental condition, such as a
    model *without contextual representations*.  That condition must not
    negate a question about whether auxiliary syntax helps.  Binding the
    condition to the question arguments keeps the qualifier local and typed.
    """

    target = primary_boolean_relation(question)
    relation_tokens = _relation_surface_tokens(target)
    question_arguments = _question_argument_tokens(question, relation_tokens) - {""}
    if not question_arguments:
        return False
    for match in re.finditer(
        r"\bwithout\b(?P<object>[^,.;:!?]{1,120})",
        str(text or ""),
        flags=re.IGNORECASE,
    ):
        condition_arguments = normalized_object_tokens(
            match.group("object"),
            relation_tokens,
        ) - {""}
        if question_arguments & condition_arguments:
            return True
    return False


def without_target_has_negative_outcome(question: str, text: str) -> bool:
    """Recognize an explicit counterfactual failure without the target."""

    value = str(text or "")
    if not without_condition_targets_question(question, value):
        return False
    return bool(
        re.search(
            r"\b(?:fail(?:ed|s)?(?:\s+to)?|unable\s+to|cannot|can\s+not|"
            r"can't|could\s+not|couldn't|worse|worsen(?:ed|s)?|harm(?:ed|ful|s)?|"
            r"lower(?:ed|s)?|decrease|decreased|decreases|poor(?:er|ly)?)\b",
            value,
            flags=re.IGNORECASE,
        )
    )
