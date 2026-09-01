from __future__ import annotations

import re

from .boolean_authority_schema import BooleanEvidenceAuthority
from .boolean_proposition_context import normalized_object_tokens
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation

_GENERIC_SUBJECT_TOKENS = {
    "are",
    "author",
    "can",
    "classifier",
    "collection",
    "current",
    "dataset",
    "did",
    "do",
    "does",
    "experiment",
    "feature",
    "framework",
    "had",
    "has",
    "have",
    "is",
    "language",
    "method",
    "model",
    "paper",
    "study",
    "system",
    "task",
    "their",
    "they",
    "this",
    "toolkit",
    "was",
    "were",
    "work",
}


def semantic_scope_basis(
    question: str, premises: list[BooleanEvidenceAuthority]
) -> str:
    actors = {value.actor for value in premises}
    if _explicit_current_paper_question(question):
        return "explicit_current_actor" if "current_paper" in actors else ""
    if "current_paper" in actors:
        return "explicit_current_actor"
    if actors & {"cited_work", "other_authors"}:
        return "explicit_prior_work_actor"
    return (
        "named_question_subject"
        if _named_question_subject_anchored(question, premises)
        else ""
    )


def _explicit_current_paper_question(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:the authors?|this (?:paper|article|study|work)|"
            r"current (?:paper|study|work)|they|their)\b",
            str(question or ""),
            flags=re.IGNORECASE,
        )
    )


def _named_question_subject_anchored(
    question: str, premises: list[BooleanEvidenceAuthority]
) -> bool:
    relation_tokens = _relation_surface_tokens(primary_boolean_relation(question))
    if not relation_tokens:
        return False
    pattern = re.compile(
        r"\b(?:"
        + "|".join(
            re.escape(value) for value in sorted(relation_tokens, key=len, reverse=True)
        )
        + r")\b",
        flags=re.IGNORECASE,
    )
    match = pattern.search(str(question or ""))
    if match is None:
        return False
    subject_tokens = (
        normalized_object_tokens(str(question or "")[: match.start()], relation_tokens)
        - _GENERIC_SUBJECT_TOKENS
    )
    subject_tokens = {value for value in subject_tokens if len(value) >= 3}
    evidence_tokens = normalized_object_tokens(
        " ".join(value.quote for value in premises), set()
    )
    return bool(subject_tokens & evidence_tokens)
