from __future__ import annotations

from typing import Any

_RANKING_METRIC_ORDER = {
    "avg_native_score": 0,
    "avg_mara_proxy_score": 1,
    "avg_mara_score": 2,
    "avg_f1": 3,
}


def route_ranking_markdown(summary: dict[str, Any]) -> list[str]:
    rankings = summary.get("route_rankings") or []
    lines: list[str] = []
    for ranking in sorted(
        (ranking for ranking in rankings if isinstance(ranking, dict)),
        key=_ranking_sort_key,
    ):
        rank_metric = str(ranking.get("rank_metric") or "score")
        for route in ranking.get("routes") or []:
            if not isinstance(route, dict):
                continue
            lines.append(
                f"{route.get('rank')}. `{route.get('route')}` "
                f"{rank_metric}=`{route.get('score')}`"
            )
    return lines


def _ranking_sort_key(ranking: dict[str, Any]) -> tuple[int, str]:
    rank_metric = str(ranking.get("rank_metric") or "")
    return (_RANKING_METRIC_ORDER.get(rank_metric, 100), rank_metric)
