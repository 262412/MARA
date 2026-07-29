from __future__ import annotations

from typing import Any

from .metrics import round_metric, safe_mean


def citation_headline_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        "avg_citation_recall": _average(predictions, "citation_recall"),
        "avg_citation_precision": _average(predictions, "citation_precision"),
        "avg_emitted_citation_recall": _average(predictions, "emitted_citation_recall"),
        "avg_emitted_citation_precision": _average(
            predictions, "emitted_citation_precision"
        ),
        "avg_source_retrieval_recall": _average(predictions, "source_retrieval_recall"),
    }


def _average(
    predictions: list[dict[str, Any]],
    metric: str,
) -> float | None:
    return round_metric(
        safe_mean(
            [
                dict(prediction.get("metrics") or {}).get(metric)
                for prediction in predictions
            ]
        )
    )
