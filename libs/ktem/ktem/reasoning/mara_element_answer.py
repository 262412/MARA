from __future__ import annotations

import re
from typing import Any


def element_evidence_answer(bundle: Any, prompt: str = "") -> str:
    query_tokens = _tokens(prompt)
    excerpts = []
    for item in bundle.items:
        if str(item.get("modality") or "") in {"page_image", "graph"}:
            continue
        text = _best_excerpt(item, query_tokens)
        if text:
            excerpts.append(text)
        if len(excerpts) >= 3:
            break
    return " ".join(excerpts)


def _best_excerpt(item: dict[str, Any], query_tokens: set[str]) -> str:
    text = str(item.get("text") or item.get("caption") or "").strip()
    if not text:
        return ""
    scored = [
        (_fragment_score(fragment, query_tokens), index, fragment)
        for index, fragment in enumerate(_fragments(text))
    ]
    if query_tokens:
        scored = [item for item in scored if item[0] > 0]
    if not scored:
        return ""
    scored.sort(key=lambda item: (-item[0], item[1]))
    excerpt = scored[0][2].strip()
    return excerpt.rstrip(".") + "."


def _fragments(text: str) -> list[str]:
    fragments: list[str] = []
    for line in str(text or "").splitlines():
        cleaned = " ".join(line.split())
        if not cleaned:
            continue
        fragments.extend(part for part in re.split(r"(?<=[.!?])\s+", cleaned) if part)
    return fragments or [" ".join(str(text or "").split())]


def _fragment_score(fragment: str, query_tokens: set[str]) -> int:
    score = 4 * len(_tokens(fragment) & query_tokens)
    if re.search(r"\d", fragment):
        score += 2
    return score


_STOPWORDS = {
    "about",
    "also",
    "and",
    "are",
    "for",
    "from",
    "how",
    "the",
    "their",
    "this",
    "was",
    "were",
    "what",
    "which",
    "with",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(text or "").lower())
        if len(token) > 2 and token not in _STOPWORDS
    }
