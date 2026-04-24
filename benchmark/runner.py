from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

from .manifest import load_manifest
from .metrics import (
    anls_score,
    citation_recall_score,
    element_hit_score,
    exact_match_score,
    formula_normalized_match_score,
    numeric_tolerance_score,
    page_hit_score,
    recall_score,
    round_metric,
    safe_mean,
    span_recall_score,
    token_f1_score,
)
from .schemas import BenchmarkConfig, ManifestBundle
from .engines import EngineRunResult, get_engine


def _score_prediction(prediction: dict[str, Any]) -> dict[str, float | None]:
    gold_answers = prediction["gold_answers"]
    predicted_answer = prediction["predicted_answer"]
    metrics = {
        "em": exact_match_score(predicted_answer, gold_answers),
        "f1": token_f1_score(predicted_answer, gold_answers),
        "anls": anls_score(predicted_answer, gold_answers),
        "formula_match": formula_normalized_match_score(predicted_answer, gold_answers),
        "numeric_match": numeric_tolerance_score(predicted_answer, gold_answers),
        "page_hit": page_hit_score(
            prediction["predicted_pages"], prediction["gold_pages"]
        ),
        "citation_recall": recall_score(
            prediction["predicted_sources"], prediction["gold_sources"]
        ),
    }
    gold_evidence = prediction.get("gold_evidence", [])
    if gold_evidence:
        metrics["element_hit"] = element_hit_score(
            prediction.get("predicted_element_ids", []), gold_evidence
        )
        metrics["span_recall"] = span_recall_score(predicted_answer, gold_evidence)
        metrics["citation_recall"] = citation_recall_score(
            prediction["predicted_sources"], gold_evidence
        )
    return metrics


_TIMING_KEYS = (
    "parse_seconds",
    "index_seconds",
    "retrieval_seconds",
    "generation_seconds",
)
_CACHE_KEYS = ("hits", "misses", "writes")


def _normalize_timings(timings: dict[str, Any] | None) -> dict[str, float]:
    source = timings or {}
    return {key: round(float(source.get(key, 0.0) or 0.0), 4) for key in _TIMING_KEYS}


def _normalize_cache_stats(stats: dict[str, Any] | None) -> dict[str, int]:
    source = stats or {}
    return {key: int(source.get(key, 0) or 0) for key in _CACHE_KEYS}


def _normalize_cache(cache: dict[str, Any] | None) -> dict[str, dict[str, int]]:
    source = cache or {}
    return {
        "parse": _normalize_cache_stats(source.get("parse")),
        "embedding": _normalize_cache_stats(source.get("embedding")),
    }


def _performance_from_timings(timings: dict[str, float]) -> dict[str, Any]:
    return {
        **timings,
        "total_seconds": round(sum(timings.values()), 4),
    }


def _normalize_operational_fields(prediction: dict[str, Any]) -> None:
    timings = _normalize_timings(prediction.get("timings"))
    prediction["timings"] = timings

    performance = dict(prediction.get("performance") or {})
    for key, value in _performance_from_timings(timings).items():
        performance.setdefault(key, value)
    prediction["performance"] = performance
    prediction["cache"] = _normalize_cache(prediction.get("cache"))
    prediction["cost"] = dict(prediction.get("cost") or {})


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


_CONFIG_FIELD_NAMES = {field.name for field in fields(BenchmarkConfig)}


def _route_id(route: dict[str, Any], fallback: str) -> str:
    return str(
        route.get("route_id")
        or route.get("id")
        or route.get("name")
        or route.get("route")
        or fallback
    )


def _active_routes(
    bundle: ManifestBundle, config: BenchmarkConfig
) -> list[dict[str, Any]]:
    routes = list(bundle.routes or [])
    if not routes:
        return [
            {
                "route_id": config.route,
                "engine": config.engine,
                "scope": config.scope,
            }
        ]

    if config.route in {"all", "*", ""}:
        return routes

    selected = []
    for index, route in enumerate(routes, start=1):
        if _route_id(route, f"route_{index}") == config.route:
            selected.append(route)
    if selected:
        return selected

    return [
        {
            "route_id": config.route,
            "engine": config.engine,
            "scope": config.scope,
        }
    ]


def _config_for_route(
    config: BenchmarkConfig, route: dict[str, Any], route_index: int
) -> BenchmarkConfig:
    route_name = _route_id(route, f"route_{route_index}")
    updates = {
        key: value
        for key, value in route.items()
        if key in _CONFIG_FIELD_NAMES and value is not None
    }
    updates["route"] = route_name
    updates.setdefault("engine", route.get("engine", config.engine))
    updates.setdefault("scope", route.get("scope", config.scope))
    return replace(config, **updates)


def _engine_result_to_prediction(
    result: EngineRunResult,
    *,
    example,
    documents,
) -> dict[str, Any]:
    document = documents[0]
    return {
        "example_id": example.example_id,
        "document_id": example.document_id,
        "question": example.question,
        "gold_answers": example.answers,
        "gold_pages": example.evidence_pages,
        "gold_sources": example.evidence_sources,
        "predicted_answer": result.answer,
        "predicted_pages": result.predicted_pages,
        "predicted_sources": result.predicted_sources,
        "predicted_element_ids": result.predicted_element_ids,
        "retrieved_hits": result.retrieved_hits,
        "retrieval_trace": result.retrieval_trace,
        "timings": {
            "parse_seconds": round(float(result.timings.get("parse_seconds", 0.0)), 4),
            "index_seconds": round(float(result.timings.get("index_seconds", 0.0)), 4),
            "retrieval_seconds": round(
                float(result.timings.get("retrieval_seconds", 0.0)), 4
            ),
            "generation_seconds": round(
                float(result.timings.get("generation_seconds", 0.0)), 4
            ),
        },
        "performance": result.performance,
        "cache": result.cache,
        "cost": result.cost,
        "context_preview": result.context_preview,
        "document_path": str(document.path),
    }


def _run_engine_example(engine, bundle: ManifestBundle, example) -> dict[str, Any]:
    documents = [
        bundle.documents[document_id]
        for document_id in (example.document_ids or [example.document_id])
    ]
    if hasattr(engine, "run_example"):
        return engine.run_example(bundle, example)
    result = engine.run(example=example, documents=documents)
    return _engine_result_to_prediction(result, example=example, documents=documents)


def _error_prediction(
    *,
    example,
    document,
    route_config: BenchmarkConfig,
    exc: Exception,
) -> dict[str, Any]:
    return {
        "example_id": example.example_id,
        "document_id": document.document_id,
        "document_path": str(document.path),
        "question": example.question,
        "gold_answers": example.answers,
        "gold_pages": example.evidence_pages,
        "gold_sources": example.evidence_sources,
        "gold_evidence": example.gold_evidence,
        "predicted_answer": "",
        "predicted_pages": [],
        "predicted_sources": [],
        "predicted_element_ids": [],
        "retrieved_hits": [],
        "retrieval_trace": [],
        "timings": {
            "parse_seconds": 0.0,
            "index_seconds": 0.0,
            "retrieval_seconds": 0.0,
            "generation_seconds": 0.0,
        },
        "performance": {
            "parse_seconds": 0.0,
            "index_seconds": 0.0,
            "retrieval_seconds": 0.0,
            "generation_seconds": 0.0,
            "total_seconds": 0.0,
        },
        "cache": {
            "parse": {"hits": 0, "misses": 0, "writes": 0},
            "embedding": {"hits": 0, "misses": 0, "writes": 0},
        },
        "cost": {},
        "context_preview": "",
        "engine": route_config.engine,
        "route": route_config.route,
        "scope": route_config.scope,
        "error": str(exc),
    }


def run_benchmark(manifest_path: str, config: BenchmarkConfig) -> dict[str, Any]:
    bundle = load_manifest(manifest_path)
    predictions: list[dict[str, Any]] = []
    engines: dict[tuple[str, str], Any] = {}
    active_routes = _active_routes(bundle, config)

    for route_index, route in enumerate(active_routes, start=1):
        route_config = _config_for_route(config, route, route_index)
        engine_key = (route_config.engine, route_config.route)
        if engine_key not in engines:
            engines[engine_key] = get_engine(route_config.engine, route_config)
        engine = engines[engine_key]

        for example in bundle.examples:
            document = bundle.documents[example.document_id]
            try:
                prediction = _run_engine_example(engine, bundle, example)
                prediction["error"] = None
            except Exception as exc:
                prediction = _error_prediction(
                    example=example,
                    document=document,
                    route_config=route_config,
                    exc=exc,
                )
            prediction["document_path"] = str(document.path)
            prediction["document_ids"] = example.document_ids or [example.document_id]
            prediction["engine"] = route_config.engine
            prediction["route"] = route_config.route
            prediction["scope"] = route_config.scope or example.scope
            _normalize_operational_fields(prediction)
            prediction["modality"] = example.modality
            prediction["answer_type"] = example.answer_type
            prediction["gold_evidence"] = example.gold_evidence
            prediction["metrics"] = _score_prediction(prediction)
            predictions.append(prediction)

    summary = {
        "dataset_name": bundle.dataset_name,
        "manifest_path": str(bundle.manifest_path),
        "suite_name": config.suite_name,
        "engine": config.engine if len(active_routes) == 1 else "matrix",
        "route": config.route,
        "scope": config.scope,
        "num_documents": len(bundle.documents),
        "num_examples": len(bundle.examples),
        "num_routes": len(active_routes),
        "num_predictions": len(predictions),
        "avg_em": round_metric(
            safe_mean([item["metrics"]["em"] for item in predictions])
        ),
        "avg_f1": round_metric(
            safe_mean([item["metrics"]["f1"] for item in predictions])
        ),
        "avg_anls": round_metric(
            safe_mean([item["metrics"]["anls"] for item in predictions])
        ),
        "avg_page_hit": round_metric(
            safe_mean([item["metrics"]["page_hit"] for item in predictions])
        ),
        "avg_citation_recall": round_metric(
            safe_mean([item["metrics"]["citation_recall"] for item in predictions])
        ),
        "avg_element_hit": round_metric(
            safe_mean([item["metrics"].get("element_hit") for item in predictions])
        ),
        "avg_span_recall": round_metric(
            safe_mean([item["metrics"].get("span_recall") for item in predictions])
        ),
        "avg_formula_match": round_metric(
            safe_mean([item["metrics"]["formula_match"] for item in predictions])
        ),
        "avg_numeric_match": round_metric(
            safe_mean([item["metrics"]["numeric_match"] for item in predictions])
        ),
        "avg_retrieval_seconds": round_metric(
            safe_mean([item["timings"]["retrieval_seconds"] for item in predictions])
        ),
        "avg_generation_seconds": round_metric(
            safe_mean([item["timings"]["generation_seconds"] for item in predictions])
        ),
        "avg_parse_seconds": round_metric(
            safe_mean([item["timings"]["parse_seconds"] for item in predictions])
        ),
        "avg_index_seconds": round_metric(
            safe_mean([item["timings"]["index_seconds"] for item in predictions])
        ),
        "cache_mode": config.cache_mode,
        "parse_cache_hits": _sum_cache_stat(predictions, "parse", "hits"),
        "parse_cache_misses": _sum_cache_stat(predictions, "parse", "misses"),
        "parse_cache_writes": _sum_cache_stat(predictions, "parse", "writes"),
        "parse_cache_hit_rate": _cache_hit_rate(predictions, "parse"),
        "embedding_cache_hits": _sum_cache_stat(predictions, "embedding", "hits"),
        "embedding_cache_misses": _sum_cache_stat(predictions, "embedding", "misses"),
        "embedding_cache_writes": _sum_cache_stat(predictions, "embedding", "writes"),
        "embedding_cache_hit_rate": _cache_hit_rate(predictions, "embedding"),
    }

    return {
        "summary": summary,
        "config": config.to_dict(),
        "documents": [
            report
            for engine in engines.values()
            if hasattr(engine, "document_reports")
            for report in engine.document_reports()
        ],
        "predictions": predictions,
        "retrieval_traces": [
            {
                "example_id": item["example_id"],
                "engine": item["engine"],
                "route": item["route"],
                "scope": item["scope"],
                "document_ids": item["document_ids"],
                "retrieved_hits": item.get("retrieved_hits", []),
                "retrieval_trace": item.get("retrieval_trace", []),
                "timings": item.get("timings", {}),
                "performance": item.get("performance", {}),
                "cache": item.get("cache", {}),
                "cost": item.get("cost", {}),
                "error": item.get("error"),
            }
            for item in predictions
        ],
    }
