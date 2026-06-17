from __future__ import annotations

from typing import Any

from .diagnostics import (
    dataset_route_diagnostics,
    diagnostic_failure_counts,
    route_confusion_table,
)
from .mara_oriented_scores import MARA_METRIC_KEYS, mara_score_metadata
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
        "dataset_route_diagnostics": dataset_route_diagnostics(
            bundle.dataset_name,
            predictions,
        ),
        "diagnostic_failure_counts": diagnostic_failure_counts(
            bundle.dataset_name,
            predictions,
        ),
        "route_confusion_table": route_confusion_table(
            bundle.dataset_name,
            predictions,
        ),
        "quality_route_metric_table": _route_metric_table(
            bundle.dataset_name,
            _role_predictions(predictions, {"qa_quality"}),
        ),
        "diagnostic_route_metric_table": _route_metric_table(
            bundle.dataset_name,
            _role_predictions(predictions, {"diagnostic", "prototype"}),
        ),
        **_quality_route_summary(predictions),
        "route_rankings": _route_rankings(bundle.dataset_name, predictions),
        "mara_score_metadata": mara_score_metadata(bundle.dataset_name),
        "backend_metadata": backend_metadata,
        "adapter_metric_metadata": adapter_metric_metadata or {},
        "external_adapter_metric_metadata": external_adapter_metric_metadata or {},
        "external_adapter_metric_metadata_by_route": (
            external_adapter_metric_metadata_by_route or {}
        ),
    }


def add_mara_summary_fields(
    summary: dict[str, Any],
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    dataset_name = str(summary.get("dataset_name") or "unknown")
    return {
        **dict(summary),
        **_mara_metric_summary(predictions),
        "route_metric_table": _route_metric_table(dataset_name, predictions),
        "quality_route_metric_table": _route_metric_table(
            dataset_name,
            _role_predictions(predictions, {"qa_quality"}),
        ),
        "diagnostic_route_metric_table": _route_metric_table(
            dataset_name,
            _role_predictions(predictions, {"diagnostic", "prototype"}),
        ),
        **_quality_route_summary(predictions),
        "route_rankings": _route_rankings(dataset_name, predictions),
        "mara_score_metadata": mara_score_metadata(dataset_name),
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
        **_citation_locator_summary(predictions),
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
        **_mara_metric_summary(predictions),
    }


def _quality_route_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    quality_predictions = _role_predictions(predictions, {"qa_quality"})
    return {
        "quality_avg_em": _avg_metric(quality_predictions, "em"),
        "quality_avg_f1": _avg_metric(quality_predictions, "f1"),
        "quality_avg_mara_score": _avg_metric(quality_predictions, "mara_score"),
        "quality_avg_numeric_match": _avg_metric(quality_predictions, "numeric_match"),
    }


def _mara_metric_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        f"avg_{metric}": _avg_metric(predictions, metric) for metric in MARA_METRIC_KEYS
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
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        f"avg_{modality}_hit": _avg_metric(predictions, f"{modality}_hit")
        for modality in ("table", "figure", "formula", "slide")
    }


def _citation_locator_summary(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    return {
        f"avg_citation_{metric}_{locator}": _avg_metric(
            predictions, f"citation_{metric}_{locator}"
        )
        for metric in ("recall", "precision")
        for locator in ("source", "page", "span")
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
                **_mara_metric_summary(route_predictions),
                "avg_anls": _avg_metric(route_predictions, "anls"),
                "avg_page_hit": _avg_metric(route_predictions, "page_hit"),
                "avg_citation_recall": _avg_metric(
                    route_predictions, "citation_recall"
                ),
                "avg_citation_precision": _avg_metric(
                    route_predictions, "citation_precision"
                ),
                **_citation_locator_summary(route_predictions),
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
                "benchmark_role": _route_role(route_predictions),
            }
        )
    return rows


def _route_rankings(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows = _route_metric_table(dataset_name, predictions)
    return [
        ranking
        for metric in ("avg_f1", "avg_mara_score")
        for ranking in [_route_ranking(dataset_name, rows, metric)]
        if ranking is not None
    ]


def _route_ranking(
    dataset_name: str,
    rows: list[dict[str, Any]],
    metric: str,
) -> dict[str, Any] | None:
    ranked = [
        (row["route"], row[metric]) for row in rows if row.get(metric) is not None
    ]
    ranked.sort(key=lambda item: (-float(item[1]), item[0]))
    if not ranked:
        return None
    return {
        "dataset_name": dataset_name,
        "rank_metric": metric,
        "routes": [
            {"rank": index, "route": route, "score": score}
            for index, (route, score) in enumerate(ranked, start=1)
        ],
    }


def _ordered_routes(predictions: list[dict[str, Any]]) -> list[str]:
    routes: list[str] = []
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        if route and route not in routes:
            routes.append(route)
    return routes


def _role_predictions(
    predictions: list[dict[str, Any]],
    roles: set[str],
) -> list[dict[str, Any]]:
    return [
        prediction
        for prediction in predictions
        if str(prediction.get("benchmark_role") or "qa_quality") in roles
    ]


def _route_role(predictions: list[dict[str, Any]]) -> str:
    for prediction in predictions:
        role = str(prediction.get("benchmark_role") or "").strip()
        if role:
            return role
    return "qa_quality"
