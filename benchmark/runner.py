from __future__ import annotations

from dataclasses import fields, replace
from typing import Any

from .engines import EngineRunResult, get_engine
from .manifest import load_manifest
from .metrics import (
    anls_score,
    citation_precision_score,
    citation_recall_score,
    cross_page_evidence_hit_score,
    element_hit_score,
    exact_match_score,
    false_abstention_score,
    formula_normalized_match_score,
    hard_negative_rejection_score,
    image_quote_hit_score,
    is_abstention_answer,
    latex_renderable_score,
    markdown_table_renderable_score,
    modality_hit_score,
    multimodal_support_score,
    numeric_tolerance_score,
    page_hit_score,
    recall_score,
    span_recall_score,
    token_f1_score,
)
from .research_adapters import (
    research_adapter_metric_metadata,
    research_adapter_metrics,
    route_backend_metadata,
)
from .research_evaluators import (
    external_research_adapter_metric_metadata,
    external_research_adapter_metrics,
)
from .route_execution import route_skip_record
from .schemas import BenchmarkConfig, ManifestBundle
from .summary import build_benchmark_summary
from .verification_metrics import verification_metrics

_TABLE_FORMATS = {"markdown_table", "markdown-table", "table"}
_LATEX_FORMATS = {"latex", "math", "formula", "math_formula", "math-formula"}


def _normalized_expected_formats(prediction: dict[str, Any]) -> set[str]:
    return {
        str(item).strip().lower()
        for item in prediction.get("expected_formats", [])
        if str(item).strip()
    }


def _guardrail_expectation_match(
    prediction: dict[str, Any],
    abstained: bool,
) -> float | None:
    expected = dict(prediction.get("expected_guardrails") or {})
    if not expected:
        return None

    claim_verification = dict(prediction.get("claim_verification") or {})
    checks: list[bool] = []
    if "rewrite_skipped" in expected:
        checks.append(
            bool(claim_verification.get("rewrite_skipped"))
            == bool(expected["rewrite_skipped"])
        )
    if "allow_abstention" in expected:
        checks.append(bool(expected["allow_abstention"]) or not abstained)
    if not checks:
        return None
    return sum(1 for item in checks if item) / len(checks)


def _score_prediction(prediction: dict[str, Any]) -> dict[str, float | None]:
    gold_answers = prediction["gold_answers"]
    predicted_answer = prediction["predicted_answer"]
    expected_formats = _normalized_expected_formats(prediction)
    claim_verification = dict(prediction.get("claim_verification") or {})
    abstained = bool(claim_verification.get("abstained")) or is_abstention_answer(
        predicted_answer
    )
    markdown_table_score = markdown_table_renderable_score(predicted_answer)
    latex_score = latex_renderable_score(predicted_answer)
    if expected_formats & _TABLE_FORMATS and markdown_table_score is None:
        markdown_table_score = 0.0
    if expected_formats & _LATEX_FORMATS and latex_score is None:
        latex_score = 0.0
    false_abstention = false_abstention_score(predicted_answer, gold_answers)
    if abstained and any(str(answer or "").strip() for answer in gold_answers):
        false_abstention = 1.0

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
        "abstained": float(abstained),
        "false_abstention": false_abstention,
        "markdown_table_renderable": markdown_table_score,
        "latex_renderable": latex_score,
        "rewrite_skipped": float(bool(claim_verification.get("rewrite_skipped"))),
        "guardrail_expectation_match": _guardrail_expectation_match(
            prediction, abstained
        ),
    }
    for modality in ("table", "figure", "formula", "slide"):
        metrics[f"{modality}_hit"] = modality_hit_score(
            modality,
            expected_modality=str(prediction.get("modality") or ""),
            evidence_metadata=dict(prediction.get("evidence_metadata") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=list(prediction.get("gold_evidence") or []),
        )
    metrics.update(verification_metrics(prediction))
    gold_evidence = prediction.get("gold_evidence", [])
    if gold_evidence:
        metrics["element_hit"] = element_hit_score(
            prediction.get("predicted_element_ids", []), gold_evidence
        )
        metrics["span_recall"] = span_recall_score(predicted_answer, gold_evidence)
        metrics["image_quote_hit"] = image_quote_hit_score(
            predicted_answer, gold_evidence
        )
        metrics["multimodal_answer_support"] = multimodal_support_score(
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=gold_evidence,
        )
        metrics["hard_negative_rejection"] = hard_negative_rejection_score(
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=gold_evidence,
        )
        metrics["citation_recall"] = citation_recall_score(
            prediction["predicted_sources"], gold_evidence
        )
        metrics["citation_precision"] = citation_precision_score(
            prediction["predicted_sources"], gold_evidence
        )
        metrics["cross_page_evidence_hit"] = cross_page_evidence_hit_score(
            prediction["predicted_pages"],
            evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
            retrieved_hits=list(prediction.get("retrieved_hits") or []),
            gold_evidence=gold_evidence,
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
    _set_visual_generator_backend(updates, route)
    return replace(config, **updates)


def _set_visual_generator_backend(
    updates: dict[str, Any],
    route: dict[str, Any],
) -> None:
    if updates.get("visual_generator_backend"):
        return
    route_policy = str(route.get("route_policy") or "").strip().lower()
    if route_policy not in {"visual", "page_image", "page-image"}:
        return
    generator_backend = route.get("generator_backend")
    if generator_backend:
        updates["visual_generator_backend"] = generator_backend


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
        "agent_trace": result.agent_trace,
        "evidence_metadata": result.evidence_metadata,
        "controller_trace": result.controller_trace,
        "controller_decision": result.controller_decision,
        "route_decision": result.route_decision,
        "retrieve_decision": result.retrieve_decision,
        "verify_decision": result.verify_decision,
        "guardrail_decision": result.guardrail_decision,
        "evidence_bundle": result.evidence_bundle,
        "workflow_plan": result.workflow_plan,
        "claim_verification": result.claim_verification,
        "presentation": result.presentation,
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
        "gold_evidence": example.gold_evidence,
        "expected_formats": example.expected_formats,
        "expected_guardrails": example.expected_guardrails,
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
        "agent_trace": [],
        "evidence_metadata": {},
        "controller_trace": [],
        "controller_decision": {},
        "route_decision": {},
        "retrieve_decision": {},
        "verify_decision": {},
        "guardrail_decision": {},
        "evidence_bundle": {},
        "claim_verification": {},
        "presentation": {},
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
        "expected_formats": example.expected_formats,
        "expected_guardrails": example.expected_guardrails,
        "error": str(exc),
    }


def _prepare_prediction_defaults(
    prediction: dict[str, Any],
    *,
    example,
    document,
    route_config: BenchmarkConfig,
) -> None:
    prediction["document_path"] = str(document.path)
    prediction["document_ids"] = example.document_ids or [example.document_id]
    prediction["engine"] = route_config.engine
    prediction["route"] = route_config.route
    prediction["scope"] = route_config.scope or example.scope
    prediction.setdefault("expected_formats", example.expected_formats)
    prediction.setdefault("expected_guardrails", example.expected_guardrails)
    prediction.setdefault("evidence_metadata", {})
    prediction.setdefault("agent_trace", [])
    prediction.setdefault("controller_trace", [])
    prediction.setdefault("controller_decision", {})
    prediction.setdefault("route_decision", {})
    prediction.setdefault("retrieve_decision", {})
    prediction.setdefault("verify_decision", {})
    prediction.setdefault("guardrail_decision", {})
    prediction.setdefault("evidence_bundle", {})
    prediction.setdefault("workflow_plan", {})
    prediction.setdefault("claim_verification", {})
    prediction.setdefault("presentation", {})


def _retrieval_trace_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "example_id": item["example_id"],
        "engine": item["engine"],
        "route": item["route"],
        "scope": item["scope"],
        "document_ids": item["document_ids"],
        "retrieved_hits": item.get("retrieved_hits", []),
        "retrieval_trace": item.get("retrieval_trace", []),
        "agent_trace": item.get("agent_trace", []),
        "evidence_metadata": item.get("evidence_metadata", {}),
        "controller_trace": item.get("controller_trace", []),
        "controller_decision": item.get("controller_decision", {}),
        "route_decision": item.get("route_decision", {}),
        "retrieve_decision": item.get("retrieve_decision", {}),
        "verify_decision": item.get("verify_decision", {}),
        "guardrail_decision": item.get("guardrail_decision", {}),
        "evidence_bundle": item.get("evidence_bundle", {}),
        "workflow_plan": item.get("workflow_plan", {}),
        "claim_verification": item.get("claim_verification", {}),
        "presentation": item.get("presentation", {}),
        "timings": item.get("timings", {}),
        "performance": item.get("performance", {}),
        "cache": item.get("cache", {}),
        "cost": item.get("cost", {}),
        "error": item.get("error"),
    }


def run_benchmark(manifest_path: str, config: BenchmarkConfig) -> dict[str, Any]:
    bundle = load_manifest(manifest_path)
    predictions: list[dict[str, Any]] = []
    engines: dict[tuple[str, str], Any] = {}
    active_routes = _active_routes(bundle, config)
    skipped_routes: list[dict[str, Any]] = []

    for route_index, route in enumerate(active_routes, start=1):
        route_config = _config_for_route(config, route, route_index)
        skip_record = route_skip_record(
            route,
            route_id=route_config.route,
            engine=route_config.engine,
        )
        if skip_record is not None:
            skipped_routes.append(skip_record)
            continue
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
            _prepare_prediction_defaults(
                prediction,
                example=example,
                document=document,
                route_config=route_config,
            )
            _normalize_operational_fields(prediction)
            prediction["modality"] = example.modality
            prediction["answer_type"] = example.answer_type
            prediction["gold_evidence"] = example.gold_evidence
            prediction["metrics"] = _score_prediction(prediction)
            prediction["adapter_metrics"] = research_adapter_metrics(prediction)
            prediction["adapter_metric_metadata"] = research_adapter_metric_metadata()
            (
                prediction["external_adapter_metrics"],
                prediction["external_adapter_metric_metadata"],
            ) = external_research_adapter_metrics(prediction, route)
            prediction["backend_metadata"] = route_backend_metadata(route, route_config)
            predictions.append(prediction)

    backend_metadata = {
        _route_id(route, f"route_{index}"): route_backend_metadata(
            route,
            _config_for_route(config, route, index),
        )
        for index, route in enumerate(active_routes, start=1)
    }
    summary = build_benchmark_summary(
        bundle=bundle,
        config=config,
        active_routes=active_routes,
        predictions=predictions,
        backend_metadata=backend_metadata,
        skipped_routes=skipped_routes,
        adapter_metric_metadata=research_adapter_metric_metadata(),
        external_adapter_metric_metadata=_external_adapter_summary_metadata(
            predictions,
            active_routes,
        ),
        external_adapter_metric_metadata_by_route=(
            _external_adapter_summary_metadata_by_route(predictions, active_routes)
        ),
    )

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
        "retrieval_traces": [_retrieval_trace_row(item) for item in predictions],
    }


def _external_adapter_summary_metadata(
    predictions: list[dict[str, Any]],
    active_routes: list[dict[str, Any]],
) -> dict[str, Any]:
    for prediction in predictions:
        metadata = prediction.get("external_adapter_metric_metadata")
        if isinstance(metadata, dict):
            return metadata
    route = active_routes[0] if active_routes else {}
    return external_research_adapter_metric_metadata(route)


def _external_adapter_summary_metadata_by_route(
    predictions: list[dict[str, Any]],
    active_routes: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    metadata_by_route: dict[str, dict[str, Any]] = {}
    prediction_metadata = _prediction_external_metadata_by_route(predictions)
    for index, route in enumerate(active_routes, start=1):
        route_id = _route_id(route, f"route_{index}")
        metadata_by_route[route_id] = prediction_metadata.get(
            route_id,
            external_research_adapter_metric_metadata(route),
        )
    return metadata_by_route


def _prediction_external_metadata_by_route(
    predictions: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    metadata_by_route: dict[str, dict[str, Any]] = {}
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        metadata = prediction.get("external_adapter_metric_metadata")
        if route and isinstance(metadata, dict) and route not in metadata_by_route:
            metadata_by_route[route] = metadata
    return metadata_by_route
