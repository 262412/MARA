from __future__ import annotations

import hashlib
import math
import re
from typing import Any

_TOKEN_RE = re.compile(r"[\w.%$€£¥-]+", re.UNICODE)


def minhash_text_similarity(left_text: str, right_text: str) -> float:
    left_tokens = _tokens(left_text)
    right_tokens = _tokens(right_text)
    if len(left_tokens) < 4 or len(right_tokens) < 4:
        return 0.0
    left_signature = _minhash_signature(left_tokens)
    right_signature = _minhash_signature(right_tokens)
    return sum(a == b for a, b in zip(left_signature, right_signature)) / len(
        left_signature
    )


def cosine_item_similarity(
    left: dict[str, Any],
    right: dict[str, Any],
) -> float:
    left_embedding = _embedding(left)
    right_embedding = _embedding(right)
    if (
        not left_embedding
        or not right_embedding
        or len(left_embedding) != len(right_embedding)
    ):
        return 0.0
    denominator = math.sqrt(sum(value * value for value in left_embedding)) * math.sqrt(
        sum(value * value for value in right_embedding)
    )
    if denominator == 0:
        return 0.0
    return (
        sum(
            left_value * right_value
            for left_value, right_value in zip(left_embedding, right_embedding)
        )
        / denominator
    )


def _minhash_signature(
    tokens: set[str],
    permutations: int = 32,
) -> tuple[int, ...]:
    return tuple(
        min(
            int.from_bytes(
                hashlib.blake2b(
                    f"{seed}:{token}".encode("utf-8"),
                    digest_size=8,
                ).digest(),
                "big",
            )
            for token in tokens
        )
        for seed in range(permutations)
    )


def _embedding(item: dict[str, Any]) -> list[float]:
    metadata = dict(item.get("metadata") or {})
    raw = metadata.get("semantic_embedding") or metadata.get("embedding") or []
    if not isinstance(raw, (list, tuple)):
        return []
    try:
        return [float(value) for value in raw]
    except (TypeError, ValueError):
        return []


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}
