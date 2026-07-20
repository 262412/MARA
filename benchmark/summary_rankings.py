from __future__ import annotations

from typing import Any

RANKING_METRICS = (
    "avg_native_score",
    "avg_semantic_answer_f1",
    "avg_mara_proxy_score",
    "avg_mara_score",
    "avg_f1",
)


def route_rankings(
    dataset_name: str,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        ranking
        for metric in RANKING_METRICS
        for ranking in [_route_ranking(dataset_name, rows, metric)]
        if ranking is not None
    ]


def _route_ranking(
    dataset_name: str,
    rows: list[dict[str, Any]],
    metric: str,
) -> dict[str, Any] | None:
    ranked = [
        (row["route"], row[metric]) for row in rows if row.get(metric) is not None
    ]
    ranked.sort(key=lambda item: (-float(item[1]), item[0]))
    if not ranked:
        return None
    return {
        "dataset_name": dataset_name,
        "rank_metric": metric,
        "routes": [
            {"rank": index, "route": route, "score": score}
            for index, (route, score) in enumerate(ranked, start=1)
        ],
    }
