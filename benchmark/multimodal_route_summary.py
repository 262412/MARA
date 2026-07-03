from __future__ import annotations

from typing import Any

from .element_coverage_report import element_coverage_report
from .metrics import round_metric, safe_mean

_PAGE_IMAGE_ROUTE = "page_image_rag_vlm"
_ELEMENT_ROUTES = {"element_rag"}
_HYBRID_ROUTES = {"hybrid_rag"}
_GRAPH_ROUTE_TOKEN = "graph"


def phase3_multimodal_summary(
    dataset_name: str,
    predictions: list[dict[str, Any]],
    *,
    backend_metadata: dict[str, dict[str, Any]] | None = None,
    skipped_routes: list[dict[str, Any]] | None = None,
    active_routes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    backend_metadata = backend_metadata or {}
    skipped_routes = skipped_routes or []
    active_route_ids = _route_ids(active_routes or [])
    observed_routes = _prediction_routes(predictions)
    route_ids = active_route_ids | observed_routes | set(backend_metadata)
    return {
        "dataset_name": dataset_name,
        "page_image": _page_image_summary(
            route_ids,
            observed_routes,
            backend_metadata,
            skipped_routes,
        ),
        "element": _element_summary(predictions, route_ids),
        "hybrid": _hybrid_summary(dataset_name, predictions),
        "graph": _graph_summary(route_ids),
    }


def _page_image_summary(
    route_ids: set[str],
    observed_routes: set[str],
    backend_metadata: dict[str, dict[str, Any]],
    skipped_routes: list[dict[str, Any]],
) -> dict[str, Any]:
    metadata = dict(backend_metadata.get(_PAGE_IMAGE_ROUTE) or {})
    skipped = _skipped_route(skipped_routes, _PAGE_IMAGE_ROUTE)
    missing_backends = list(skipped.get("missing_backends") or [])
    if skipped.get("backend_status") == "not_configured":
        status = "blocked_backend"
    elif _has_live_vlm_backend(metadata):
        status = "vlm_live"
    elif _PAGE_IMAGE_ROUTE in observed_routes:
        status = "vlm_route_observed"
    elif _looks_like_evidence_only_smoke(metadata, skipped):
        status = "evidence_only_smoke"
    else:
        status = (
            "not_evaluated" if _PAGE_IMAGE_ROUTE not in route_ids else "blocked_backend"
        )
    return {
        "status": status,
        "route": _PAGE_IMAGE_ROUTE,
        "visual_retriever": metadata.get("visual_retriever"),
        "visual_generator": metadata.get("generator_backend"),
        "requires_backend_config": bool(metadata.get("requires_backend_config")),
        "missing_backends": missing_backends,
    }


def _element_summary(
    predictions: list[dict[str, Any]],
    route_ids: set[str],
) -> dict[str, Any]:
    element_predictions = [
        prediction
        for prediction in predictions
        if str(prediction.get("route") or "") in _ELEMENT_ROUTES
    ]
    observed = bool(element_predictions or (route_ids & _ELEMENT_ROUTES))
    index_counts = [
        len(((prediction.get("evidence_metadata") or {}).get("element_index") or []))
        for prediction in element_predictions
    ]
    coverage = element_coverage_report(element_predictions)
    predictions_with_index = int(coverage["predictions_with_element_index"])
    avg_index_records = round_metric(
        safe_mean([float(count) for count in index_counts])
    )
    avg_element_hit = _avg_metric(element_predictions, "element_hit")
    status = "not_evaluated"
    if observed:
        status = (
            "index_coverage_present"
            if predictions_with_index > 0
            else "index_coverage_gap"
        )
    return {
        "status": status,
        "routes": sorted(_ELEMENT_ROUTES & route_ids),
        "predictions_with_element_index": predictions_with_index,
        "avg_element_index_records": avg_index_records,
        "avg_element_hit": avg_element_hit,
        "coverage_report": coverage,
    }


def _hybrid_summary(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    if not any(
        str(prediction.get("route") or "") in _HYBRID_ROUTES
        for prediction in predictions
    ):
        return {
            "status": "not_evaluated",
            "question_type_route_metrics": [],
        }
    rows = _question_type_route_metrics(dataset_name, predictions)
    return {
        "status": "question_type_breakdown_available" if rows else "not_evaluated",
        "question_type_route_metrics": rows,
    }


def _graph_summary(route_ids: set[str]) -> dict[str, Any]:
    return {
        "scope": "local_lightweight_only",
        "full_graphrag_claim": False,
        "routes": sorted(route for route in route_ids if _GRAPH_ROUTE_TOKEN in route),
    }


def _question_type_route_metrics(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for question_type, route in _ordered_question_type_routes(predictions):
        route_predictions = [
            prediction
            for prediction in predictions
            if str(prediction.get("route") or "") == route
            and _question_type(prediction.get("question")) == question_type
        ]
        if route_predictions:
            rows.append(
                _question_type_route_row(
                    dataset_name, question_type, route, route_predictions
                )
            )
    return rows


def _question_type_route_row(
    dataset_name: str,
    question_type: str,
    route: str,
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "dataset_name": dataset_name,
        "question_type": question_type,
        "route": route,
        "count": len(predictions),
        "avg_f1": _avg_metric(predictions, "f1"),
        "avg_native_score": _avg_metric(predictions, "native_score"),
        "avg_page_hit": _avg_metric(predictions, "page_hit"),
    }


def _ordered_question_type_routes(
    predictions: list[dict[str, Any]],
) -> list[tuple[str, str]]:
    seen: list[tuple[str, str]] = []
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        if not route:
            continue
        item = (_question_type(prediction.get("question")), route)
        if item not in seen:
            seen.append(item)
    return seen


def _question_type(question: Any) -> str:
    text = str(question or "").lower()
    if any(
        term in text
        for term in ("slide", "image", "figure", "chart", "diagram", "visual", "page")
    ):
        return "visual_page"
    if any(term in text for term in ("table", "row", "column")):
        return "element_table"
    if any(
        term in text
        for term in ("number", "amount", "revenue", "percent", "percentage", "how many")
    ):
        return "numeric"
    if any(
        term in text for term in ("summarize", "compare", "relationship", "overview")
    ):
        return "synthesis_graph"
    return "text"


def _avg_metric(predictions: list[dict[str, Any]], metric: str) -> float | None:
    return round_metric(
        safe_mean(
            [
                (prediction.get("metrics") or {}).get(metric)
                for prediction in predictions
            ]
        )
    )


def _route_ids(routes: list[dict[str, Any]]) -> set[str]:
    return {
        route_id
        for route in routes
        for route_id in [str(route.get("route_id") or route.get("route") or "").strip()]
        if route_id
    }


def _prediction_routes(predictions: list[dict[str, Any]]) -> set[str]:
    return {
        route
        for prediction in predictions
        for route in [str(prediction.get("route") or "").strip()]
        if route
    }


def _skipped_route(
    skipped_routes: list[dict[str, Any]],
    route_id: str,
) -> dict[str, Any]:
    for route in skipped_routes:
        skipped_id = str(route.get("route_id") or route.get("route") or "").strip()
        if skipped_id == route_id:
            return route
    return {}


def _has_live_vlm_backend(metadata: dict[str, Any]) -> bool:
    return bool(metadata.get("visual_retriever") and metadata.get("generator_backend"))


def _looks_like_evidence_only_smoke(
    metadata: dict[str, Any],
    skipped: dict[str, Any],
) -> bool:
    values = {
        str(metadata.get("generator_backend") or "").lower(),
        str(metadata.get("backend_status") or "").lower(),
        str(skipped.get("skip_reason") or "").lower(),
    }
    return any("evidence" in value and "smoke" in value for value in values)
