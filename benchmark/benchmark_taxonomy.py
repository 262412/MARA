from __future__ import annotations

from collections import OrderedDict
from typing import Any

from .ragtruth_native_scores import is_ragtruth_prediction, ragtruth_native_objective

FAILURE_TAXONOMY_TYPES = (
    "answer_mismatch",
    "timeout",
    "cancelled",
    "backend_unavailable",
    "empty_retrieval",
    "false_abstention",
    "bad_citation",
    "execution_error",
    "unsupported_claim",
    "none",
)
ROUTING_TAXONOMY_TYPES = (
    "direct_baseline",
    "text_retrieval",
    "visual_retrieval",
    "element_retrieval",
    "graph_retrieval",
    "hybrid_retrieval",
    "controller",
    "guarded_controller",
    "retriever_only",
    "unknown",
)
_BACKEND_UNAVAILABLE_STATUSES = {
    "blocked",
    "missing",
    "not_configured",
    "unavailable",
    "unreachable",
}
_BAD_CITATION_FAILURES = {
    "bad_citation",
    "citation_miss",
    "missing_citation_metadata",
}


def add_prediction_taxonomy(prediction: dict[str, Any]) -> None:
    prediction["failure_taxonomy"] = classify_failure_taxonomy(prediction)
    prediction["routing_taxonomy"] = classify_routing_taxonomy(prediction)


def classify_failure_taxonomy(prediction: dict[str, Any]) -> str:
    if _is_timeout(prediction):
        return "timeout"
    if _is_cancelled(prediction):
        return "cancelled"
    if _is_backend_unavailable(prediction):
        return "backend_unavailable"
    if _is_execution_error(prediction):
        return "execution_error"
    if _is_empty_retrieval(prediction):
        return "empty_retrieval"
    if _is_false_abstention(prediction):
        return "false_abstention"
    if _is_bad_citation(prediction):
        return "bad_citation"
    if _has_unsupported_claim(prediction):
        return "unsupported_claim"
    if _is_answer_mismatch(prediction):
        return "answer_mismatch"
    return "none"


def classify_routing_taxonomy(route_or_prediction: dict[str, Any]) -> str:
    route = _route_id(route_or_prediction)
    policy = str(route_or_prediction.get("route_policy") or "").strip().lower()
    missing_backends = {
        str(item).strip().lower()
        for item in route_or_prediction.get("missing_backends", []) or []
        if str(item).strip()
    }
    if route.endswith("_retriever_only") or policy == "retriever_only":
        return "retriever_only"
    if route in {"direct", "direct_answer"} or policy == "direct":
        return "direct_baseline"
    if route in {"crag_guarded"}:
        return "guarded_controller"
    if route in {"controller_auto"}:
        return "controller"
    if route in {"text_rag", "doc_text", "doc"} or policy in {"text", "doc"}:
        return "text_retrieval"
    if route in {
        "page_image_rag_smoke",
        "page_image_rag_vlm",
        "doc_page_image",
        "page_image",
        "vlm",
    } or policy in {"visual", "page_image", "page-image"}:
        return "visual_retrieval"
    if missing_backends & {"colpali", "colqwen", "visual_generator", "vlm"}:
        return "visual_retrieval"
    if route in {"element_rag", "doc_element", "element"} or policy == "element":
        return "element_retrieval"
    if route in {"graph_rag_local", "graph_rag_global", "graph_global"} or (
        policy == "graph"
    ):
        return "graph_retrieval"
    if route in {"hybrid_rag", "hybrid"} or policy == "hybrid":
        return "hybrid_retrieval"
    return "unknown"


def failure_taxonomy_counts(
    dataset_name: str,
    predictions: list[dict[str, Any]],
    *,
    skipped_routes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    counts: OrderedDict[tuple[str, str], int] = OrderedDict()
    for prediction in predictions:
        key = (_prediction_failure_taxonomy(prediction), "prediction")
        counts[key] = counts.get(key, 0) + 1
    for route in skipped_routes or []:
        key = ("backend_unavailable", "route_skip")
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "dataset_name": dataset_name,
            "failure_taxonomy": failure_taxonomy,
            "count": count,
            "unit": unit,
        }
        for (failure_taxonomy, unit), count in counts.items()
    ]


def taxonomy_summary_fields(
    dataset_name: str,
    predictions: list[dict[str, Any]],
    *,
    skipped_routes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "failure_taxonomy_counts": failure_taxonomy_counts(
            dataset_name,
            predictions,
            skipped_routes=skipped_routes,
        ),
        "failure_taxonomy_by_route": failure_taxonomy_by_route(
            dataset_name,
            predictions,
            skipped_routes=skipped_routes,
        ),
        "routing_taxonomy_counts": routing_taxonomy_counts(dataset_name, predictions),
    }


def failure_taxonomy_by_route(
    dataset_name: str,
    predictions: list[dict[str, Any]],
    *,
    skipped_routes: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    counts: OrderedDict[tuple[str, str, str, str], int] = OrderedDict()
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        routing_taxonomy = _prediction_routing_taxonomy(prediction)
        failure_taxonomy = _prediction_failure_taxonomy(prediction)
        key = (route, routing_taxonomy, failure_taxonomy, "prediction")
        counts[key] = counts.get(key, 0) + 1
    for route_record in skipped_routes or []:
        route = _route_id(route_record)
        routing_taxonomy = classify_routing_taxonomy(route_record)
        key = (route, routing_taxonomy, "backend_unavailable", "route_skip")
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "dataset_name": dataset_name,
            "route": route,
            "routing_taxonomy": routing_taxonomy,
            "failure_taxonomy": failure_taxonomy,
            "count": count,
            "unit": unit,
        }
        for (route, routing_taxonomy, failure_taxonomy, unit), count in counts.items()
    ]


def routing_taxonomy_counts(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts: OrderedDict[str, int] = OrderedDict()
    for prediction in predictions:
        routing_taxonomy = _prediction_routing_taxonomy(prediction)
        counts[routing_taxonomy] = counts.get(routing_taxonomy, 0) + 1
    return [
        {
            "dataset_name": dataset_name,
            "routing_taxonomy": routing_taxonomy,
            "count": count,
        }
        for routing_taxonomy, count in counts.items()
    ]


def _prediction_failure_taxonomy(prediction: dict[str, Any]) -> str:
    value = str(prediction.get("failure_taxonomy") or "").strip()
    return value or classify_failure_taxonomy(prediction)


def _prediction_routing_taxonomy(prediction: dict[str, Any]) -> str:
    value = str(prediction.get("routing_taxonomy") or "").strip()
    return value or classify_routing_taxonomy(prediction)


def _is_timeout(prediction: dict[str, Any]) -> bool:
    if str(prediction.get("terminal_outcome") or "") == "timeout":
        return True
    error_type = str(prediction.get("error_type") or "").strip()
    diagnostics = dict(prediction.get("diagnostics") or {})
    return (
        error_type == "route_timeout"
        or diagnostics.get("failure_class") == "route_timeout"
    )


def _is_backend_unavailable(prediction: dict[str, Any]) -> bool:
    statuses = [
        prediction.get("backend_status"),
        prediction.get("route_backend_status"),
        (
            (prediction.get("backend_metadata") or {}).get("backend_status")
            if isinstance(prediction.get("backend_metadata"), dict)
            else None
        ),
    ]
    if any(
        str(status or "").strip().lower() in _BACKEND_UNAVAILABLE_STATUSES
        for status in statuses
    ):
        return True
    error_text = " ".join(
        str(prediction.get(key) or "").strip().lower()
        for key in ("error", "predicted_answer")
    )
    return any(
        marker in error_text
        for marker in (
            "backend is not configured",
            "backend unavailable",
            "connection refused",
            "no vlm backend is configured",
        )
    )


def _is_execution_error(prediction: dict[str, Any]) -> bool:
    if str(prediction.get("terminal_outcome") or "") == "execution_failed":
        return True
    return bool(str(prediction.get("error") or "").strip())


def _is_cancelled(prediction: dict[str, Any]) -> bool:
    return str(prediction.get("terminal_outcome") or "") == "cancelled"


def _is_empty_retrieval(prediction: dict[str, Any]) -> bool:
    diagnostics = dict(prediction.get("diagnostics") or {})
    retrieval_failure = str(diagnostics.get("retrieval_failure_type") or "").strip()
    if retrieval_failure in {"no_retrieved_hits", "raw_retriever_zero"}:
        return True
    retrieved_count = diagnostics.get("retrieved_count")
    if retrieved_count is not None:
        return int(retrieved_count or 0) == 0
    return not bool(prediction.get("retrieved_hits") or [])


def _is_false_abstention(prediction: dict[str, Any]) -> bool:
    metrics = dict(prediction.get("metrics") or {})
    observability = dict(prediction.get("verifier_observability") or {})
    return _float_positive(metrics.get("false_abstention")) or _float_positive(
        observability.get("false_abstention")
    )


def _is_bad_citation(prediction: dict[str, Any]) -> bool:
    diagnostics = dict(prediction.get("diagnostics") or {})
    citation_failure = str(diagnostics.get("citation_failure_type") or "").strip()
    if citation_failure in _BAD_CITATION_FAILURES:
        return True
    metrics = dict(prediction.get("metrics") or {})
    recall = metrics.get("citation_recall")
    gold_sources = prediction.get("gold_sources") or []
    return bool(gold_sources) and recall is not None and float(recall or 0.0) == 0.0


def _has_unsupported_claim(prediction: dict[str, Any]) -> bool:
    observability = dict(prediction.get("verifier_observability") or {})
    metrics = dict(prediction.get("metrics") or {})
    return _float_positive(observability.get("has_unsupported_claim")) or (
        _float_positive(metrics.get("unsupported_claim_rate"))
    )


def _is_answer_mismatch(prediction: dict[str, Any]) -> bool:
    if is_ragtruth_prediction(prediction):
        native_score = ragtruth_native_objective(prediction)
        return native_score is None or native_score == 0.0
    metrics = dict(prediction.get("metrics") or {})
    for key in ("native_score", "f1", "em", "anls"):
        value = metrics.get(key)
        if value is not None:
            return float(value or 0.0) == 0.0
    return False


def _float_positive(value: Any) -> bool:
    try:
        return float(value or 0.0) > 0.0
    except (TypeError, ValueError):
        return False


def _route_id(route_or_prediction: dict[str, Any]) -> str:
    return (
        str(
            route_or_prediction.get("route")
            or route_or_prediction.get("route_id")
            or route_or_prediction.get("id")
            or ""
        )
        .strip()
        .lower()
    )
