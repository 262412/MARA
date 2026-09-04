from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmark.fusion_stage_contract import fusion_stage_audit

STAGES = (
    "canonical_candidate_evidence",
    "fused_evidence",
    "reranker_input_evidence",
    "reranked_evidence",
    "selected_evidence",
    "generation_context_evidence",
    "execution_operand_evidence",
    "verified_claim_support_evidence",
    "emitted_citation_evidence",
)
CORE_STAGES = {
    "canonical_candidate_evidence",
    "fused_evidence",
    "reranker_input_evidence",
    "selected_evidence",
    "generation_context_evidence",
    "verified_claim_support_evidence",
    "emitted_citation_evidence",
}
TERMINAL_EVIDENCE_STAGES = {
    "verified_claim_support_evidence",
    "emitted_citation_evidence",
}


def stage_audit(
    prediction: dict[str, Any],
    *,
    suite_kind: str,
) -> tuple[dict[str, Any], list[str]]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    audit: dict[str, Any] = {"example_id": str(prediction.get("example_id") or "")}
    ranking_trace = dict(metadata.get("ranking_trace") or {})
    fusion_audit, fusion_violations = fusion_stage_audit(prediction)
    audit["fusion_stage"] = fusion_audit
    query_plan = dict(metadata.get("query_plan") or {})
    slots = [
        dict(item)
        for item in query_plan.get("evidence_slots") or []
        if isinstance(item, dict)
    ]
    expected_ambiguity = expected_ambiguity_safe_abstention(prediction)
    answerable = prediction_answerable(prediction) and not expected_ambiguity
    stage_audits, missing = audit_evidence_stages(
        metadata,
        ranking_trace=ranking_trace,
        suite_kind=suite_kind,
        answerable=answerable,
        expected_ambiguity=expected_ambiguity,
        missing_execution=missing_execution(slots),
    )
    audit.update(stage_audits)
    if ranking_trace.get("executed") and int(
        ranking_trace.get("output_count") or 0
    ) != len(records(metadata.get("reranked_evidence"))):
        missing.append("reranker_output_count_mismatch")
    if fusion_violations:
        missing.append("fusion_stage_contract")
    return audit, missing


def prediction_answerable(prediction: Mapping[str, Any]) -> bool:
    return any(
        str(answer or "").strip().lower()
        not in {"", "unanswerable", "insufficient evidence"}
        for answer in prediction.get("gold_answers") or []
    )


def missing_execution(slots: list[dict[str, Any]]) -> bool:
    return any(
        bool(slot.get("required_for_execution"))
        and str(slot.get("status") or "missing") != "filled"
        for slot in slots
    )


def audit_evidence_stages(
    metadata: Mapping[str, Any],
    *,
    ranking_trace: Mapping[str, Any],
    suite_kind: str,
    answerable: bool,
    expected_ambiguity: bool,
    missing_execution: bool,
) -> tuple[dict[str, Any], list[str]]:
    audits: dict[str, Any] = {}
    missing: list[str] = []
    for stage in STAGES:
        stage_records = records(metadata.get(stage))
        status = stage_status(
            stage,
            metadata=metadata,
            ranking_trace=ranking_trace,
            suite_kind=suite_kind,
            answerable=answerable,
            expected_ambiguity=expected_ambiguity,
            missing_execution=missing_execution,
            records=stage_records,
        )
        audits[stage] = {"status": status, "count": len(stage_records)}
        if status in {"recorded_empty_not_applicable", "not_applicable"}:
            audits[stage]["applicability"] = "not_applicable"
        if stage in CORE_STAGES and status in {"missing", "empty_required"}:
            missing.append(stage)
        if stage == "reranked_evidence" and ranking_executed(ranking_trace):
            if status == "missing":
                missing.append(stage)
    return audits, missing


def stage_status(
    stage: str,
    *,
    metadata: Mapping[str, Any],
    ranking_trace: Mapping[str, Any],
    suite_kind: str,
    answerable: bool,
    expected_ambiguity: bool,
    missing_execution: bool,
    records: list[dict[str, Any]],
) -> str:
    if stage in TERMINAL_EVIDENCE_STAGES and expected_ambiguity:
        if records:
            return "recorded_unexpected"
        return (
            "recorded_empty_not_applicable" if stage in metadata else "not_applicable"
        )
    if stage in CORE_STAGES and answerable and stage in metadata and not records:
        return "empty_required"
    if stage in metadata:
        return "recorded"
    if stage == "reranked_evidence" and not ranking_executed(ranking_trace):
        return "truthfully_not_executed"
    if stage == "execution_operand_evidence" and suite_kind in {
        "qasper",
        "qasper_debug",
    }:
        return "not_applicable"
    if stage == "execution_operand_evidence" and missing_execution:
        return "blocked_missing_requirements"
    return "missing"


def ranking_executed(ranking_trace: Mapping[str, Any]) -> bool:
    return bool(
        ranking_trace.get("executed")
        if "executed" in ranking_trace
        else ranking_trace.get("backend_execution")
    )


def expected_ambiguity_safe_abstention(prediction: dict[str, Any]) -> bool:
    diagnostics = prediction.get("qasper_annotation_diagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = dict(prediction.get("annotation_diagnostics") or {})
    if diagnostics.get("ambiguous") is not True:
        return False
    terminal_outcome = str(prediction.get("terminal_outcome") or "").strip().lower()
    if not terminal_outcome:
        commit = prediction.get("terminal_semantic_commit")
        if isinstance(commit, dict):
            terminal_outcome = str(commit.get("outcome") or "").strip().lower()
    return terminal_outcome == "safe_abstention"


def records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]
