from __future__ import annotations

from typing import Any

from .metrics import round_metric, safe_mean


def answer_finalization_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    modes = [
        _answer_mode_for_prediction(item)
        for item in predictions
        if _answer_mode_for_prediction(item)
    ]
    return {
        "benchmark_answer_mode": _single_or_mixed(modes),
        "benchmark_answer_modes": _count_values(modes),
        "avg_answer_for_user_tokens": avg_answer_tokens(
            predictions,
            "answer_for_user",
        ),
        "avg_answer_for_scoring_tokens": avg_answer_tokens(
            predictions,
            "answer_for_scoring",
        ),
    }


def avg_product_metric(
    predictions: list[dict[str, Any]],
    metric: str,
) -> float | None:
    return round_metric(
        safe_mean(
            [
                (item.get("product_metrics") or {}).get(metric)
                for item in predictions
                if item.get("product_metrics")
            ]
        )
    )


def avg_answer_tokens(
    predictions: list[dict[str, Any]],
    key: str,
) -> float | None:
    return round_metric(
        safe_mean([_answer_token_count(item.get(key)) for item in predictions])
    )


def _answer_mode_for_prediction(prediction: dict[str, Any]) -> str:
    finalization = dict(prediction.get("answer_finalization") or {})
    return str(
        prediction.get("benchmark_answer_mode") or finalization.get("mode") or ""
    ).strip()


def _single_or_mixed(values: list[str]) -> str | None:
    if not values:
        return None
    unique = sorted(set(values))
    if len(unique) == 1:
        return unique[0]
    return "mixed"


def _count_values(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _answer_token_count(value: Any) -> int:
    return len(str(value or "").split())
