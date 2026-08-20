from __future__ import annotations

import re

_COUNT_MARKER_RE = re.compile(
    r"\b(?P<marker>double|twice|two|2|triple|thrice|three|3)\b",
    flags=re.IGNORECASE,
)
_ANNOTATION_RE = re.compile(
    r"\b(?:annotat\w*|label\w*|crowd[- ]?source\w*)\b",
    flags=re.IGNORECASE,
)
_ANSWER_BY_EXPERT_RE = re.compile(
    r"\banswer\w*\s+by\b[^.!?]{0,100}\b" r"(?:expert|annotator|rater|judge)\w*\b",
    flags=re.IGNORECASE,
)
_NEGATION_RE = re.compile(r"\b(?:no|not|never)\b", flags=re.IGNORECASE)
_NON_EXACT_COUNT_RE = re.compile(
    r"\b(?:at\s+least|at\s+most|more\s+than|fewer\s+than|"
    r"no\s+(?:fewer|more)\s+than|additional)\b",
    flags=re.IGNORECASE,
)

_COUNT_VALUES = {
    "double": 2,
    "twice": 2,
    "two": 2,
    "2": 2,
    "triple": 3,
    "thrice": 3,
    "three": 3,
    "3": 3,
}


def annotation_count_question(value: str) -> bool:
    return bool(annotation_relation_present(value) and annotation_count_target(value))


def annotation_relation_present(value: str) -> bool:
    text = str(value or "")
    return bool(_ANNOTATION_RE.search(text) or _ANSWER_BY_EXPERT_RE.search(text))


def annotation_count_target(value: str) -> int | None:
    if not annotation_relation_present(value):
        return None
    markers = list(_COUNT_MARKER_RE.finditer(str(value or "")))
    if not markers:
        return None
    unnegated = [marker for marker in markers if not _marker_is_negated(value, marker)]
    marker = (unnegated or markers)[0]
    return _COUNT_VALUES[marker.group("marker").lower()]


def annotation_count_observed(value: str) -> int | None:
    if not annotation_relation_present(value):
        return None
    markers = list(_COUNT_MARKER_RE.finditer(str(value or "")))
    if not markers:
        return None
    marker = min(markers, key=lambda match: _relation_distance(value, match))
    return _COUNT_VALUES[marker.group("marker").lower()]


def annotation_count_object(question: str, text: str) -> str:
    target = annotation_count_target(question)
    observed = annotation_count_observed(text)
    return (
        "annotation count"
        if target is not None
        and observed == target
        and annotation_relation_present(text)
        else ""
    )


def annotation_count_polarity(question: str, text: str) -> bool | None:
    """Return target-count negation, ignoring negated alternative counts."""

    target = annotation_count_target(question)
    observed = (
        target
        if _same_question_text(question, text)
        else annotation_count_observed(text)
    )
    if (
        target is None
        or observed != target
        or not annotation_relation_present(text)
        or not _count_marker_is_exact(text, target)
    ):
        return None
    marker = _target_marker(text, target)
    return _marker_is_negated(text, marker) if marker is not None else None


def annotation_count_scope_complete(
    question: str,
    quote: str,
    *,
    required_count: int,
) -> bool:
    return bool(
        annotation_relation_present(quote)
        and annotation_count_observed(quote) == required_count
        and annotation_count_target(question) == required_count
        and _count_marker_is_exact(quote, required_count)
    )


def annotation_count_scope_complete_for_quantifier(
    question: str,
    quote: str,
    quantifier: str,
) -> bool:
    if not quantifier.startswith("count:"):
        return False
    return annotation_count_scope_complete(
        question,
        quote,
        required_count=int(quantifier.partition(":")[2]),
    )


def _target_marker(value: str, target: int) -> re.Match[str] | None:
    return next(
        (
            marker
            for marker in _COUNT_MARKER_RE.finditer(str(value or ""))
            if _COUNT_VALUES[marker.group("marker").lower()] == target
        ),
        None,
    )


def _count_marker_is_exact(value: str, target: int) -> bool:
    marker = _target_marker(value, target)
    if marker is None:
        return False
    local = str(value or "")[max(0, marker.start() - 24) : marker.end() + 24]
    return not _NON_EXACT_COUNT_RE.search(local)


def _same_question_text(question: str, text: str) -> bool:
    return " ".join(str(question or "").lower().split()) == " ".join(
        str(text or "").lower().split()
    )


def _marker_is_negated(value: str, marker: re.Match[str]) -> bool:
    prefix = str(value or "")[max(0, marker.start() - 40) : marker.start()]
    return bool(_NEGATION_RE.search(prefix))


def _relation_distance(value: str, marker: re.Match[str]) -> int:
    text = str(value or "")
    relation_matches = list(_ANNOTATION_RE.finditer(text))
    if not relation_matches:
        relation_matches = list(_ANSWER_BY_EXPERT_RE.finditer(text))
    return min(
        (abs(marker.start() - relation.start()) for relation in relation_matches),
        default=len(text),
    )
