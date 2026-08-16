from __future__ import annotations

import math
import re
from typing import Any

_TOKEN_RE = re.compile(r"[\w.%$€£¥-]+", re.UNICODE)


def selection_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    embedding_similarity = _embedding_cosine(left, right)
    if embedding_similarity is not None:
        return embedding_similarity
    left_tokens = selection_tokens(evidence_item_text(left))
    right_tokens = selection_tokens(evidence_item_text(right))
    return (
        len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
        if left_tokens and right_tokens
        else 0.0
    )


def evidence_item_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "")
        for field in ("text", "ocr_text", "vlm_text", "caption")
    )


def selection_tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}


def _embedding_cosine(
    left: dict[str, Any],
    right: dict[str, Any],
) -> float | None:
    left_embedding = _embedding(left)
    right_embedding = _embedding(right)
    if (
        not left_embedding
        or not right_embedding
        or len(left_embedding) != len(right_embedding)
    ):
        return None
    denominator = math.sqrt(sum(value * value for value in left_embedding)) * math.sqrt(
        sum(value * value for value in right_embedding)
    )
    if denominator == 0:
        return None
    return (
        sum(
            left_value * right_value
            for left_value, right_value in zip(left_embedding, right_embedding)
        )
        / denominator
    )


def _embedding(item: dict[str, Any]) -> list[float]:
    metadata = dict(item.get("metadata") or {})
    value = metadata.get("semantic_embedding") or metadata.get("embedding") or []
    if not isinstance(value, (list, tuple)):
        return []
    try:
        return [float(item) for item in value]
    except (TypeError, ValueError):
        return []
