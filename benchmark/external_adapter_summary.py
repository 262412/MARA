from __future__ import annotations

from typing import Any

from .research_evaluators import external_research_adapter_metric_metadata


def external_adapter_summary_metadata(
    predictions: list[dict[str, Any]],
    active_routes: list[dict[str, Any]],
) -> dict[str, Any]:
    for prediction in predictions:
        metadata = prediction.get("external_adapter_metric_metadata")
        if isinstance(metadata, dict):
            return metadata
    route = active_routes[0] if active_routes else {}
    return external_research_adapter_metric_metadata(route)


def external_adapter_summary_metadata_by_route(
    predictions: list[dict[str, Any]],
    active_routes: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    metadata_by_route: dict[str, dict[str, Any]] = {}
    prediction_metadata = _prediction_metadata_by_route(predictions)
    for index, route in enumerate(active_routes, start=1):
        route_id = _route_id(route, f"route_{index}")
        metadata_by_route[route_id] = prediction_metadata.get(
            route_id,
            external_research_adapter_metric_metadata(route),
        )
    return metadata_by_route


def _prediction_metadata_by_route(
    predictions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    metadata_by_route: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        metadata = prediction.get("external_adapter_metric_metadata")
        if route and isinstance(metadata, dict) and route not in metadata_by_route:
            metadata_by_route[route] = metadata
    return metadata_by_route


def _route_id(route: dict[str, Any], fallback: str) -> str:
    return str(
        route.get("route_id")
        or route.get("id")
        or route.get("name")
        or route.get("route")
        or fallback
    )
