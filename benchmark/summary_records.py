from __future__ import annotations

from typing import Any


def benchmark_identity_summary(
    bundle: Any,
    config: Any,
    active_routes: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    skipped_routes: list[dict[str, Any]],
) -> dict[str, Any]:
    num_skipped_routes = len(skipped_routes)
    return {
        "dataset_name": bundle.dataset_name,
        "manifest_path": str(bundle.manifest_path),
        "suite_name": config.suite_name,
        "engine": config.engine if len(active_routes) == 1 else "matrix",
        "route": config.route,
        "scope": config.scope,
        "num_documents": len(bundle.documents),
        "num_examples": len(bundle.examples),
        "num_routes": len(active_routes),
        "num_executed_routes": len(active_routes) - num_skipped_routes,
        "num_skipped_routes": num_skipped_routes,
        "skipped_routes": skipped_routes,
        "not_configured_routes": [
            item
            for item in skipped_routes
            if item.get("backend_status") == "not_configured"
        ],
        "num_predictions": len(predictions),
    }


def per_example_metric_records(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records = []
    for prediction in predictions:
        metrics = dict(prediction.get("metrics") or {})
        error_type = str(prediction.get("error_type") or "")
        records.append(
            {
                "dataset": dataset_name,
                "example_id": str(prediction.get("example_id") or ""),
                "route": str(prediction.get("route") or ""),
                "deployed_policy": str(prediction.get("headline_role") or ""),
                "primary_score": metrics.get("native_score"),
                "metrics": metrics,
                "error": prediction.get("error"),
                "error_type": error_type,
                "timed_out": error_type == "route_timeout",
            }
        )
    return records


def adapter_metadata_summary(
    *,
    adapter_metric_metadata: dict[str, dict[str, Any]] | None,
    external_adapter_metric_metadata: dict[str, Any] | None,
    external_adapter_metric_metadata_by_route: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "adapter_metric_metadata": adapter_metric_metadata or {},
        "external_adapter_metric_metadata": external_adapter_metric_metadata or {},
        "external_adapter_metric_metadata_by_route": (
            external_adapter_metric_metadata_by_route or {}
        ),
    }
