from __future__ import annotations

from typing import Any

from .metrics import round_metric, safe_mean
from .verification_metrics import verification_summary


def build_benchmark_summary(
    *,
    bundle: Any,
    config: Any,
    active_routes: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    backend_metadata: dict[str, dict[str, Any]],
    skipped_routes: list[dict[str, Any]] | None = None,
    adapter_metric_metadata: dict[str, dict[str, Any]] | None = None,
    external_adapter_metric_metadata: dict[str, Any] | None = None,
    external_adapter_metric_metadata_by_route: dict[str, Any] | None = None,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    skipped_routes = skipped_routes or []
    return {
        **_identity_summary(bundle, config, active_routes, predictions, skipped_routes),
        **(selection or {}),
        **_quality_summary(predictions),
        **_format_guardrail_summary(predictions),
        **verification_summary(predictions),
        **_timing_summary(predictions),
        **_cache_summary(predictions, config.cache_mode),
        "route_metric_table": _route_metric_table(bundle.dataset_name, predictions),
        "route_rankings": _route_rankings(bundle.dataset_name, predictions),
        "backend_metadata": backend_metadata,
        "adapter_metric_metadata": adapter_metric_metadata or {},
        "external_adapter_metric_metadata": external_adapter_metric_metadata or {},
        "external_adapter_metric_metadata_by_route": (
            external_adapter_metric_metadata_by_route or {}
        ),
    }


def _identity_summary(
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


def _quality_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "avg_em": _avg_metric(predictions, "em"),
        "avg_f1": _avg_metric(predictions, "f1"),
        "avg_anls": _avg_metric(predictions, "anls"),
        "avg_page_hit": _avg_metric(predictions, "page_hit"),
        "avg_citation_recall": _avg_metric(predictions, "citation_recall"),
        "avg_citation_precision": _avg_metric(predictions, "citation_precision"),
        "avg_element_hit": _avg_metric(predictions, "element_hit"),
        **_multimodal_hit_summary(predictions),
        "avg_span_recall": _avg_metric(predictions, "span_recall"),
        "avg_image_quote_hit": _avg_metric(predictions, "image_quote_hit"),
        "avg_cross_page_evidence_hit": _avg_metric(
            predictions, "cross_page_evidence_hit"
        ),
        "avg_multimodal_answer_support": _avg_metric(
            predictions, "multimodal_answer_support"
        ),
        "avg_hard_negative_rejection": _avg_metric(
            predictions, "hard_negative_rejection"
        ),
        "avg_formula_match": _avg_metric(predictions, "formula_match"),
        "avg_numeric_match": _avg_metric(predictions, "numeric_match"),
        "avg_abstention_rate": _avg_metric(predictions, "abstained"),
        "avg_false_abstention": _avg_metric(predictions, "false_abstention"),
    }


def _format_guardrail_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "avg_markdown_table_renderable": _avg_metric(
            predictions, "markdown_table_renderable"
        ),
        "avg_latex_renderable": _avg_metric(predictions, "latex_renderable"),
        "avg_rewrite_skipped": _avg_metric(predictions, "rewrite_skipped"),
        "avg_guardrail_expectation_match": _avg_metric(
            predictions, "guardrail_expectation_match"
        ),
    }


def _timing_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"avg_{key}": round_metric(
            safe_mean([item["timings"][key] for item in predictions])
        )
        for key in (
            "retrieval_seconds",
            "generation_seconds",
            "parse_seconds",
            "index_seconds",
        )
    }


def _cache_summary(
    predictions: list[dict[str, Any]],
    cache_mode: str,
) -> dict[str, Any]:
    return {
        "cache_mode": cache_mode,
        "parse_cache_hits": _sum_cache_stat(predictions, "parse", "hits"),
        "parse_cache_misses": _sum_cache_stat(predictions, "parse", "misses"),
        "parse_cache_writes": _sum_cache_stat(predictions, "parse", "writes"),
        "parse_cache_hit_rate": _cache_hit_rate(predictions, "parse"),
        "embedding_cache_hits": _sum_cache_stat(predictions, "embedding", "hits"),
        "embedding_cache_misses": _sum_cache_stat(predictions, "embedding", "misses"),
        "embedding_cache_writes": _sum_cache_stat(predictions, "embedding", "writes"),
        "embedding_cache_hit_rate": _cache_hit_rate(predictions, "embedding"),
    }


def _avg_metric(predictions: list[dict[str, Any]], metric: str) -> float | None:
    return round_metric(
        safe_mean([item["metrics"].get(metric) for item in predictions])
    )


def _sum_cache_stat(predictions: list[dict[str, Any]], section: str, stat: str) -> int:
    return sum(
        int(((prediction.get("cache") or {}).get(section) or {}).get(stat, 0) or 0)
        for prediction in predictions
    )


def _cache_hit_rate(predictions: list[dict[str, Any]], section: str) -> float | None:
    hits = _sum_cache_stat(predictions, section, "hits")
    misses = _sum_cache_stat(predictions, section, "misses")
    total = hits + misses
    if total == 0:
        return None
    return round_metric(hits / total)


def _multimodal_hit_summary(
    predictions: list[dict[str, Any]]
) -> dict[str, float | None]:
    return {
        f"avg_{modality}_hit": _avg_metric(predictions, f"{modality}_hit")
        for modality in ("table", "figure", "formula", "slide")
    }


def _route_metric_table(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in _ordered_routes(predictions):
        route_predictions = [
            prediction
            for prediction in predictions
            if str(prediction.get("route") or "") == route
        ]
        rows.append(
            {
                "dataset_name": dataset_name,
                "route": route,
                "num_predictions": len(route_predictions),
                "avg_em": _avg_metric(route_predictions, "em"),
                "avg_f1": _avg_metric(route_predictions, "f1"),
                "avg_anls": _avg_metric(route_predictions, "anls"),
                "avg_page_hit": _avg_metric(route_predictions, "page_hit"),
                "avg_citation_recall": _avg_metric(
                    route_predictions, "citation_recall"
                ),
                "avg_citation_precision": _avg_metric(
                    route_predictions, "citation_precision"
                ),
                "avg_unsupported_claim_rate": _avg_metric(
                    route_predictions, "unsupported_claim_rate"
                ),
                "avg_abstention_rate": _avg_metric(route_predictions, "abstained"),
                "avg_multimodal_answer_support": _avg_metric(
                    route_predictions, "multimodal_answer_support"
                ),
                "avg_total_seconds": round_metric(
                    safe_mean(
                        [
                            (prediction.get("performance") or {}).get("total_seconds")
                            for prediction in route_predictions
                        ]
                    )
                ),
            }
        )
    return rows


def _route_rankings(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = _route_metric_table(dataset_name, predictions)
    ranked = [
        (row["route"], row["avg_f1"]) for row in rows if row.get("avg_f1") is not None
    ]
    ranked.sort(key=lambda item: (-float(item[1]), item[0]))
    return (
        [
            {
                "dataset_name": dataset_name,
                "rank_metric": "avg_f1",
                "routes": [
                    {"rank": index, "route": route, "score": score}
                    for index, (route, score) in enumerate(ranked, start=1)
                ],
            }
        ]
        if ranked
        else []
    )


def _ordered_routes(predictions: list[dict[str, Any]]) -> list[str]:
    routes: list[str] = []
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        if route and route not in routes:
            routes.append(route)
    return routes
