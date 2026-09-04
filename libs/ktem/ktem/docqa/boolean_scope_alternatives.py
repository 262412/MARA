from __future__ import annotations

import re
from typing import NamedTuple

from .boolean_proposition_tokens import _object_token

_MAX_ALTERNATIVE_CONTEXT_SENTENCES = 3
_MAX_ALTERNATIVE_CONTEXT_CHARS = 1000


class AlternativeContext(NamedTuple):
    text: str
    start: int
    end: int


def other_quantified_scope_complete(
    noun: str,
    quote: str,
    relation_spans: list[str],
    *,
    question: str = "",
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
    if any(
        re.search(
            rf"\b(?:other|another|additional)\b[^.!?;]{{0,60}}"
            rf"\b{re.escape(noun)}s?\b",
            span,
            flags=re.IGNORECASE,
        )
        for span in relation_spans
    ):
        return True
    return _explicit_besides_alternative(question, quote, noun)


def _explicit_besides_alternative(question: str, quote: str, noun: str) -> bool:
    excluded_match = re.search(
        r"\b(?:besides|other\s+than|apart\s+from|in\s+addition\s+to)\s+"
        r"(?:the\s+)?([^,;?.]+)",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if excluded_match is None or not noun:
        return False
    excluded = _normalized_object_phrase(excluded_match.group(1))
    normalized_quote = _normalized_object_phrase(quote)
    if not excluded or excluded not in normalized_quote:
        return False
    if re.search(
        rf"\b(?:and|also|additional|another|other|as\s+well\s+as|"
        rf"in\s+addition\s+to)\b[^.!?;]{{0,60}}\b{re.escape(noun)}s?\b",
        quote,
        flags=re.IGNORECASE,
    ):
        return True
    return any(
        _explicit_alternative_span(span, noun, excluded)
        for span in re.split(r"(?:\r?\n)+|(?<=[.!?;])\s+", str(quote or ""))
    )


def explicit_besides_alternative_context(
    question: str,
    text: str,
    span: str,
) -> AlternativeContext | None:
    """Return the smallest same-paragraph window proving a named alternative."""

    noun = other_quantified_object_noun(question)
    source = str(text or "")
    target = str(span or "")
    matches = list(re.finditer(re.escape(target), source)) if target else []
    if not noun or len(matches) != 1:
        return None
    target_match = matches[0]
    statements = _statement_offsets(source)
    target_index = next(
        (
            index
            for index, (start, end) in enumerate(statements)
            if start <= target_match.start() and target_match.end() <= end
        ),
        None,
    )
    if target_index is None:
        return None
    candidates: list[tuple[int, int, int, str]] = []
    first_index = max(0, target_index - _MAX_ALTERNATIVE_CONTEXT_SENTENCES + 1)
    last_index = min(
        len(statements) - 1,
        target_index + _MAX_ALTERNATIVE_CONTEXT_SENTENCES - 1,
    )
    for first in range(first_index, target_index + 1):
        for last in range(target_index, last_index + 1):
            sentence_count = last - first + 1
            if sentence_count > _MAX_ALTERNATIVE_CONTEXT_SENTENCES:
                continue
            start, end = statements[first][0], statements[last][1]
            raw_candidate = source[start:end]
            start += len(raw_candidate) - len(raw_candidate.lstrip())
            end -= len(raw_candidate) - len(raw_candidate.rstrip())
            candidate = source[start:end]
            if (
                len(candidate) > _MAX_ALTERNATIVE_CONTEXT_CHARS
                or re.search(r"\n\s*\n|(?:^|\n)\s*#{1,6}\s+", candidate)
                or not _explicit_besides_alternative(question, candidate, noun)
            ):
                continue
            candidates.append((sentence_count, len(candidate), start, candidate))
    if not candidates:
        return None
    _count, _length, start, candidate = min(candidates)
    return AlternativeContext(candidate, start, start + len(candidate))


def expanded_alternative_quote(question: str, text: str, span: str) -> str:
    context = explicit_besides_alternative_context(question, text, span)
    return context.text if context is not None else str(span or "")


def _statement_offsets(value: str) -> list[tuple[int, int]]:
    protected = re.sub(r"(?<=\d)\.(?=\d)", "\x00", str(value or ""))
    return [
        (match.start(), match.end())
        for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", protected)
        if match.group(0).strip()
    ]


def other_quantified_object_noun(question: str) -> str:
    match = re.search(
        r"\bother\s+(?:[a-z0-9][a-z0-9-]*\s+){0,2}"
        r"(?P<noun>[a-z][a-z-]*s?)\s+"
        r"(?:besides|other\s+than|apart\s+from|in\s+addition\s+to)\b",
        str(question or ""),
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""
    noun = match.group("noun").lower()
    return noun[:-1] if noun.endswith("s") else noun


def other_quantifier_present(question: str) -> bool:
    return bool(
        re.search(
            r"\bother\s+(?:[a-z0-9][a-z0-9-]*\s+){0,2}(?:tasks?|benchmarks?|"
            r"data|datasets?|corpora|corpus|languages?|methods?|models?|"
            r"systems?|metrics?)\b",
            str(question or ""),
            flags=re.IGNORECASE,
        )
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
    normalized_noun = _object_token(str(noun or "").lower())
    return bool(normalized_noun) and normalized_noun in {
        _object_token(token)
        for token in re.findall(r"[a-z][a-z-]*", str(span or "").lower())
    }


def _normalized_object_phrase(value: str) -> str:
    return " ".join(
        token
        for raw in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if (token := _object_token(raw))
    )
