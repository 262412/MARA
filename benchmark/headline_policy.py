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
    if len(deployed_predictions) == 1:
        return deployed_predictions, "deployed_manifest_policy"
    if len(deployed_predictions) > 1:
        ensemble_policies = {
            str(prediction.get("headline_ensemble_policy") or "").strip()
            for prediction in deployed_predictions
            if str(prediction.get("headline_ensemble_policy") or "").strip()
        }
        if len(ensemble_policies) == 1:
            policy = next(iter(ensemble_policies))
            return deployed_predictions, f"deployed_manifest_ensemble:{policy}"
        raise ValueError(
            "Benchmark manifest must declare exactly one deployed_policy "
            "or one shared headline_ensemble_policy."
        )
    has_manifest_roles = any(
        str(prediction.get("headline_role") or "").strip()
        for prediction in quality_predictions
    )
    if has_manifest_roles:
        raise ValueError(
            "Benchmark manifest must declare exactly one deployed_policy "
            "when headline_role is configured."
        )
    controller_predictions = [
        prediction
        for prediction in quality_predictions
        if str(prediction.get("route") or "").strip() == "controller_auto"
    ]
    if controller_predictions:
        return controller_predictions, "deployed_controller_policy"
    return quality_predictions, "quality_routes_without_controller"
