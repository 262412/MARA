from __future__ import annotations

from typing import Any

from .benchmark_taxonomy import taxonomy_summary_fields
from .diagnostics import (
    dataset_route_diagnostics,
    diagnostic_failure_counts,
    route_confusion_table,
)
from .verifier_observability import route_verifier_observability_table


def diagnostic_summary_fields(
    dataset_name: str,
    predictions: list[dict[str, Any]],
    *,
    skipped_routes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "dataset_route_diagnostics": dataset_route_diagnostics(
            dataset_name,
            predictions,
        ),
        "diagnostic_failure_counts": diagnostic_failure_counts(
            dataset_name,
            predictions,
        ),
        **taxonomy_summary_fields(
            dataset_name,
            predictions,
            skipped_routes=skipped_routes,
        ),
        "verifier_observability_by_route": route_verifier_observability_table(
            dataset_name,
            predictions,
        ),
        "route_confusion_table": route_confusion_table(dataset_name, predictions),
    }
