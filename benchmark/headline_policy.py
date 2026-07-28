from __future__ import annotations

from typing import Any


def headline_policy_predictions(
    quality_predictions: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str]:
    deployed_predictions = [
        prediction
        for prediction in quality_predictions
        if str(prediction.get("headline_role") or "").strip() == "deployed_policy"
    ]
    if deployed_predictions:
        return deployed_predictions, "deployed_manifest_policy"
    has_manifest_roles = any(
        str(prediction.get("headline_role") or "").strip()
        for prediction in quality_predictions
    )
    if has_manifest_roles:
        return quality_predictions, "quality_routes_without_deployed_policy"
    controller_predictions = [
        prediction
        for prediction in quality_predictions
        if str(prediction.get("route") or "").strip() == "controller_auto"
    ]
    if controller_predictions:
        return controller_predictions, "deployed_controller_policy"
    return quality_predictions, "quality_routes_without_controller"
