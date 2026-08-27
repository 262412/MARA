from __future__ import annotations

import re

from ktem.docqa.boolean_evidence_scope import _actor
from ktem.docqa.boolean_proposition_polarity import evidence_polarity
from ktem.docqa.boolean_proposition_tokens import _content_tokens, _object_token
from ktem.docqa.question_proposition import build_question_proposition

_NUMBER_EQUIVALENTS = {
    "zero": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
    "ten": "10",
}


def candidate_slot_hints(question: str, text: str) -> list[str]:
    """Return conservative, non-authoritative hints for one exact selector."""

    proposition = build_question_proposition(question)
    hints: list[str] = []
    if _candidate_actor_aligned(proposition.actor, proposition.subject_surface, text):
        hints.append("actor")
    if evidence_polarity(question, text, desired_polarity="yes") in {"yes", "no"}:
        hints.append("predicate")
    if _candidate_object_aligned(proposition.object_surface, text):
        hints.append("object")
    if _candidate_quantifier_aligned(proposition.quantifier, text):
        hints.append("quantifier")
    return hints


def candidate_relation_anchor(question: str, text: str) -> bool:
    """Return whether one exact span carries the target relation and object."""

    hints = set(candidate_slot_hints(question, text))
    if "predicate" not in hints:
        return False
    proposition = build_question_proposition(question)
    object_tokens = normalized_candidate_object_tokens(proposition.object_surface)
    quantifier_tokens = normalized_candidate_object_tokens(
        str(proposition.quantifier or "")
    )
    relation_object_tokens = object_tokens - quantifier_tokens
    return bool(relation_object_tokens & normalized_candidate_object_tokens(text))


def normalized_candidate_object_tokens(value: str) -> set[str]:
    return {
        normalized
        for token in _content_tokens(value)
        if (normalized := _object_token(token))
    }


def _candidate_actor_aligned(actor: str, subject: str, text: str) -> bool:
    if actor == "current_paper":
        return _actor(text, "unknown") == "current_paper"
    if actor == "prior_work":
        return _actor(text, "related_work") == "cited_work"
    subject_tokens = normalized_candidate_object_tokens(subject)
    return bool(
        subject_tokens and subject_tokens <= normalized_candidate_object_tokens(text)
    )


def _candidate_object_aligned(object_surface: str, text: str) -> bool:
    object_tokens = normalized_candidate_object_tokens(object_surface)
    return bool(
        object_tokens and object_tokens <= normalized_candidate_object_tokens(text)
    )


def _candidate_quantifier_aligned(quantifier: str, text: str) -> bool:
    normalized = " ".join(str(quantifier or "").casefold().split())
    if normalized in {"", "none"}:
        return False
    tokens = set(re.findall(r"[a-z0-9]+", str(text or "").casefold()))
    if normalized.startswith("count:"):
        count = normalized.partition(":")[2]
        equivalent = next(
            (word for word, value in _NUMBER_EQUIVALENTS.items() if value == count),
            None,
        )
        return bool(count in tokens or (equivalent and equivalent in tokens))
    equivalent = _NUMBER_EQUIVALENTS.get(normalized)
    if equivalent is not None:
        return normalized in tokens or equivalent in tokens
    reverse = {value: key for key, value in _NUMBER_EQUIVALENTS.items()}
    equivalent = reverse.get(normalized)
    if equivalent is not None:
        return normalized in tokens or equivalent in tokens
    return normalized in " ".join(str(text or "").casefold().split())
