from __future__ import annotations

import re

_PHRASE_TOKEN_RE = re.compile(r"[\w]+", re.UNICODE)
_QUOTED_ANCHOR_RE = re.compile(r"""["“]([^"”]{2,})["”]""")
_DATE_ANCHOR_RE = re.compile(
    r"\b(?:January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+\d{1,2},?\s+(?:19|20)\d{2}\b",
    re.IGNORECASE,
)
_NUMBERED_ANCHOR_RE = re.compile(
    r"\b(?:episode|chapter|section|season)\s+\d+\b",
    re.IGNORECASE,
)
_PROPER_PHRASE_RE = re.compile(
    r"\b[A-Z][\w'’-]*(?:\s+(?:(?:of|the|and|in|on|for)\s+)?" r"[A-Z][\w'’-]*)+\b"
)
_PHRASE_STOPWORDS = {
    "a",
    "an",
    "and",
    "did",
    "do",
    "does",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "was",
    "were",
    "what",
    "when",
    "which",
    "who",
}
_ANCHOR_GENERIC_TOKENS = _PHRASE_STOPWORDS | {
    "air",
    "answer",
    "as",
    "be",
    "built",
    "die",
    "died",
    "dies",
    "episode",
    "open",
    "opened",
    "season",
    "sing",
    "sings",
    "start",
    "version",
}


def anchor_coverage(query: str, item_text: str) -> float:
    anchors = _query_anchors(query)
    if not anchors:
        return 0.0
    normalized_text = _normalized_phrase(item_text)
    return sum(anchor in normalized_text for anchor in anchors) / len(anchors)


def phrase_bigram_coverage(query: str, item_text: str) -> float:
    query_tokens = [
        token.lower() for token in _PHRASE_TOKEN_RE.findall(str(query or ""))
    ]
    bigrams = list(
        dict.fromkeys(
            f"{left} {right}"
            for left, right in zip(query_tokens, query_tokens[1:])
            if left not in _PHRASE_STOPWORDS or right not in _PHRASE_STOPWORDS
        )
    )
    if not bigrams:
        return 0.0
    normalized_text = _normalized_phrase(item_text)
    return sum(bigram in normalized_text for bigram in bigrams) / len(bigrams)


def _query_anchors(query: str) -> tuple[str, ...]:
    raw_anchors = [
        *_QUOTED_ANCHOR_RE.findall(query),
        *_DATE_ANCHOR_RE.findall(query),
        *_NUMBERED_ANCHOR_RE.findall(query),
        *_PROPER_PHRASE_RE.findall(query),
        *_content_bigram_anchors(query),
    ]
    anchors: list[str] = []
    for value in raw_anchors:
        normalized = _normalized_phrase(value)
        tokens = normalized.split()
        if (
            len(tokens) >= 2
            and any(token not in _PHRASE_STOPWORDS for token in tokens)
            and normalized not in anchors
        ):
            anchors.append(normalized)
    return tuple(anchors)


def _content_bigram_anchors(query: str) -> list[str]:
    tokens = [token.lower() for token in _PHRASE_TOKEN_RE.findall(str(query or ""))]
    return list(
        dict.fromkeys(
            f"{left} {right}"
            for left, right in zip(tokens, tokens[1:])
            if len(left) > 1
            and len(right) > 1
            and left not in _ANCHOR_GENERIC_TOKENS
            and right not in _ANCHOR_GENERIC_TOKENS
        )
    )


def _normalized_phrase(text: str) -> str:
    return " ".join(
        token.lower() for token in _PHRASE_TOKEN_RE.findall(str(text or ""))
    )
