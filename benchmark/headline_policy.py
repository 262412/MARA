from __future__ import annotations

from typing import Any


def headline_policy_predictions(
    quality_predictions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    controller_predictions = [
        prediction
        for prediction in quality_predictions
        if str(prediction.get("route") or "").strip() == "controller_auto"
    ]
    if controller_predictions:
        return controller_predictions, "deployed_controller_policy"
    return quality_predictions, "quality_routes_without_controller"
