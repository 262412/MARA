from __future__ import annotations

from typing import Any, Callable

SELECTION_SCORE_CONTRACT = "single_stage_per_query_rank_normalized_v2"
_SCORE_FIELDS = (
    "learned_score",
    "reranking_score",
    "reranker_score",
    "hybrid_fusion_score",
    "visual_retriever_score",
    "element_retriever_score",
    "retriever_score",
    "score",
)


def normalized_selection_scores(
    items: list[dict[str, Any]],
    *,
    identity_of: Callable[[dict[str, Any]], str],
) -> list[dict[str, Any]]:
    normalized_by_identity: dict[str, float] = {}
    sources_by_identity: dict[str, list[str]] = {}
    selected_field = _selection_score_field(items)
    if selected_field:
        rows = _ranked_field_rows(items, selected_field)
        denominator = max(1, len(rows) - 1)
        for rank, (_value, _index, item) in enumerate(rows):
            identity = identity_of(item)
            normalized = 1.0 - rank / denominator if len(rows) > 1 else 1.0
            normalized_by_identity[identity] = normalized
            sources_by_identity.setdefault(identity, []).append(selected_field)
    output: list[dict[str, Any]] = []
    for item in items:
        identity = identity_of(item)
        scored = dict(item)
        scored["_selection_relevance_score"] = normalized_by_identity.get(
            identity,
            0.0,
        )
        scored["_selection_relevance_sources"] = list(
            dict.fromkeys(sources_by_identity.get(identity, []))
        )
        output.append(scored)
    return output


def _selection_score_field(items: list[dict[str, Any]]) -> str:
    ranked_fields = [
        (field, len(_ranked_field_rows(items, field))) for field in _SCORE_FIELDS
    ]
    complete = [
        field for field, count in ranked_fields if items and count == len(items)
    ]
    if complete:
        return complete[0]
    return max(ranked_fields, key=lambda row: row[1], default=("", 0))[0]


def without_selection_annotations(item: dict[str, Any]) -> dict[str, Any]:
    output = dict(item)
    output.pop("_selection_relevance_score", None)
    output.pop("_selection_relevance_sources", None)
    return output


def _ranked_field_rows(
    items: list[dict[str, Any]],
    field: str,
) -> list[tuple[float, int, dict[str, Any]]]:
    rows: list[tuple[float, int, dict[str, Any]]] = []
    for index, item in enumerate(items):
        value = _score_field_value(item, field)
        if value is not None:
            rows.append((value, index, item))
    return sorted(rows, key=lambda row: (-row[0], row[1]))


def _score_field_value(item: dict[str, Any], field: str) -> float | None:
    metadata = dict(item.get("metadata") or {})
    value = metadata.get(field, item.get(field))
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
