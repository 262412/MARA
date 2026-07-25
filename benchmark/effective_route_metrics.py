from __future__ import annotations

from typing import Any

from .multimodal_route_summary import effective_prediction_route
from .stage_metrics import prediction_stage_metrics, stage_metric_summary


def effective_route_stage_metric_table(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in _ordered_effective_routes(predictions):
        route_predictions = [
            prediction
            for prediction in predictions
            if effective_prediction_route(prediction) == route
        ]
        measured_predictions = [
            {
                **prediction,
                "stage_metrics": (
                    prediction.get("stage_metrics")
                    or prediction_stage_metrics(prediction)
                ),
            }
            for prediction in route_predictions
        ]
        rows.append(
            {
                "dataset_name": dataset_name,
                "effective_route": route,
                "num_predictions": len(route_predictions),
                **stage_metric_summary(measured_predictions),
            }
        )
    return rows


def _ordered_effective_routes(
    predictions: list[dict[str, Any]],
) -> list[str]:
    routes: list[str] = []
    for prediction in predictions:
        route = effective_prediction_route(prediction)
        if route and route not in routes:
            routes.append(route)
    return routes
