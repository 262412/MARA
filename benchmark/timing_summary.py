from __future__ import annotations

from typing import Any

from .metrics import round_metric, safe_mean

_TIMING_STAGE_KEYS = (
    "planning_seconds",
    "preparation_seconds_amortized",
    "parse_seconds",
    "index_seconds",
    "retrieval_seconds",
    "reranking_seconds",
    "generation_seconds",
    "retry_seconds",
    "verification_seconds",
    "pipeline_planning_seconds",
    "pipeline_retrieval_seconds",
    "pipeline_generation_seconds",
    "pipeline_retry_seconds",
    "pipeline_verification_seconds",
    "pipeline_finalization_seconds",
    "answerability_seconds",
    "answer_finalization_seconds",
    "total_seconds",
    "total_seconds_including_preparation",
)


def timing_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    averages = {
        f"avg_{key}": round_metric(
            safe_mean([_timing_value(item, key) for item in predictions])
        )
        for key in (
            "retrieval_seconds",
            "generation_seconds",
            "parse_seconds",
            "index_seconds",
        )
    }
    return {
        **averages,
        "timing_distribution": {
            key: _stage_distribution(predictions, key) for key in _TIMING_STAGE_KEYS
        },
        "num_route_timeouts": route_timeout_count(predictions),
    }


def route_timing_fields(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    total_distribution = _stage_distribution(predictions, "total_seconds")
    inclusive_distribution = _stage_distribution(
        predictions,
        "total_seconds_including_preparation",
    )
    return {
        "avg_total_seconds": round_metric(
            safe_mean(
                [
                    (prediction.get("performance") or {}).get("total_seconds")
                    for prediction in predictions
                ]
            )
        ),
        "median_total_seconds": total_distribution["median"],
        "p95_total_seconds": total_distribution["p95"],
        "avg_total_seconds_including_preparation": round_metric(
            safe_mean(
                [
                    (prediction.get("performance") or {}).get(
                        "total_seconds_including_preparation"
                    )
                    for prediction in predictions
                ]
            )
        ),
        "median_total_seconds_including_preparation": inclusive_distribution["median"],
        "p95_total_seconds_including_preparation": inclusive_distribution["p95"],
        "num_route_timeouts": route_timeout_count(predictions),
    }


def route_timeout_count(predictions: list[dict[str, Any]]) -> int:
    return sum(
        str(prediction.get("error_type") or "") == "route_timeout"
        for prediction in predictions
    )


def _stage_distribution(
    predictions: list[dict[str, Any]],
    key: str,
) -> dict[str, float | int | None]:
    values = [
        value
        for prediction in predictions
        if (value := _timing_value(prediction, key)) is not None
    ]
    total = len(predictions)
    return {
        "count": len(values),
        "coverage": round_metric(len(values) / total) if total else None,
        "median": round_metric(_percentile(values, 0.5)),
        "p95": round_metric(_percentile(values, 0.95)),
    }


def _timing_value(prediction: dict[str, Any], key: str) -> float | None:
    for source in (
        prediction.get("performance") or {},
        prediction.get("timings") or {},
    ):
        value = source.get(key)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def _percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight
