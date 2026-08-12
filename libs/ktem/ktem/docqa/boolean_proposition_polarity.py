from __future__ import annotations

import re

from .boolean_evidence_scope import (
    _english_closed_scope,
    _has_closed_quantifier,
    _language_data_question,
    _non_english_counterexample,
)
from .boolean_proposition_tokens import _content_tokens, _relation_surface_tokens
from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation


def answer_polarity(answer: str) -> str:
    normalized = str(answer or "").strip().lower()
    if normalized in {"yes", "true"}:
        return "yes"
    if normalized in {"no", "false"}:
        return "no"
    return ""


def evidence_polarity(
    question: str,
    text: str,
    *,
    desired_polarity: str,
) -> str:
    if _language_data_question(question) and _has_closed_quantifier(question):
        if _non_english_counterexample(text):
            return "no"
        if _english_closed_scope(text):
            return "yes"
        return ""
    evidence_polarity = _target_relation_polarity(question, text)
    question_polarity = _target_relation_polarity(question, question)
    if evidence_polarity is None or question_polarity is None:
        return ""
    evidence_negative = evidence_polarity
    question_negative = question_polarity
    return "yes" if evidence_negative == question_negative else "no"


def target_relation_is_negated(question: str, text: str) -> bool:
    """Return polarity for the relation occurrence nearest the asked object.

    A context chunk can contain both a positive and a negative use of the same
    relation (for example, ``improves accuracy, but does not improve
    robustness``).  Aggregating every occurrence turns that into an arbitrary
    all/any decision.  Authority callers pass an exact proposition span; when
    a larger context is supplied we choose the occurrence anchored to the
    question's object and fail closed on an unresolved tie.
    """

    return _target_relation_polarity(question, text) is True


def _target_relation_polarity(question: str, text: str) -> bool | None:
    target = primary_boolean_relation(question)
    lowered = str(text or "").lower()
    if _alternative_object_is_explicitly_excluded(question, lowered, target):
        return True
    if target == "improve" and re.search(
        r"\b(?:(?:small|minor|marginal)\s*,?\s*)?"
        r"(?:non[- ]?significant|insignificant)\s+improvements?\b"
        r"|\bno\s+(?:noticeable|significant)\s+"
        r"(?:improvement|performance\s+difference)\b",
        lowered,
    ):
        return True
    relation_matches = [
        match
        for match in re.finditer(r"[a-z]+(?:'[a-z]+)?", lowered)
        if target and target in boolean_relation_lemmas(match.group(0))
    ]
    if not relation_matches:
        return bool(
            re.search(
                r"\b(?:can't|cannot|couldn't|could not|didn't|doesn't|does not|"
                r"don't|do not|did not|fail(?:ed|s)? to|not able to|unable to|"
                r"no|not|never|without)\b",
                lowered,
            )
        )
    polarities = [
        _relation_match_is_negated(lowered, match) for match in relation_matches
    ]
    if len(set(polarities)) <= 1:
        return polarities[0]

    selected = _select_relation_match(question, lowered, relation_matches)
    if selected is None:
        return None
    return _relation_match_is_negated(lowered, selected)


_META_RELATION_FORMS = {
    "assert",
    "claim",
    "describe",
    "mention",
    "report",
    "show",
}


def _select_relation_match(
    question: str,
    text: str,
    matches: list[re.Match[str]],
) -> re.Match[str] | None:
    """Choose the relation occurrence anchored to the question object."""

    relation = primary_boolean_relation(question)
    object_tokens = _content_tokens(question) - {
        token
        for surface in _relation_surface_tokens(relation)
        for token in _content_tokens(surface)
    }
    object_tokens -= {"did", "does", "do", "is", "are", "was", "were"}

    token_positions = [
        (match.start(), match.end(), match.group(0).lower())
        for match in re.finditer(r"[a-z0-9]+(?:-[a-z0-9]+)?", text)
    ]

    def score(match: re.Match[str]) -> tuple[int, int, int]:
        distances = [
            min(abs(start - match.end()), abs(end - match.start()))
            for start, end, token in token_positions
            if token.rstrip("s") in object_tokens or token in object_tokens
        ]
        object_distance = min(distances, default=10_000)
        is_meta = int(match.group(0).lower().rstrip("s") in _META_RELATION_FORMS)
        # Prefer a concrete predicate to a reporting/meta-verb, then the
        # closest object anchor, then the later occurrence for passive clauses.
        return (is_meta, object_distance, -match.start())

    ranked = sorted(matches, key=score)
    if not ranked:
        return None
    best = ranked[0]
    if len(ranked) > 1 and score(ranked[1])[:2] == score(best)[:2]:
        first = _relation_match_is_negated(text, best)
        second = _relation_match_is_negated(text, ranked[1])
        if first != second:
            return None
    return best


def _alternative_object_is_explicitly_excluded(
    question: str,
    lowered_text: str,
    target_relation: str,
) -> bool:
    object_match = re.search(
        r"\b(?:any\s+)?(?:other\s+)?(?P<noun>[a-z][a-z-]*)" r"\s+other\s+than\b",
        str(question or "").lower(),
    )
    if object_match is None or not target_relation:
        return False
    noun = object_match.group("noun")
    singular = noun[:-1] if noun.endswith("s") else noun
    relation_present = target_relation in boolean_relation_lemmas(lowered_text)
    exclusion_present = re.search(
        rf"\bno\s+other\s+{re.escape(singular)}s?\b",
        lowered_text,
    )
    return bool(relation_present and exclusion_present)


def _relation_match_is_negated(lowered: str, match: re.Match[str]) -> bool:
    separators = (".", ";", ":", ",", " but ", " however ", " yet ")
    prefix = lowered[: match.start()]
    boundary = max(prefix.rfind(value) for value in separators)
    local_prefix = prefix[boundary + 1 :]
    suffix = lowered[match.end() :]
    suffix_boundary = min(
        (index for value in separators if (index := suffix.find(value)) >= 0),
        default=len(suffix),
    )
    local_suffix = suffix[:suffix_boundary]
    return bool(
        re.search(
            r"\b(?:can't|cannot|couldn't|could not|didn't|doesn't|does not|"
            r"don't|do not|did not|fail(?:ed|s)?\s+to|not\s+able\s+to|"
            r"unable\s+to|omit(?:ted|s)?|exclud(?:e|ed|es)|"
            r"skip(?:ped|s)?|no|not|never|without)\b",
            local_prefix,
        )
        or re.search(r"^\s+(?:no|not\s+any)\b", local_suffix)
    )
