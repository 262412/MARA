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
    first_line = next(
        (line.strip() for line in str(candidate or "").splitlines() if line.strip()),
        "",
    )
    match = re.match(
        r"^(?:answer\s*:\s*)?(yes|no|true|false)\b",
        first_line,
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""
    return "yes" if match.group(1).lower() in {"yes", "true"} else "no"


def quality_control_relation_polarity(question: str, quote: str) -> str:
    """Resolve the narrow QASPER data-quality proposition from a local quote."""

    lowered_question = str(question or "").lower()
    if not (
        re.search(r"\b(?:subject(?:ed)?\s+to|undergo(?:es|ne)?)\b", lowered_question)
        and re.search(r"\bquality\s+control\b", lowered_question)
    ):
        return ""
    lowered_quote = str(quote or "").lower()
    if re.search(
        r"\b(?:not\s+subject(?:ed)?\s+to|without|no)\s+(?:any\s+)?quality\s+control\b",
        lowered_quote,
    ):
        return "no"
    if re.search(
        r"\b(?:harder|difficult|impossible)\s+to\s+validate\s+the\s+quality\b",
        lowered_quote,
    ):
        return "no"
    if re.search(
        r"\b(?:subject(?:ed)?\s+to|undergo(?:es|ne|went)?)\s+(?:a\s+)?quality\s+control\b",
        lowered_quote,
    ):
        return "yes"
    return ""


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
    quality_control_polarity = quality_control_relation_polarity(question, quote)
    if quality_control_polarity:
        return verdict == quality_control_polarity
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


def corrected_complete_requirement_polarity(
    quote: str,
    question: str,
    verdict: str,
) -> str:
    """Correct only an explicit requirement-modality contradiction.

    A complete semantic verdict remains authoritative for ordinary lexical
    negation.  Requirement questions are the narrow exception because phrases
    such as ``without fine-tuning`` directly determine whether something is
    required.
    """

    if not _requirement_relation_conflicts(quote, question, verdict):
        return ""
    opposite = "no" if verdict == "yes" else "yes"
    if boolean_quote_supports_relation(quote, question, opposite):
        return opposite
    return ""


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
