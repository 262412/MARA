from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Protocol


class ElementRetrieverBackend(Protocol):
    name: str

    def score(self, query: str, record: dict[str, Any]) -> float:
        ...


class LocalElementRetriever:
    name = "local_element_retriever"
    backend_type = "deterministic_metadata"

    def score(self, query: str, record: dict[str, Any]) -> float:
        query_tokens = _tokens(query)
        if not query_tokens:
            return 0.0
        element_tokens = _tokens(
            " ".join(
                str(record.get(key) or "")
                for key in (
                    "element_id",
                    "element_type",
                    "modality",
                    "caption",
                    "text",
                )
            )
        )
        return round(len(query_tokens & element_tokens) / len(query_tokens), 4)


def rank_element_records(
    query: str,
    records: list[dict[str, Any]],
    *,
    retriever: ElementRetrieverBackend | None = None,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    backend = retriever or LocalElementRetriever()
    scored = [
        (_score_record(backend, query, record), index, record)
        for index, record in enumerate(records)
    ]
    scored.sort(key=lambda item: (-item[0], item[1]))
    scores = {
        str(record.get("evidence_id") or "").strip(): score
        for score, _, record in scored
        if str(record.get("evidence_id") or "").strip()
    }
    ranked = [
        _with_score_metadata(
            record,
            score,
            backend.name,
            getattr(backend, "backend_type", "custom"),
        )
        for score, _, record in scored
    ]
    return ranked, scores


def _score_record(
    backend: ElementRetrieverBackend,
    query: str,
    record: dict[str, Any],
) -> float:
    return round(float(backend.score(query, record) or 0.0), 4)


def _with_score_metadata(
    record: dict[str, Any],
    score: float,
    retriever_name: str,
    backend_type: str,
) -> dict[str, Any]:
    updated = deepcopy(record)
    metadata = dict(updated.get("metadata") or {})
    metadata["element_retriever"] = retriever_name
    metadata["element_retriever_backend_type"] = backend_type
    metadata["element_retriever_score"] = score
    updated["metadata"] = metadata
    return updated


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
