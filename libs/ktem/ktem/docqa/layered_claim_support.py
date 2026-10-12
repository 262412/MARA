from __future__ import annotations

import re
from typing import Any

from .boolean_evidence_scope import evidence_item_text
from .claim_support import text_contradicts_claim
from .evidence_identity import identity_of
from .qasper_relation_frame import (
    question_relation_frame,
    question_scope_is_explicit,
    relation_is_explicit,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_NUMBER_RE = re.compile(
    r"(?<![a-z0-9])(?:\d+(?:\.\d+)?|zero|one|two|three|four|five|six|seven|"
    r"eight|nine|ten)(?![a-z0-9])",
    re.IGNORECASE,
)
_SENTENCE_RE = re.compile(r"[^.!?\n]+(?:[.!?]+|$)")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "being",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "these",
    "this",
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
_DISCOURSE_TERMS = {
    "additionally",
    "also",
    "answer",
    "author",
    "authors",
    "specifically",
    "therefore",
    "thus",
}
_TOKEN_ALIASES = {
    "approach": "method",
    "approaches": "method",
    "application": "applicable",
    "applicability": "applicable",
    "applying": "apply",
    "articles": "article",
    "based": "base",
    "benefits": "benefit",
    "caused": "cause",
    "combined": "combine",
    "combines": "combine",
    "combining": "combine",
    "connections": "connection",
    "detects": "detect",
    "detection": "detect",
    "demonstrated": "demonstrate",
    "demonstrates": "demonstrate",
    "demonstrating": "demonstrate",
    "decreased": "decrease",
    "decreases": "decrease",
    "decline": "decrease",
    "declined": "decrease",
    "derived": "derive",
    "derives": "derive",
    "deriving": "derive",
    "differences": "difference",
    "distributions": "distribution",
    "embeddings": "embedding",
    "encoded": "encode",
    "encodes": "encode",
    "encoding": "encode",
    "features": "feature",
    "generated": "generate",
    "generates": "generate",
    "generating": "generate",
    "improved": "improve",
    "improves": "improve",
    "improving": "improve",
    "indicators": "indicator",
    "integrates": "integrate",
    "integrating": "integrate",
    "languages": "language",
    "lower": "reduce",
    "lowered": "reduce",
    "lowers": "reduce",
    "leveraged": "leverage",
    "leverages": "leverage",
    "leveraging": "leverage",
    "models": "model",
    "networks": "network",
    "patterns": "pattern",
    "representations": "represent",
    "represents": "represent",
    "representing": "represent",
    "robustness": "robust",
    "sentences": "sentence",
    "spammers": "spammer",
    "similarities": "similarity",
    "topics": "topic",
    "uses": "use",
    "using": "use",
    "users": "user",
}


def layered_claim_supporting_ids(
    claim: str,
    evidence_items: list[dict[str, Any]],
    *,
    prompt: str = "",
) -> tuple[str, ...]:
    """Return evidence items that support the claim at sentence level.

    This is deliberately narrower than topic matching: a candidate sentence
    must cover the claim's substantive values and, when the question exposes a
    relation, state that relation and scope explicitly.
    """

    claim_tokens = _content_tokens(claim)
    if not claim_tokens:
        return ()
    claim_numbers = _numbers(claim)
    frame = question_relation_frame(prompt) if str(prompt or "").strip() else None
    if frame is not None and frame.relation_kind == "quantity" and not claim_numbers:
        return ()

    supporting: list[str] = []
    for item in evidence_items:
        evidence_id = identity_of(item).key
        quotes = [
            quote
            for quote, _start, _end in _sentence_spans(evidence_item_text(item))
            if not quote.lstrip().startswith("#")
        ]
        for quote in quotes:
            if quote.lstrip().startswith("#") or text_contradicts_claim(claim, quote):
                continue
            quote_tokens = _content_tokens(quote)
            quote_numbers = _numbers(quote)
            if claim_numbers and not claim_numbers <= quote_numbers:
                continue
            if frame is not None:
                if frame.predicate and not relation_is_explicit(
                    frame,
                    quote,
                    answer_numbers=claim_numbers,
                    quote_numbers=quote_numbers,
                ):
                    continue
                if not question_scope_is_explicit(frame, quote):
                    continue
            overlap = claim_tokens & quote_tokens
            if _supports_core_values(claim_tokens, overlap):
                supporting.append(evidence_id)
                break
        else:
            if _supports_coherent_item(
                claim,
                claim_tokens,
                claim_numbers,
                quotes,
                frame=frame,
            ):
                supporting.append(evidence_id)
    return tuple(dict.fromkeys(supporting))


def _supports_core_values(claim_tokens: set[str], overlap: set[str]) -> bool:
    if not overlap:
        return False
    if len(claim_tokens) <= 2:
        return len(overlap) == len(claim_tokens)
    required = max(2, (len(claim_tokens) * 3 + 3) // 4)
    return len(overlap) >= min(len(claim_tokens), required)


def _supports_coherent_item(
    claim: str,
    claim_tokens: set[str],
    claim_numbers: set[str],
    quotes: list[str],
    *,
    frame: Any,
) -> bool:
    if not quotes:
        return False
    non_contradictory_quotes = [
        quote for quote in quotes if not text_contradicts_claim(claim, quote)
    ]
    if not non_contradictory_quotes:
        return False
    item_tokens = set().union(
        *(_content_tokens(quote) for quote in non_contradictory_quotes)
    )
    overlap = claim_tokens & item_tokens
    required = max(3, (len(claim_tokens) + 1) // 2)
    if len(overlap) < min(len(claim_tokens), required):
        return False
    if claim_numbers and not claim_numbers <= set().union(
        *(_numbers(quote) for quote in quotes)
    ):
        return False
    if frame is None or not frame.predicate:
        return True
    return any(
        relation_is_explicit(
            frame,
            quote,
            answer_numbers=claim_numbers,
            quote_numbers=_numbers(quote),
        )
        and question_scope_is_explicit(frame, quote)
        for quote in non_contradictory_quotes
    )


def _sentence_spans(text: str) -> list[tuple[str, int, int]]:
    output: list[tuple[str, int, int]] = []
    for match in _SENTENCE_RE.finditer(str(text or "")):
        raw = match.group(0)
        leading = len(raw) - len(raw.lstrip())
        quote = raw.strip()
        if not quote:
            continue
        start = match.start() + leading
        output.append((quote, start, start + len(quote)))
    return output


def _content_tokens(value: str) -> set[str]:
    return {
        _normalize_token(token)
        for token in _TOKEN_RE.findall(str(value or "").lower())
        if token not in _STOPWORDS and token not in _DISCOURSE_TERMS
    }


def _normalize_token(token: str) -> str:
    value = _TOKEN_ALIASES.get(token, token)
    if value.endswith("ies") and len(value) > 4:
        return f"{value[:-3]}y"
    if value.endswith("ing") and len(value) > 5:
        return value[:-3]
    if value.endswith("ed") and len(value) > 5:
        return value[:-2]
    if value.endswith("s") and not value.endswith("ss") and len(value) > 4:
        return value[:-1]
    return value


def _numbers(value: str) -> set[str]:
    return {match.group(0).lower() for match in _NUMBER_RE.finditer(str(value or ""))}
