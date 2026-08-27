from __future__ import annotations

from ktem.docqa.boolean_proposition_tokens import _content_tokens, _object_token
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_validation import (
    locally_allowed_proposition_slots,
    locally_observed_proposition_slots,
)


def candidate_slot_hints(question: str, text: str) -> list[str]:
    """Return conservative, non-authoritative hints for one exact selector."""

    proposition = build_question_proposition(question)
    return list(locally_observed_proposition_slots(text, proposition))


def candidate_relation_anchor(question: str, text: str) -> bool:
    """Return whether one exact span carries the target relation and object."""

    proposition = build_question_proposition(question)
    allowed = set(locally_allowed_proposition_slots(text, proposition))
    return {"predicate", "object"} <= allowed


def normalized_candidate_object_tokens(value: str) -> set[str]:
    return {
        normalized
        for token in _content_tokens(value)
        if (normalized := _object_token(token))
    }
