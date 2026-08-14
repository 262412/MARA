from __future__ import annotations

from copy import deepcopy
from dataclasses import fields, replace
from pathlib import Path
from time import monotonic, perf_counter
from typing import Any

from .backend_health_summary import load_backend_health
from .engines import EngineRunResult, get_engine
from .external_adapter_summary import (
    external_adapter_summary_metadata,
    external_adapter_summary_metadata_by_route,
)
from .manifest import load_manifest
from .performance_timing import apply_engine_failure_diagnostics, measure_duration
from .prediction_completion import complete_prediction
from .research_adapters import research_adapter_metric_metadata, route_backend_metadata
from .route_execution import route_skip_record
from .route_timeout import (
    RouteExecutionTimeout,
    raise_if_route_budget_exceeded,
    route_timeout_seconds,
    run_with_route_timeout,
)
from .run_provenance import benchmark_run_provenance
from .sampling import select_examples_for_config, selection_summary
from .schemas import BenchmarkConfig, ManifestBundle
from .semantic_answer import semantic_judge_backend
from .summary import build_benchmark_summary

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
        return _routes_with_config_evaluators(
            [
                {
                    "route_id": config.route,
                    "engine": config.engine,
                    "scope": config.scope,
                }
            ],
            config,
        )

    if config.route in {"all", "*", ""}:
        return _routes_with_config_evaluators(routes, config)

    selected = []
    for index, route in enumerate(routes, start=1):
        if _route_id(route, f"route_{index}") == config.route:
            selected.append(route)
    if selected:
        return _routes_with_config_evaluators(selected, config)

    return _routes_with_config_evaluators(
        [
            {
                "route_id": config.route,
                "engine": config.engine,
                "scope": config.scope,
            }
        ],
        config,
    )


def _routes_with_config_evaluators(
    routes: list[dict[str, Any]],
    config: BenchmarkConfig,
) -> list[dict[str, Any]]:
    configured = dict(config.external_evaluators or {})
    if not configured:
        return routes
    merged_routes: list[dict[str, Any]] = []
    for route in routes:
        merged_route = dict(route)
        route_evaluators = dict(merged_route.get("external_evaluators") or {})
        merged_route["external_evaluators"] = {**configured, **route_evaluators}
        merged_routes.append(merged_route)
    return merged_routes


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
    if config.docqa_citation_mode is not None:
        updates["docqa_citation_mode"] = config.docqa_citation_mode
    if config.route_timeout_seconds is not None:
        updates["route_timeout_seconds"] = config.route_timeout_seconds
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
        "document_ids": list(example.document_ids or [example.document_id]),
        "question": example.question,
        "gold_answers": example.answers,
        "gold_pages": example.evidence_pages,
        "gold_sources": example.evidence_sources,
        "gold_source_ids": example.gold_source_ids,
        "gold_evidence_texts": example.gold_evidence_texts,
        "predicted_answer": result.answer,
        "predicted_pages": result.predicted_pages,
        "predicted_sources": result.predicted_sources,
        "predicted_citations": result.predicted_citations,
        "scored_predicted_sources": result.scored_predicted_sources,
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
        "engine_terminal_answer": result.engine_terminal_answer,
        "engine_terminal_state": deepcopy(result.engine_terminal_state),
        "engine_verify_decision": deepcopy(result.engine_verify_decision),
        "engine_terminal_guardrail_decision": deepcopy(
            result.engine_terminal_guardrail_decision
        ),
        "engine_terminal_evidence_bundle": deepcopy(
            result.engine_terminal_evidence_bundle
        ),
        "engine_terminal_projection_hash": result.engine_terminal_projection_hash,
        "engine_terminal_commit": deepcopy(result.engine_terminal_commit),
        "terminal_semantic_commit": deepcopy(result.engine_terminal_commit),
        "claim_verification": result.claim_verification,
        "presentation": result.presentation,
        "source_identity_crosswalk": result.source_identity_crosswalk,
        "timings": {
            **{
                str(key): round(float(value or 0.0), 6)
                for key, value in result.timings.items()
            },
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
        "gold_evidence_records": example.gold_evidence_records,
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


def _set_engine_route_deadline(engine: Any, deadline: float | None) -> None:
    setter = getattr(engine, "set_route_deadline_monotonic", None)
    if callable(setter):
        setter(deadline)


def _prepare_engine_examples(
    engine,
    bundle: ManifestBundle,
    examples: list[Any],
) -> None:
    prepare_examples = getattr(engine, "prepare_examples", None)
    if callable(prepare_examples):
        prepare_examples(bundle, examples)


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
        "document_ids": list(example.document_ids or [example.document_id]),
        "document_path": str(document.path),
        "question": example.question,
        "gold_answers": example.answers,
        "gold_pages": example.evidence_pages,
        "gold_sources": example.evidence_sources,
        "gold_source_ids": example.gold_source_ids,
        "gold_evidence_texts": example.gold_evidence_texts,
        "gold_evidence": example.gold_evidence,
        "gold_evidence_records": example.gold_evidence_records,
        "predicted_answer": "",
        "predicted_pages": [],
        "predicted_sources": [],
        "predicted_citations": [],
        "scored_predicted_sources": [],
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
        "error_type": _error_type(exc),
        "route_timeout_seconds": route_timeout_seconds(
            exc, route_config.route_timeout_seconds
        ),
    }


def _retrieval_trace_row(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "example_id": item["example_id"],
        "engine": item["engine"],
        "route": item["route"],
        "scope": item["scope"],
        "benchmark_role": item.get("benchmark_role", "qa_quality"),
        "agent_mode": item.get("agent_mode"),
        "route_policy": item.get("route_policy"),
        "benchmark_prompt_policy": item.get("benchmark_prompt_policy"),
        "benchmark_prompt_profile": item.get("benchmark_prompt_profile"),
        "benchmark_prompt_source": item.get("benchmark_prompt_source"),
        "benchmark_question": item.get("benchmark_question"),
        "benchmark_retrieval_query": item.get("benchmark_retrieval_query"),
        "document_ids": item["document_ids"],
        "gold_pages": item.get("gold_pages", []),
        "gold_sources": item.get("gold_sources", []),
        "gold_source_ids": item.get("gold_source_ids", []),
        "gold_evidence_texts": item.get("gold_evidence_texts", []),
        "gold_evidence": item.get("gold_evidence", []),
        "gold_evidence_records": item.get("gold_evidence_records", []),
        "predicted_pages": item.get("predicted_pages", []),
        "predicted_sources": item.get("predicted_sources", []),
        "predicted_citations": item.get("predicted_citations", []),
        "scored_predicted_sources": item.get("scored_predicted_sources", []),
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
        "verifier_observability": item.get("verifier_observability", {}),
        "presentation": item.get("presentation", {}),
        "timings": item.get("timings", {}),
        "performance": item.get("performance", {}),
        "cache": item.get("cache", {}),
        "cost": item.get("cost", {}),
        "error": item.get("error"),
        "error_type": item.get("error_type"),
        "route_timeout_seconds": item.get("route_timeout_seconds"),
        "engine_terminal_commit": item.get("engine_terminal_commit", {}),
        "terminal_semantic_commit": item.get("terminal_semantic_commit", {}),
    }


def run_benchmark(manifest_path: str, config: BenchmarkConfig) -> dict[str, Any]:
    bundle = load_manifest(manifest_path)
    selected_examples = select_examples_for_config(bundle.examples, config)
    selected_bundle = replace(bundle, examples=selected_examples)
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
        semantic_judge = semantic_judge_backend(
            route_config.semantic_evaluator,
            model=route_config.semantic_evaluator_model,
            timeout_seconds=route_config.semantic_evaluator_timeout_seconds,
        )
        preparation_seconds = measure_duration(
            lambda: _prepare_engine_examples(
                engine, selected_bundle, selected_bundle.examples
            )
        )

        for example in selected_bundle.examples:
            document = selected_bundle.documents[example.document_id]
            route_started_at = perf_counter()
            route_deadline_monotonic = (
                monotonic() + route_config.route_timeout_seconds
                if route_config.route_timeout_seconds is not None
                else None
            )
            _set_engine_route_deadline(engine, route_deadline_monotonic)
            try:
                prediction = run_with_route_timeout(
                    route_config.route_timeout_seconds,
                    lambda: _run_engine_example(engine, selected_bundle, example),
                )
                raise_if_route_budget_exceeded(
                    route_started_at, route_config.route_timeout_seconds
                )
                prediction["error"] = None
            except Exception as exc:
                prediction = _error_prediction(
                    example=example,
                    document=document,
                    route_config=route_config,
                    exc=exc,
                )
                apply_engine_failure_diagnostics(prediction, engine)
            complete_prediction(
                prediction,
                example=example,
                document=document,
                route_config=route_config,
                route=route,
                dataset_name=bundle.dataset_name,
                benchmark_role=_benchmark_role(route, route_config.route),
                preparation_seconds=preparation_seconds,
                example_count=len(selected_bundle.examples),
                engine=engine,
                semantic_judge=semantic_judge,
            )
            predictions.append(prediction)

    backend_metadata = {
        _route_id(route, f"route_{index}"): route_backend_metadata(
            route,
            _config_for_route(config, route, index),
        )
        for index, route in enumerate(active_routes, start=1)
    }
    summary = build_benchmark_summary(
        bundle=selected_bundle,
        config=config,
        active_routes=active_routes,
        predictions=predictions,
        backend_metadata=backend_metadata,
        backend_health=load_backend_health(config.backend_health_json),
        skipped_routes=skipped_routes,
        adapter_metric_metadata=research_adapter_metric_metadata(),
        external_adapter_metric_metadata=external_adapter_summary_metadata(
            predictions,
            active_routes,
        ),
        external_adapter_metric_metadata_by_route=(
            external_adapter_summary_metadata_by_route(predictions, active_routes)
        ),
        selection=selection_summary(config, len(bundle.examples)),
    )
    summary["run_provenance"] = benchmark_run_provenance(
        manifest_path=manifest_path,
        config=config.to_dict(),
        repo_root=Path(__file__).resolve().parents[1],
    )

    return {
        "summary": summary,
        "config": config.to_dict(),
        "documents": [
            *_manifest_document_reports(selected_bundle),
            *_engine_document_reports(engines.values()),
        ],
        "predictions": predictions,
        "retrieval_traces": [_retrieval_trace_row(item) for item in predictions],
    }


def _benchmark_role(route: dict[str, Any], route_id: str) -> str:
    explicit = str(route.get("benchmark_role") or "").strip()
    if explicit in {"qa_quality", "diagnostic", "prototype"}:
        return explicit
    normalized_route_id = str(route_id or "").strip()
    if normalized_route_id == "direct_answer":
        return "diagnostic"
    if (
        normalized_route_id.startswith("graph_rag")
        or normalized_route_id == "element_rag"
    ):
        return "prototype"
    return "qa_quality"


def _error_type(exc: Exception) -> str:
    if isinstance(exc, RouteExecutionTimeout):
        return "route_timeout"
    return "execution_error"


def _manifest_document_reports(bundle: ManifestBundle) -> list[dict[str, Any]]:
    return [document.to_dict() for document in bundle.documents.values()]


def _engine_document_reports(engines: Any) -> list[dict[str, Any]]:
    reports: list[dict[str, Any]] = []
    for engine in engines:
        if not hasattr(engine, "document_reports"):
            continue
        reports.extend(engine.document_reports())
    return reports
