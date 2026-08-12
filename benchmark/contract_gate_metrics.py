from __future__ import annotations

from typing import Any

from ktem.docqa.query_plan_schema import slot_binding_state

from .evidence_identity_metrics import reranker_lineage
from .metrics import is_abstention_answer, safe_mean


def contract_gate_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, Any]:
    summary: dict[str, Any] = {
        **_coverage_summary(metrics),
        "required_candidate_nonempty_rate": _mean(
            metrics, "required_candidate_nonempty"
        ),
        "required_selected_nonempty_rate": _mean(metrics, "required_selected_nonempty"),
        "required_generation_context_nonempty_rate": _mean(
            metrics, "required_generation_context_nonempty"
        ),
    }
    summary["contract_gates"] = {
        "reranker_lineage": _gate(
            metrics,
            applicable="reranker_applicable",
            executed="reranker_executed",
            evaluated="reranker_evaluated",
            passed="reranker_passed",
        ),
        "reranker_query_execution": _gate(
            metrics,
            applicable="reranker_query_applicable",
            executed="reranker_queries_executed",
            evaluated="reranker_query_applicable",
            passed="reranker_query_execution_passed",
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
        "safe_abstention": _gate(
            metrics,
            applicable="safe_abstention_applicable",
            executed="safe_abstention_passed",
            evaluated="safe_abstention_applicable",
            passed="safe_abstention_passed",
        ),
    }
    return summary


def _coverage_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    mean_keys = (
        "citation_emission",
        "execution_operand_provenance_coverage",
        "accepted_answer_citation_emission",
        "verified_claim_support_coverage",
        "final_answer_citation_emission",
        "reranker_execution_query_coverage",
        "calculation_executed",
        "safe_abstention_passed",
    )
    summary = {key: _mean(metrics, key) for key in mean_keys}
    return {
        "citation_required_example_count": _sum(metrics, "citation_required"),
        "citation_emitted_example_count": _sum(metrics, "citation_emitted"),
        "required_citation_missing_count": _sum(metrics, "required_citation_missing"),
        "citation_emission_rate": summary["citation_emission"],
        "citation_emission_coverage": summary["citation_emission"],
        "accepted_answer_count": _sum(metrics, "accepted_answer_count"),
        "reranker_execution_coverage": _mean(metrics, "reranker_executed"),
        "reranker_unique_output_artifact_mismatch_count": _sum(
            metrics,
            "reranker_unique_output_artifact_mismatch_count",
        ),
        "calculation_execution_coverage": summary["calculation_executed"],
        "safe_abstention_coverage": summary["safe_abstention_passed"],
        **{
            key: summary[key]
            for key in (
                "execution_operand_provenance_coverage",
                "accepted_answer_citation_emission",
                "verified_claim_support_coverage",
                "final_answer_citation_emission",
                "reranker_execution_query_coverage",
            )
        },
    }


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
    answerable = _answerable_document_qa(prediction) and _document_qa_applicable(
        prediction
    )
    evidence_metrics = _evidence_gate_metrics(
        answerable,
        metadata,
        candidates=candidates,
        selected=selected,
        generation_context=generation_context,
    )
    citation_metrics = _citation_gate_metrics(prediction, metadata, answerable)
    reranker_metrics = _reranker_gate_metrics(
        metadata,
        reranker_input,
        reranked,
    )
    calculation_metrics = _calculation_gate_metrics(prediction, metadata)
    return {
        "answerable_document_qa": float(answerable),
        **evidence_metrics,
        **citation_metrics,
        **reranker_metrics,
        **calculation_metrics,
    }


def _evidence_gate_metrics(
    answerable: bool,
    metadata: dict[str, Any],
    *,
    candidates: list[dict[str, Any]],
    selected: list[dict[str, Any]],
    generation_context: list[dict[str, Any]],
) -> dict[str, float | None]:
    stages_recorded = all(
        key in metadata
        for key in (
            "canonical_candidate_evidence",
            "selected_evidence",
            "generation_context_evidence",
        )
    )
    return {
        "required_candidate_nonempty": _when(answerable, bool(candidates)),
        "required_selected_nonempty": _when(answerable, bool(selected)),
        "required_generation_context_nonempty": _when(
            answerable,
            bool(generation_context),
        ),
        "evidence_stages_recorded": _when(answerable, stages_recorded),
        "required_evidence_stages_nonempty": _when(
            answerable,
            bool(candidates and selected and generation_context),
        ),
    }


def _citation_gate_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
    answerable: bool,
) -> dict[str, float | None]:
    accepted = _accepted_answer(prediction)
    applicable = _document_qa_applicable(prediction)
    required = applicable and accepted and bool(prediction.get("gold_evidence"))
    emitted = _has_emitted_citation(prediction, metadata)
    execution = _calculation_executed(metadata) or _bundle_calculation_executed(
        prediction
    )
    execution_provenance = bool(_records(metadata.get("execution_operand_evidence")))
    verified_support = bool(_records(metadata.get("verified_claim_support_evidence")))
    return {
        "citation_required": float(required),
        "citation_emitted": float(emitted),
        "required_citation_missing": float(required and not emitted),
        "citation_emission": _when(required, emitted),
        "execution_operand_provenance_coverage": _when(
            execution,
            execution_provenance,
        ),
        "accepted_answer_count": float(accepted),
        "accepted_answer_citation_emission": _when(
            applicable and accepted,
            emitted,
        ),
        "verified_claim_support_coverage": _when(
            applicable and accepted,
            verified_support,
        ),
        "final_answer_citation_emission": _when(
            applicable and accepted,
            emitted,
        ),
    }


def _reranker_gate_metrics(
    metadata: dict[str, Any],
    reranker_input: list[dict[str, Any]],
    reranked: list[dict[str, Any]],
) -> dict[str, float | None]:
    ranking_trace = dict(metadata.get("ranking_trace") or {})
    applicable = _reranker_applicable(ranking_trace)
    executed = applicable and bool(
        ranking_trace.get("executed")
        if "executed" in ranking_trace
        else ranking_trace.get("backend_execution")
    )
    violations = (
        reranker_lineage(reranker_input, reranked)[1]
        if executed and reranker_input and reranked
        else 0
    )
    evaluated = executed and bool(reranker_input and reranked)
    execution_traces = [
        trace
        for trace in metadata.get("reranker_execution_traces") or []
        if isinstance(trace, dict)
    ]
    applicable_queries = [
        trace
        for trace in execution_traces
        if trace.get("configured") or trace.get("loaded")
    ]
    missing_query_trace = applicable and not execution_traces
    if missing_query_trace:
        applicable_queries = [{"configured": True, "executed": False}]
    executed_queries = [trace for trace in applicable_queries if trace.get("executed")]
    query_coverage = (
        len(executed_queries) / len(applicable_queries) if applicable_queries else None
    )
    unique_output_count = ranking_trace.get("unique_output_identity_count")
    artifact_count = ranking_trace.get("reranker_artifact_record_count")
    artifact_mismatch = (
        int(unique_output_count != artifact_count)
        if unique_output_count is not None and artifact_count is not None
        else 0
    )
    return {
        "reranker_applicable": float(applicable),
        "reranker_executed": _when(applicable, executed),
        "reranker_evaluated": _when(applicable, evaluated),
        "reranker_passed": _when(applicable, evaluated and violations == 0),
        "reranker_lineage_violation_count": float(violations),
        "reranker_query_applicable": float(bool(applicable_queries)),
        "reranker_queries_executed": _when(
            bool(applicable_queries),
            len(executed_queries) == len(applicable_queries),
        ),
        "reranker_query_execution_passed": _when(
            bool(applicable_queries),
            len(executed_queries) == len(applicable_queries),
        ),
        "reranker_execution_query_coverage": query_coverage,
        "reranker_unique_output_artifact_mismatch_count": float(artifact_mismatch),
    }


def _calculation_gate_metrics(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, float | None]:
    applicable = _calculation_applicable(prediction, metadata)
    executed = _calculation_executed(metadata)
    abstention_applicable = _safe_abstention_applicable(prediction, metadata)
    safely_abstained = is_abstention_answer(
        str(
            prediction.get("answer_for_scoring")
            or prediction.get("predicted_answer")
            or ""
        )
    )
    return {
        "calculation_applicable": float(applicable),
        "calculation_expected": float(applicable),
        "calculation_executed": _when(applicable, executed),
        "safe_abstention_applicable": float(abstention_applicable),
        "safe_abstention_expected": float(abstention_applicable),
        "safe_abstention_passed": _when(
            abstention_applicable,
            safely_abstained,
        ),
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


def _document_qa_applicable(prediction: dict[str, Any]) -> bool:
    role = str(prediction.get("benchmark_role") or "").strip().lower()
    route = (
        str(prediction.get("route") or prediction.get("route_id") or "")
        .strip()
        .lower()
        .replace("-", "_")
    )
    return role != "diagnostic" and route not in {"direct", "direct_answer"}


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


def _accepted_answer(prediction: dict[str, Any]) -> bool:
    status = str(prediction.get("answer_status") or "").strip().lower()
    answer = str(
        prediction.get("answer_for_scoring") or prediction.get("predicted_answer") or ""
    )
    return status != "abstained" and not is_abstention_answer(answer)


def _bundle_calculation_executed(prediction: dict[str, Any]) -> bool:
    bundle = prediction.get("evidence_bundle")
    if not isinstance(bundle, dict):
        return False
    metadata = bundle.get("metadata")
    return isinstance(metadata, dict) and _calculation_executed(metadata)


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


def _calculation_applicable(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    query_plan = dict(metadata.get("query_plan") or {})
    constraints = dict(query_plan.get("constraints") or {})
    numeric_plan = str(query_plan.get("answer_type") or "").lower() in {
        "numeric",
        "formula",
    } or any(
        isinstance(slot, dict) and bool(slot.get("required_for_execution"))
        for slot in query_plan.get("evidence_slots") or []
    )
    return bool(
        _answerable_document_qa(prediction)
        and numeric_plan
        and constraints.get("finance_formula_status") != "unsupported"
    )


def _safe_abstention_applicable(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    query_plan = dict(metadata.get("query_plan") or {})
    constraints = dict(query_plan.get("constraints") or {})
    evidence_items = _execution_slot_evidence(metadata)
    missing_execution = any(
        isinstance(slot, dict)
        and bool(slot.get("required_for_execution"))
        and slot_binding_state(
            slot,
            evidence_items if evidence_items else None,
        )
        != "filled"
        for slot in query_plan.get("evidence_slots") or []
    )
    return bool(
        not _answerable_document_qa(prediction)
        or constraints.get("finance_formula_status") == "unsupported"
        or missing_execution
    )


def _execution_slot_evidence(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        item
        for key in (
            "evidence",
            "selected_evidence",
            "generation_context_evidence",
            "execution_operand_evidence",
        )
        for item in _records(metadata.get(key))
    ]


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
