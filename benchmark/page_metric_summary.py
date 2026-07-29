from __future__ import annotations

from typing import Any

from .metrics import round_metric, safe_mean


def page_metric_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        f"avg_{metric}": round_metric(
            safe_mean(
                [
                    dict(prediction.get("metrics") or {}).get(metric)
                    for prediction in predictions
                ]
            )
        )
        for metric in (
            "strict_gold_page_coverage",
            "canonical_mapped_page_coverage",
            "equivalent_evidence_page_coverage",
        )
    }
