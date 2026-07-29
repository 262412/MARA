from __future__ import annotations

from typing import Any

from .evidence_identity_metrics import reranker_lineage
from .metrics import is_abstention_answer, safe_mean


def contract_gate_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "required_candidate_nonempty_rate": _mean(
            metrics, "required_candidate_nonempty"
        ),
        "required_selected_nonempty_rate": _mean(metrics, "required_selected_nonempty"),
        "required_generation_context_nonempty_rate": _mean(
            metrics, "required_generation_context_nonempty"
        ),
        "citation_required_example_count": _sum(metrics, "citation_required"),
        "citation_emitted_example_count": _sum(metrics, "citation_emitted"),
        "required_citation_missing_count": _sum(metrics, "required_citation_missing"),
        "citation_emission_rate": _mean(metrics, "citation_emission"),
        "citation_emission_coverage": _mean(metrics, "citation_emission"),
        "reranker_execution_coverage": _mean(metrics, "reranker_executed"),
        "calculation_execution_coverage": _mean(metrics, "calculation_executed"),
    }
    summary["contract_gates"] = {
        "reranker_lineage": _gate(
            metrics,
            applicable="reranker_applicable",
            executed="reranker_executed",
            evaluated="reranker_evaluated",
            passed="reranker_passed",
        ),
        "citation_emission": _gate(
            metrics,
            applicable="citation_required",
            executed="citation_emitted",
            evaluated="citation_required",
            passed="citation_emission",
        ),
        "evidence_stage_nonempty": _gate(
            metrics,
            applicable="answerable_document_qa",
            executed="evidence_stages_recorded",
            evaluated="answerable_document_qa",
            passed="required_evidence_stages_nonempty",
        ),
        "calculation_execution": _gate(
            metrics,
            applicable="calculation_applicable",
            executed="calculation_executed",
            evaluated="calculation_applicable",
            passed="calculation_executed",
        ),
    }
    return summary


def prediction_gate_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    *,
    candidates: list[dict[str, Any]],
    reranker_input: list[dict[str, Any]],
    reranked: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    generation_context: list[dict[str, Any]],
) -> dict[str, float | None]:
    answerable = _answerable_document_qa(prediction)
    citation_required = answerable and bool(prediction.get("gold_evidence"))
    citation_emitted = _has_emitted_citation(prediction, metadata)
    ranking_trace = dict(metadata.get("ranking_trace") or {})
    reranker_applicable = _reranker_applicable(ranking_trace)
    reranker_executed = reranker_applicable and bool(
        ranking_trace.get("executed")
        if "executed" in ranking_trace
        else ranking_trace.get("backend_execution")
    )
    reranker_violations = (
        reranker_lineage(reranker_input, reranked)[1]
        if reranker_executed and reranker_input and reranked
        else 0
    )
    calculation_applicable = _calculation_applicable(metadata)
    calculation_executed = _calculation_executed(metadata)
    return {
        "answerable_document_qa": float(answerable),
        "required_candidate_nonempty": _when(answerable, bool(candidates)),
        "required_selected_nonempty": _when(answerable, bool(selected)),
        "required_generation_context_nonempty": _when(
            answerable, bool(generation_context)
        ),
        "evidence_stages_recorded": _when(
            answerable,
            all(
                key in metadata
                for key in (
                    "canonical_candidate_evidence",
                    "selected_evidence",
                    "generation_context_evidence",
                )
            ),
        ),
        "required_evidence_stages_nonempty": _when(
            answerable, bool(candidates and selected and generation_context)
        ),
        "citation_required": float(citation_required),
        "citation_emitted": float(citation_emitted),
        "required_citation_missing": float(citation_required and not citation_emitted),
        "citation_emission": _when(citation_required, citation_emitted),
        "reranker_applicable": float(reranker_applicable),
        "reranker_executed": _when(reranker_applicable, reranker_executed),
        "reranker_evaluated": _when(
            reranker_applicable,
            reranker_executed and bool(reranker_input and reranked),
        ),
        "reranker_passed": _when(
            reranker_applicable,
            reranker_executed
            and bool(reranker_input and reranked)
            and reranker_violations == 0,
        ),
        "reranker_lineage_violation_count": float(reranker_violations),
        "calculation_applicable": float(calculation_applicable),
        "calculation_executed": _when(calculation_applicable, calculation_executed),
    }


def _gate(
    metrics: list[dict[str, float | None]],
    *,
    applicable: str,
    executed: str,
    evaluated: str,
    passed: str,
) -> dict[str, Any]:
    applicable_count = _sum(metrics, applicable)
    executed_count = _sum(metrics, executed)
    evaluated_count = _sum(metrics, evaluated)
    passed_count = _sum(metrics, passed)
    violation_count = max(0.0, applicable_count - passed_count)
    status = "not_applicable"
    if applicable_count:
        status = "passed" if violation_count == 0 else "failed"
    return {
        "applicable_count": applicable_count,
        "executed_count": executed_count,
        "evaluated_count": evaluated_count,
        "passed_count": passed_count,
        "violation_count": violation_count,
        "status": status,
    }


def _answerable_document_qa(prediction: dict[str, Any]) -> bool:
    return any(
        str(answer or "").strip() and not is_abstention_answer(str(answer))
        for answer in prediction.get("gold_answers") or []
    )


def _has_emitted_citation(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    if _records(metadata.get("emitted_citation_evidence")):
        return True
    bundle = prediction.get("evidence_bundle")
    if isinstance(bundle, dict):
        bundle_metadata = bundle.get("metadata")
        if isinstance(bundle_metadata, dict) and _records(
            bundle_metadata.get("emitted_citation_evidence")
        ):
            return True
    if _records(prediction.get("structured_citations")):
        return True
    answer = str(prediction.get("predicted_answer") or "")
    return bool("#page:" in answer or "#source" in answer or "#evidence:" in answer)


def _reranker_applicable(ranking_trace: dict[str, Any]) -> bool:
    return bool(
        ranking_trace.get("configured")
        or ranking_trace.get("loaded")
        or ranking_trace.get("executed")
        or ranking_trace.get("backend_execution")
        or ranking_trace.get("backend")
        or ranking_trace.get("configured_backend")
        or ranking_trace.get("reranker_backend")
    )


def _calculation_applicable(metadata: dict[str, Any]) -> bool:
    query_plan = dict(metadata.get("query_plan") or {})
    return any(
        isinstance(slot, dict) and bool(slot.get("required_for_execution"))
        for slot in query_plan.get("evidence_slots") or []
    )


def _calculation_executed(metadata: dict[str, Any]) -> bool:
    trace = metadata.get("finance_numeric_trace")
    if not isinstance(trace, dict):
        return False
    execution = trace.get("calculation_execution")
    return isinstance(execution, dict) and execution.get("status") == "ok"


def _when(applicable: bool, value: bool) -> float | None:
    return float(value) if applicable else None


def _sum(metrics: list[dict[str, float | None]], key: str) -> float:
    return sum(float(metric.get(key) or 0.0) for metric in metrics)


def _mean(
    metrics: list[dict[str, float | None]],
    key: str,
) -> float | None:
    return safe_mean(
        [value for metric in metrics if (value := metric.get(key)) is not None]
    )


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]
