from __future__ import annotations

import re

from .boolean_proposition_tokens import _object_token


def other_quantified_scope_complete(
    noun: str,
    quote: str,
    relation_spans: list[str],
    *,
    verdict: str,
) -> bool:
    """Require explicit alternative or closed-scope evidence for ``other``."""

    if not noun or not relation_spans:
        return False
    if verdict == "no":
        no_other = re.search(
            rf"\bno\s+other\s+{re.escape(noun)}s?\b",
            quote,
            flags=re.IGNORECASE,
        )
        closed_relation = any(
            re.search(r"\b(?:only|solely|exclusively)\b", span, re.IGNORECASE)
            for span in relation_spans
        )
        return bool(no_other or closed_relation)
    if verdict != "yes":
        return False
    return any(
        re.search(
            rf"\b(?:other|another|additional)\b[^.!?;]{{0,60}}"
            rf"\b{re.escape(noun)}s?\b",
            span,
            flags=re.IGNORECASE,
        )
        for span in relation_spans
    )


def _other_than_scope_complete(
    question: str,
    noun: str,
    relation_spans: list[str],
    *,
    verdict: str,
) -> bool:
    excluded_match = re.search(
        r"\bother\s+than\s+(?:the\s+)?([^,;?.]+)",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if excluded_match is None:
        return False
    excluded = _normalized_object_phrase(excluded_match.group(1))
    if verdict == "no":
        return any(
            re.search(rf"\bno\s+other\s+{re.escape(noun)}s?\b", span, re.I)
            or bool(
                excluded
                and excluded in _normalized_object_phrase(span)
                and re.search(
                    rf"\bonly\s+(?:on\s+)?(?:the\s+)?[^.!?;]{{0,50}}"
                    rf"\b{re.escape(noun)}s?\b",
                    span,
                    re.I,
                )
            )
            for span in relation_spans
        )
    if verdict != "yes":
        return False
    return any(
        _explicit_alternative_span(span, noun, excluded) for span in relation_spans
    )


def _explicit_alternative_span(span: str, noun: str, excluded: str) -> bool:
    if not _span_mentions_object_noun(span, noun):
        return False
    normalized = _normalized_object_phrase(span)
    if excluded and excluded in normalized:
        return False
    if re.search(r"\b(?:also|another|additional|other)\b", span, re.I):
        return True
    named = re.search(
        rf"\b([A-Z][A-Za-z0-9_-]+)\s+{re.escape(noun)}s?\b",
        span,
    )
    return bool(named and named.group(1).lower() not in {"our", "the", "we"})


def _span_mentions_object_noun(span: str, noun: str) -> bool:
    return bool(noun) and bool(
        re.search(rf"\b{re.escape(noun)}s?\b", span, flags=re.IGNORECASE)
    )


def _normalized_object_phrase(value: str) -> str:
    return " ".join(
        token
        for raw in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if (token := _object_token(raw))
    )
