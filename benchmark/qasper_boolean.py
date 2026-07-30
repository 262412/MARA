from __future__ import annotations

import re

from ktem.docqa.boolean_relations import (
    boolean_relation_lemmas,
    boolean_relations_align,
    primary_boolean_relation,
)

_BOOLEAN_QUESTION_RE = re.compile(
    r"(?:^|[,;:]\s*)(?:is|are|was|were|do|does|did|has|have|had|"
    r"can|could|will|would|should|may|might)\b",
    re.IGNORECASE,
)
_QUESTION_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


def is_boolean_question(question: str) -> bool:
    return bool(_BOOLEAN_QUESTION_RE.search(str(question or "").strip()))


def boolean_candidate_polarity(candidate: str) -> str:
    if str(candidate or "").lower() in {"yes", "true"}:
        return "yes"
    return "no" if candidate else ""


def normalized_boolean_quote(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def boolean_quote_is_grounded(quote: str, evidence: str) -> bool:
    normalized_quote = normalized_boolean_quote(quote)
    normalized_evidence = normalized_boolean_quote(evidence)
    return len(normalized_quote) >= 8 and normalized_quote in normalized_evidence


def stemmed_content_tokens(value: str) -> set[str]:
    return {
        token[:5] if len(token) > 5 else token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if token not in _QUESTION_STOPWORDS
    }


def boolean_quote_supports_relation(
    quote: str,
    question: str,
    verdict: str,
) -> bool:
    quote_tokens = stemmed_content_tokens(quote)
    question_anchors = stemmed_content_tokens(question)
    question_relations = boolean_relation_lemmas(question)
    quote_relations = boolean_relation_lemmas(quote)
    if _requirement_relation_conflicts(quote, question, verdict):
        return False
    if _qualitative_risk_relation_supported(quote, question, verdict):
        return True
    primary_relation = primary_boolean_relation(question)
    if primary_relation and not boolean_relations_align(question, quote):
        if verdict != "no" or not _negative_relation_supported(
            quote,
            question_anchors,
            quote_tokens,
            {primary_relation},
        ):
            return False
    elif question_relations and not (question_relations & quote_relations):
        return False
    required_anchors = min(2, len(question_anchors))
    if required_anchors and len(quote_tokens & question_anchors) >= required_anchors:
        return True
    if verdict != "no":
        return False
    lowered_quote = str(quote or "").lower()
    return any(
        cue in lowered_quote
        for cue in (
            "drop-in replacement",
            "does not",
            "do not",
            "no ",
            "not ",
            "unnecessary",
            "without",
        )
    )


def boolean_complete_quote_conflicts(
    quote: str,
    question: str,
    verdict: str,
) -> bool:
    """Return only deterministic, high-precision proposition conflicts.

    Complete verdicts already come from the semantic proposition judge. This
    helper must remain narrower than ``boolean_quote_supports_relation`` so a
    lexical paraphrase mismatch cannot overrule a complete semantic verdict.
    """

    if _requirement_relation_conflicts(quote, question, verdict):
        return True
    if _qualitative_risk_relation_supported(quote, question, verdict):
        return False
    question_negative = _has_explicit_negation(question)
    quote_negative = _has_explicit_negation(quote)
    if question_negative:
        return False
    if verdict == "no" and not quote_negative:
        return _positive_relation_alignment(quote, question)
    if verdict == "yes" and quote_negative:
        return boolean_quote_supports_relation(quote, question, "no")
    return False


def _has_explicit_negation(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:doesn't|does not|don't|do not|no|not|never|without)\b",
            str(value or "").lower(),
        )
    )


def _positive_relation_alignment(quote: str, question: str) -> bool:
    question_relations = boolean_relation_lemmas(question)
    quote_relations = boolean_relation_lemmas(quote)
    if not question_relations or not (question_relations & quote_relations):
        return False
    relation_tokens = {
        lemma[:5] if len(lemma) > 5 else lemma for lemma in question_relations
    }
    question_objects = stemmed_content_tokens(question) - relation_tokens
    quote_tokens = stemmed_content_tokens(quote)
    return bool(question_objects & quote_tokens)


def _requirement_relation_conflicts(
    quote: str,
    question: str,
    verdict: str,
) -> bool:
    lowered_question = str(question or "").lower()
    if not re.search(
        r"\b(?:require|required|requires|necessary|must)\b", lowered_question
    ):
        return False
    lowered_quote = str(quote or "").lower()
    if verdict == "yes":
        return not re.search(
            r"\b(?:require|required|requires|necessary|must)\b",
            lowered_quote,
        ) or bool(
            re.search(
                r"\b(?:without|unnecessary|optional|drop-in)\b",
                lowered_quote,
            )
        )
    return not bool(
        re.search(
            r"\b(?:without|unnecessary|not required|does not require|"
            r"do not require|optional|drop-in)\b",
            lowered_quote,
        )
    )


def _qualitative_risk_relation_supported(
    quote: str,
    question: str,
    verdict: str,
) -> bool:
    if verdict != "yes" or not re.search(
        r"\b(?:downside|disadvantage|drawback|risk)\b",
        str(question or "").lower(),
    ):
        return False
    return bool(
        re.search(
            r"\b(?:disadvantage|drawback|harm|limit|remove|risk)\b|"
            r"not a silver bullet",
            str(quote or "").lower(),
        )
    )


def _negative_relation_supported(
    quote: str,
    question_anchors: set[str],
    quote_tokens: set[str],
    question_relations: set[str],
) -> bool:
    object_anchors = question_anchors - {
        lemma[:5] if len(lemma) > 5 else lemma for lemma in question_relations
    }
    lowered_quote = str(quote or "").lower()
    if "drop-in replacement" in lowered_quote and {"fine", "tunin"} <= object_anchors:
        return True
    if not (object_anchors & quote_tokens):
        return False
    return any(
        cue in lowered_quote
        for cue in (
            "drop-in replacement",
            "does not",
            "do not",
            "no ",
            "not ",
            "unnecessary",
            "without",
        )
    )
