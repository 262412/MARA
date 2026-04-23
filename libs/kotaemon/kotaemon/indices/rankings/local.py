from __future__ import annotations

import re
from collections import Counter
from typing import Any

from kotaemon.base import Document

from .base import BaseReranking

_TOKEN_RE = re.compile(r"[A-Za-z]+|\d+|[\u3400-\u4dbf\u4e00-\u9fff]+")
_CJK_RE = re.compile(r"^[\u3400-\u4dbf\u4e00-\u9fff]+$")

_ELEMENT_KEYWORDS = {
    "table": {
        "table",
        "tables",
        "tabular",
        "\u8868",
        "\u8868\u683c",
        "\u6570\u636e\u8868",
    },
    "figure": {
        "figure",
        "fig",
        "image",
        "plot",
        "chart",
        "diagram",
        "\u56fe",
        "\u56fe\u7247",
        "\u56fe\u50cf",
    },
    "formula": {
        "formula",
        "equation",
        "latex",
        "math",
        "\u516c\u5f0f",
        "\u65b9\u7a0b",
    },
}


class LocalMultilingualReranking(BaseReranking):
    """Local lexical reranker for low-cost multilingual fallback ranking."""

    score_metadata_key: str = "local_reranking_score"
    type_boost: float = 0.25

    def run(self, documents: list[Document], query: str) -> list[Document]:
        query_tokens = _tokenize(query)
        query_counts = Counter(query_tokens)
        routed_types = _query_element_routes(query_tokens)

        scored_documents = []
        for index, document in enumerate(documents):
            metadata = dict(getattr(document, "metadata", None) or {})
            doc_tokens = _tokenize(_ranking_text(document, metadata))
            score = _overlap_score(query_counts, Counter(doc_tokens))

            element_type = _normalize_element_type(
                metadata.get("element_type", metadata.get("type"))
            )
            if element_type in routed_types:
                score += self.type_boost

            metadata[self.score_metadata_key] = score
            document.metadata = metadata
            scored_documents.append((index, score, document))

        scored_documents.sort(key=lambda item: (-item[1], item[0]))
        return [document for _, _, document in scored_documents]


def _tokenize(value: Any) -> list[str]:
    tokens: list[str] = []
    for match in _TOKEN_RE.findall(str(value or "").lower()):
        tokens.append(match)
        if _CJK_RE.match(match) and len(match) > 1:
            tokens.extend(match)
    return tokens


def _ranking_text(document: Document, metadata: dict[str, Any]) -> str:
    parts = [
        getattr(document, "text", ""),
        metadata.get("caption"),
        metadata.get("table_origin"),
        metadata.get("normalized_formula"),
        metadata.get("ocr_text"),
    ]
    return " ".join(str(part) for part in parts if part is not None)


def _overlap_score(query_counts: Counter[str], doc_counts: Counter[str]) -> float:
    if not query_counts:
        return 0.0
    overlap = sum(
        min(count, doc_counts.get(token, 0)) for token, count in query_counts.items()
    )
    return overlap / sum(query_counts.values())


def _query_element_routes(query_tokens: list[str]) -> set[str]:
    routes = set()
    query_token_set = set(query_tokens)
    for element_type, keywords in _ELEMENT_KEYWORDS.items():
        if query_token_set.intersection(keywords):
            routes.add(element_type)
    return routes


def _normalize_element_type(value: Any) -> str:
    normalized = str(value or "text").strip().lower()
    if normalized in {"image", "fig", "chart", "plot"}:
        return "figure"
    return normalized
