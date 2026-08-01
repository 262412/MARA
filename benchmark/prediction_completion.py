from __future__ import annotations

from time import monotonic
from typing import Any

from .answer_finalizer import finalize_prediction_answer
from .benchmark_prompts import build_benchmark_prompt
from .benchmark_taxonomy import add_prediction_taxonomy
from .diagnostics import prediction_diagnostics
from .mara_oriented_scores import (
    add_mara_oriented_metrics,
    promote_external_primary_score,
)
from .performance_timing import add_amortized_preparation_timing, record_stage_timing
from .research_adapters import (
    research_adapter_metric_metadata,
    research_adapter_metrics,
    route_backend_metadata,
)
from .research_evaluators import external_research_adapter_metrics
from .scoring import normalize_operational_fields, score_prediction
from .stage_metrics import prediction_stage_metric_status, prediction_stage_metrics
from .task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)
from .verifier_observability import prediction_verifier_observability


def complete_prediction(
    prediction: dict[str, Any],
    *,
    example: Any,
    document: Any,
    route_config: Any,
    route: dict[str, Any],
    dataset_name: str,
    benchmark_role: str,
    preparation_seconds: float,
    example_count: int,
    engine: Any,
    semantic_judge: Any,
) -> None:
    _prepare_prediction_defaults(
        prediction,
        example=example,
        document=document,
        route_config=route_config,
        route=route,
        dataset_name=dataset_name,
        benchmark_role=benchmark_role,
    )
    normalize_operational_fields(prediction)
    add_amortized_preparation_timing(
        prediction,
        preparation_seconds,
        example_count,
    )
    prediction["modality"] = example.modality
    prediction["answer_type"] = example.answer_type
    prediction["gold_evidence"] = example.gold_evidence
    _finalize_answer(
        prediction,
        dataset_name=dataset_name,
        answer_mode=route_config.benchmark_answer_mode,
        engine=engine,
    )
    _score_and_diagnose(
        prediction,
        dataset_name=dataset_name,
        semantic_judge=semantic_judge,
        route=route,
        route_config=route_config,
    )


def _prepare_prediction_defaults(
    prediction: dict[str, Any],
    *,
    example: Any,
    document: Any,
    route_config: Any,
    route: dict[str, Any],
    dataset_name: str,
    benchmark_role: str,
) -> None:
    prompt = build_benchmark_prompt(example, route_config, dataset_name=dataset_name)
    prediction.update(
        {
            "document_path": str(document.path),
            "document_ids": example.document_ids or [example.document_id],
            "engine": route_config.engine,
            "route": route_config.route,
            "scope": route_config.scope or example.scope,
            "benchmark_role": benchmark_role,
            "headline_role": str(route.get("headline_role") or "").strip(),
        }
    )
    defaults = {
        "benchmark_prompt_policy": prompt.policy,
        "benchmark_prompt_profile": prompt.profile,
        "benchmark_prompt_source": prompt.prompt_source,
        "benchmark_answer_mode": route_config.benchmark_answer_mode,
        "benchmark_no_think": prompt.no_think,
        "route_timeout_seconds": route_config.route_timeout_seconds,
        "benchmark_question": prompt.benchmark_question,
        "benchmark_retrieval_query": prompt.retrieval_query,
        "benchmark_runtime_prompt": prompt.runtime_prompt,
        "example_metadata": dict(example.metadata or {}),
        "expected_formats": example.expected_formats,
        "expected_guardrails": example.expected_guardrails,
        "predicted_citations": [],
        "scored_predicted_sources": [],
        "evidence_metadata": {},
        "agent_trace": [],
        "controller_trace": [],
        "controller_decision": {},
        "route_decision": {},
        "retrieve_decision": {},
        "verify_decision": {},
        "guardrail_decision": {},
        "evidence_bundle": {},
        "workflow_plan": {},
        "claim_verification": {},
        "presentation": {},
    }
    for key, value in defaults.items():
        prediction.setdefault(key, value)


def _finalize_answer(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    answer_mode: str,
    engine: Any,
) -> None:
    started = monotonic()
    finalize_prediction_answer(
        prediction,
        dataset_name=dataset_name,
        mode=answer_mode,
    )
    finalization_seconds = monotonic() - started
    started = monotonic()
    task_contract_applied = apply_task_answer_contract(
        prediction,
        dataset_name=dataset_name,
        llm_factory=lambda: engine.task_contract_llm(),
    )
    answerability_seconds = monotonic() - started
    if task_contract_applied:
        started = monotonic()
        finalize_prediction_answer(
            prediction,
            dataset_name=dataset_name,
            mode=answer_mode,
        )
        finalization_seconds += monotonic() - started
    synchronize_terminal_answer_state(prediction)
    record_stage_timing(prediction, "answerability_seconds", answerability_seconds)
    record_stage_timing(
        prediction,
        "answer_finalization_seconds",
        finalization_seconds,
    )


def _score_and_diagnose(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
    semantic_judge: Any,
    route: dict[str, Any],
    route_config: Any,
) -> None:
    prediction["product_metrics"] = score_prediction(
        prediction,
        answer_key="predicted_answer",
    )
    prediction["metrics"] = score_prediction(
        prediction,
        semantic_judge=semantic_judge,
    )
    prediction["diagnostics"] = prediction_diagnostics(prediction)
    prediction["verifier_observability"] = prediction_verifier_observability(prediction)
    add_prediction_taxonomy(prediction)
    add_mara_oriented_metrics(prediction, dataset_name=dataset_name)
    prediction["stage_metrics"] = prediction_stage_metrics(prediction)
    prediction["stage_metric_status"] = prediction_stage_metric_status(prediction)
    prediction["adapter_metrics"] = research_adapter_metrics(prediction)
    prediction["adapter_metric_metadata"] = research_adapter_metric_metadata()
    (
        prediction["external_adapter_metrics"],
        prediction["external_adapter_metric_metadata"],
    ) = external_research_adapter_metrics(prediction, route)
    promote_external_primary_score(prediction, dataset_name=dataset_name)
    prediction["backend_metadata"] = route_backend_metadata(route, route_config)
