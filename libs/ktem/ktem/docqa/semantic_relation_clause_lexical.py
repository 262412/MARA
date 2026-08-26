from __future__ import annotations

import re
from typing import Any

from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import boolean_relation_lemma
from .question_proposition import QuestionProposition

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
_CLAUSE_BOUNDARY_RE = re.compile(
    r",\s+(?:but|however|yet|although|while|whereas)\s+|[;.!?](?:\s+|$)",
    re.IGNORECASE,
)
_CURRENT_PAPER_ACTOR_RE = re.compile(
    r"\b(?:we|us|our|the\s+authors?|authors?|"
    r"(?:this|the|our)\s+(?:paper|study|work)|"
    r"(?:the|our|this|proposed|current)\s+(?:approach|method|model|system))\b",
    re.IGNORECASE,
)
_PRIOR_WORK_ACTOR_RE = re.compile(
    r"\b(?:(?:prior|previous|earlier|existing)\s+"
    r"(?:work|study|studies|approach|method|model|system)|they|their)\b",
    re.IGNORECASE,
)
_ANY_ACTOR_RE = re.compile(
    r"\b(?:prior\s+work|previous\s+work|the\s+model|this\s+model|"
    r"the\s+experiment|this\s+experiment|the\s+system|this\s+system|"
    r"this\s+sentence|it|they|their)\b",
    re.IGNORECASE,
)
_META_PREDICATE_RE = re.compile(
    r"\b(?:ask|assert|claim|confirm|describe|demonstrate|establish|indicate|"
    r"mention|prove|report|say|show|state|suggest)\w*\b",
    re.IGNORECASE,
)
_META_NOUN_RE = re.compile(
    r"\b(?:claim|evidence|mention|question|report|sentence|statement|text|"
    r"title|passage)\b",
    re.IGNORECASE,
)
_META_COMPLEMENT_RE = re.compile(r"\b(?:if|that|whether)\b", re.IGNORECASE)
ASSERTIVE_VERB_RE = re.compile(
    r"\b(?:is|are|was|were|has|have|had|can|could|did|does|do|will|would|"
    r"focus(?:es|ed|ing)?|reference(?:s|d|ing)?|"
    r"[A-Za-z]{3,}(?:ed|ing))\b",
    re.IGNORECASE,
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "any",
    "at",
    "by",
    "did",
    "do",
    "does",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "to",
    "was",
    "were",
    "with",
}
SEMANTIC_SCAFFOLD_TOKENS = {
    "how",
    "if",
    "it",
    "its",
    "see",
    "that",
    "their",
    "when",
    "whether",
}


def clause_spans(value: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in _CLAUSE_BOUNDARY_RE.finditer(value):
        boundary = match.group(0)
        end = match.start() if boundary.lstrip().startswith(",") else match.end()
        trimmed = _trim_span(value, start, end)
        if trimmed[0] < trimmed[1]:
            spans.append(trimmed)
        start = match.end()
    trimmed = _trim_span(value, start, len(value))
    if trimmed[0] < trimmed[1]:
        spans.append(trimmed)
    return spans or ([(0, len(value))] if value else [])


def actor_span(
    clause: str,
    proposition: QuestionProposition,
    *,
    offset: int,
) -> tuple[dict[str, Any] | None, bool]:
    pattern = None
    if proposition.actor == "current_paper":
        pattern = _CURRENT_PAPER_ACTOR_RE
    elif proposition.actor == "prior_work":
        pattern = _PRIOR_WORK_ACTOR_RE
    if pattern is not None and (match := pattern.search(clause)) is not None:
        return _span_payload(clause, match.start(), match.end(), offset=offset), True
    for surface in (proposition.subject_surface, proposition.actor):
        span = literal_span(clause, surface, offset=offset)
        if span is not None:
            return span, True
    fallback = _ANY_ACTOR_RE.search(clause)
    if fallback is not None:
        return (
            _span_payload(clause, fallback.start(), fallback.end(), offset=offset),
            False,
        )
    return None, False


def predicate_spans(
    clause: str,
    predicate: str,
    *,
    offset: int,
) -> list[dict[str, Any]]:
    target = boolean_relation_lemma(predicate) or str(predicate or "").casefold()
    target_surfaces = {
        str(surface).casefold() for surface in _relation_surface_tokens(target)
    }
    target_stems = {
        _token_stem(part)
        for part in re.split(r"[_\s]+", target)
        if part and part not in {"be", "of", "on", "to"}
    }
    target_stems.add(_token_stem(predicate))
    output = []
    for match in _TOKEN_RE.finditer(clause):
        token = match.group(0).casefold()
        relation = boolean_relation_lemma(token)
        if (
            relation == target
            or token in target_surfaces
            or _token_stem(token) in target_stems
        ):
            output.append(
                _span_payload(clause, match.start(), match.end(), offset=offset)
            )
    return output


def contextual_predicate_span(
    clause: str,
    *,
    offset: int,
) -> dict[str, Any] | None:
    for match in _TOKEN_RE.finditer(clause):
        token = match.group(0)
        if boolean_relation_lemma(token) or re.search(
            r"(?:ed|ing)$", token, flags=re.IGNORECASE
        ):
            return _span_payload(clause, match.start(), match.end(), offset=offset)
    return None


def object_span(
    clause: str,
    object_surface: str,
    required_tokens: set[str],
    *,
    offset: int,
) -> tuple[dict[str, Any] | None, set[str]]:
    literal = literal_span(clause, object_surface, offset=offset)
    if literal is not None:
        return literal, set(required_tokens)
    token_matches = [
        (match, canonical_semantic_token(match.group(0)))
        for match in _TOKEN_RE.finditer(clause)
    ]
    covered = {
        token for _match, token in token_matches if token and token in required_tokens
    }
    if not covered:
        return None, set()
    selected = [match for match, token in token_matches if token in covered]
    return (
        _span_payload(
            clause,
            min(match.start() for match in selected),
            max(match.end() for match in selected),
            offset=offset,
        ),
        covered,
    )


def literal_span(clause: str, value: str, *, offset: int) -> dict[str, Any] | None:
    normalized = " ".join(str(value or "").split())
    if not normalized or normalized.casefold() == "none":
        return None
    pattern = r"\s+".join(re.escape(part) for part in normalized.split())
    match = re.search(pattern, clause, flags=re.IGNORECASE)
    if match is None:
        return None
    return _span_payload(clause, match.start(), match.end(), offset=offset)


def meta_scoped(clause: str, relation_start: int) -> bool:
    prefix = clause[:relation_start]
    recent = prefix[-160:]
    meta_predicates = list(_META_PREDICATE_RE.finditer(recent))
    if meta_predicates:
        last = meta_predicates[-1]
        after_meta = recent[last.end() :]
        if _META_COMPLEMENT_RE.search(after_meta) or len(after_meta.strip()) <= 80:
            return True
    return bool(
        _META_NOUN_RE.search(recent)
        and (
            _META_COMPLEMENT_RE.search(recent)
            or re.search(
                r"\b(?:no|not|without|insufficient|lack(?:s|ed|ing)?)\b",
                recent,
                re.I,
            )
        )
    )


def direct_relation_negated(clause: str, relation_start: int) -> bool:
    prefix = clause[:relation_start]
    recent = prefix[-80:]
    return bool(
        re.search(
            r"(?:\b(?:do|does|did|is|are|was|were|has|have|had|can|could|"
            r"will|would)\s+(?:not|never)(?:\s+[A-Za-z]+ly){0,2}\s*|"
            r"\bnever(?:\s+[A-Za-z]+ly){0,2}\s*|"
            r"\b(?:fail(?:s|ed)?\s+to|without)\s*)$",
            recent,
            flags=re.IGNORECASE,
        )
    )


def semantic_content_token_set(value: str) -> set[str]:
    return {
        normalized
        for match in _TOKEN_RE.finditer(str(value or ""))
        if (normalized := canonical_semantic_token(match.group(0)))
        and normalized not in _STOPWORDS
        and normalized not in SEMANTIC_SCAFFOLD_TOKENS
    }


def canonical_semantic_token(value: str) -> str:
    stem = _token_stem(value)
    if stem.startswith("entit"):
        return "entity"
    return {
        "amplifie": "affect",
        "amplify": "affect",
        "evaluat": "metric",
        "evaluated": "metric",
        "evaluation": "metric",
        "predict": "prediction",
        "predicting": "prediction",
        "system": "component",
        "visual": "image",
    }.get(stem, stem)


def _token_stem(value: str) -> str:
    token = str(value or "").casefold().strip("'-")
    if not token:
        return ""
    if token.endswith(("ations", "ation")) and len(token) > 7:
        return token[:-4] if token.endswith("ations") else token[:-3]
    noun_suffix = "m" + "ent"
    for suffix in (noun_suffix + "s", noun_suffix, "ingly", "edly", "ing", "ied", "ed"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            stem = token[: -len(suffix)]
            return f"{stem}y" if suffix == "ied" else stem
    if token.endswith("ies") and len(token) > 4:
        return token[:-3] + "y"
    if token.endswith("s") and not token.endswith(("ss", "us")) and len(token) > 4:
        return token[:-1]
    return token


def _span_payload(
    clause: str,
    start: int,
    end: int,
    *,
    offset: int,
) -> dict[str, Any]:
    return {
        "text": clause[start:end],
        "span_start": offset + start,
        "span_end": offset + end,
    }


def _trim_span(value: str, start: int, end: int) -> tuple[int, int]:
    while start < end and value[start].isspace():
        start += 1
    while end > start and value[end - 1].isspace():
        end -= 1
    return start, end
