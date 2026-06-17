from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Protocol


class VisualRetrieverBackend(Protocol):
    name: str

    def score(self, query: str, record: dict[str, Any]) -> float:
        ...


class VisualGeneratorBackend(Protocol):
    name: str

    def generate(self, request: Any, bundle: Any) -> str:
        ...


class LocalLateInteractionVisualRetriever:
    name = "local_late_interaction"
    backend_type = "deterministic_smoke"

    def score(self, query: str, record: dict[str, Any]) -> float:
        query_tokens = _tokens(query)
        if not query_tokens:
            return 0.0
        metadata = dict(record.get("metadata") or {})
        late_tokens = _tokens_from_value(metadata.get("late_interaction_tokens"))
        visual_tokens = _tokens_from_value(metadata.get("visual_embedding_tokens"))
        text_tokens = _tokens(
            " ".join(
                str(record.get(key) or "")
                for key in ("caption", "ocr_text", "text", "vlm_text")
            )
        )
        late_hit = len(query_tokens & (late_tokens | visual_tokens))
        text_hit = len(query_tokens & text_tokens)
        return round((late_hit * 2 + text_hit) / max(len(query_tokens), 1), 4)


def rank_page_image_records(
    query: str,
    records: list[dict[str, Any]],
    *,
    retriever: VisualRetrieverBackend | None = None,
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    backend = retriever or LocalLateInteractionVisualRetriever()
    scored = [
        (score, index, record)
        for index, (score, record) in enumerate(
            zip(_score_records(backend, query, records), records)
        )
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


def _score_records(
    backend: VisualRetrieverBackend,
    query: str,
    records: list[dict[str, Any]],
) -> list[float]:
    score_many = getattr(backend, "score_many", None)
    if callable(score_many):
        scores = [round(float(score or 0.0), 4) for score in score_many(query, records)]
        if len(scores) != len(records):
            raise ValueError("Visual retriever score_many returned wrong score count.")
        return scores
    return [_score_record(backend, query, record) for record in records]


def _score_record(
    backend: VisualRetrieverBackend,
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
    metadata["visual_retriever"] = retriever_name
    metadata["visual_retriever_backend_type"] = backend_type
    metadata["visual_retriever_score"] = score
    updated["metadata"] = metadata
    return updated


def _tokens_from_value(value: Any) -> set[str]:
    if isinstance(value, list):
        return _tokens(" ".join(str(item) for item in value))
    return _tokens(str(value or ""))


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
