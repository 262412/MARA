from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from .run_provenance import require_matching_paired_inputs


@dataclass(frozen=True, slots=True)
class AblationPhase:
    phase: str
    description: str
    features: tuple[str, ...]


_B_FEATURES = (
    "task_contract_repairs",
    "semantic_answer_scoring",
)
_C_FEATURES = _B_FEATURES + (
    "canonical_evidence_identity",
    "three_level_deduplication",
    "claim_aggregation",
)
_D_FEATURES = _C_FEATURES + (
    "rrf_after_canonicalization",
    "strong_reranking",
    "constrained_mmr",
)
_E_FEATURES = _D_FEATURES + (
    "query_plan",
    "evidence_slots",
    "multi_page_structure",
    "second_round_retrieval",
)
_F_FEATURES = _E_FEATURES + (
    "deterministic_calculation",
    "calculation_verification",
)
_G_FEATURES = _F_FEATURES + ("controller_crag_integration",)

ABLATION_PHASES = {
    "A": AblationPhase("A", "Frozen legacy system", ()),
    "B": AblationPhase("B", "Task contracts and semantic scoring", _B_FEATURES),
    "C": AblationPhase("C", "Evidence identity and answer deduplication", _C_FEATURES),
    "D": AblationPhase("D", "Reranking and diversity selection", _D_FEATURES),
    "E": AblationPhase("E", "Structured multi-round retrieval", _E_FEATURES),
    "F": AblationPhase("F", "Deterministic numeric execution", _F_FEATURES),
    "G": AblationPhase("G", "Controller and CRAG integration", _G_FEATURES),
}


@dataclass(frozen=True, slots=True)
class ReleaseGate:
    metric: str
    threshold: float
    comparison: Literal["ge", "gt", "le", "eq"]
    failure_stage: str
    category: Literal["contract", "paired_regression", "capability_target"]


CONTRACT_GATES = (
    ReleaseGate("token_f1_rescore_delta", 0.0, "eq", "evaluation", "contract"),
    ReleaseGate("semantic_calibration_examples", 200.0, "ge", "judge", "contract"),
    ReleaseGate("semantic_calibration_agreement", 0.90, "ge", "judge", "contract"),
    ReleaseGate("semantic_judge_coverage", 0.995, "ge", "judge", "contract"),
    ReleaseGate("qasper_structure_valid", 1.0, "ge", "task_contract", "contract"),
    ReleaseGate("ragtruth_json_valid", 0.99, "ge", "task_contract", "contract"),
    ReleaseGate("ragtruth_execution_error", 0.0, "eq", "task_contract", "contract"),
)
PAIRED_REGRESSION_GATES = (
    ReleaseGate(
        "simple_qa_median_latency_increase",
        0.20,
        "le",
        "latency",
        "paired_regression",
    ),
    ReleaseGate(
        "complex_qa_median_latency_increase",
        0.50,
        "le",
        "latency",
        "paired_regression",
    ),
)
CAPABILITY_TARGETS = (
    ReleaseGate("qasper_semantic_f1", 0.80, "ge", "task_contract", "capability_target"),
    ReleaseGate(
        "ragtruth_positive_recall",
        0.70,
        "ge",
        "task_contract",
        "capability_target",
    ),
    ReleaseGate(
        "ragtruth_clean_specificity",
        0.90,
        "ge",
        "task_contract",
        "capability_target",
    ),
    ReleaseGate("ragtruth_span_f1", 0.60, "ge", "task_contract", "capability_target"),
    ReleaseGate(
        "slidevqa_duplicate_ratio",
        0.05,
        "le",
        "aggregation",
        "capability_target",
    ),
    ReleaseGate("slidevqa_token_f1", 0.58, "ge", "generation", "capability_target"),
    ReleaseGate(
        "mmdocrag_page_duplicate_ratio",
        0.10,
        "le",
        "aggregation",
        "capability_target",
    ),
    ReleaseGate("mmdocrag_page_f1", 0.18, "ge", "retrieval", "capability_target"),
    ReleaseGate(
        "mmdocrag_element_hit_at_10",
        0.30,
        "ge",
        "retrieval",
        "capability_target",
    ),
    ReleaseGate("mmdocrag_element_f1", 0.12, "ge", "retrieval", "capability_target"),
    ReleaseGate("financebench_page_hit", 0.70, "ge", "retrieval", "capability_target"),
    ReleaseGate(
        "financebench_all_gold_pages_hit",
        0.35,
        "ge",
        "coverage",
        "capability_target",
    ),
    ReleaseGate(
        "financebench_all_operands_hit",
        0.50,
        "ge",
        "coverage",
        "capability_target",
    ),
    ReleaseGate(
        "financebench_native_numeric",
        0.20,
        "ge",
        "calculation",
        "capability_target",
    ),
    ReleaseGate(
        "conditional_calculation_accuracy",
        0.95,
        "ge",
        "calculation",
        "capability_target",
    ),
    ReleaseGate("unit_accuracy", 0.98, "ge", "verification", "capability_target"),
    ReleaseGate("crag_false_abstention", 0.15, "le", "controller", "capability_target"),
    ReleaseGate("alce_native_score", 0.75, "ge", "generation", "capability_target"),
    ReleaseGate("alce_citation_f1", 0.93, "ge", "generation", "capability_target"),
)
RELEASE_GATES = CONTRACT_GATES + PAIRED_REGRESSION_GATES + CAPABILITY_TARGETS


def validate_ablation_progression(phases: list[str]) -> None:
    normalized = [str(phase).strip().upper() for phase in phases]
    expected = list(ABLATION_PHASES)[: len(normalized)]
    if normalized != expected:
        raise ValueError(
            "Ablation phases must be a fixed prefix of A, B, C, D, E, F, G."
        )


def formal_full_run_allowed(
    *,
    phase: str,
    unit_tests_passed: bool,
    fixed_sample_passed: bool,
    semantic_calibration_passed: bool,
) -> bool:
    return bool(
        str(phase).strip().upper() == "G"
        and unit_tests_passed
        and fixed_sample_passed
        and semantic_calibration_passed
    )


def evaluate_release_gates(
    *,
    phase_b: dict[str, Any],
    phase_g: dict[str, Any],
    paired_semantic_ci_low: float | None,
    token_f1_rescore_delta: float | None = None,
) -> dict[str, dict[str, Any]]:
    if phase_b.get("run_provenance") or phase_g.get("run_provenance"):
        require_matching_paired_inputs(phase_b, phase_g)
    metrics = _summary_metric_aliases(phase_g)
    metrics["token_f1_rescore_delta"] = token_f1_rescore_delta
    results = {
        gate.metric: _evaluate_gate(gate, metrics.get(gate.metric))
        for gate in RELEASE_GATES
    }
    phase_b_f1 = _number(phase_b.get("avg_semantic_answer_f1"))
    phase_g_f1 = _number(phase_g.get("avg_semantic_answer_f1"))
    delta = None
    if phase_b_f1 is not None and phase_g_f1 is not None:
        delta = (phase_g_f1 - phase_b_f1) * 100.0
    results["semantic_f1_delta_pp"] = _custom_result(
        value=delta,
        threshold=8.0,
        comparison="ge",
        failure_stage="end_to_end",
        category="paired_regression",
    )
    results["semantic_f1_ci_low"] = _custom_result(
        value=_number(paired_semantic_ci_low),
        threshold=0.0,
        comparison="gt",
        failure_stage="end_to_end",
        category="paired_regression",
    )
    return results


def _evaluate_gate(gate: ReleaseGate, value: Any) -> dict[str, Any]:
    return _custom_result(
        value=_number(value),
        threshold=gate.threshold,
        comparison=gate.comparison,
        failure_stage=gate.failure_stage,
        category=gate.category,
    )


def _custom_result(
    *,
    value: float | None,
    threshold: float,
    comparison: Literal["ge", "gt", "le", "eq"],
    failure_stage: str,
    category: Literal["contract", "paired_regression", "capability_target"],
) -> dict[str, Any]:
    if value is None:
        passed = False
        status = "missing"
    else:
        passed = _compare(value, threshold, comparison)
        status = "passed" if passed else "failed"
    return {
        "value": None if value is None else round(value, 6),
        "threshold": threshold,
        "comparison": comparison,
        "passed": passed,
        "status": status,
        "failure_stage": "" if passed else failure_stage,
        "category": category,
        "release_blocking": category != "capability_target",
    }


def _compare(value: float, threshold: float, comparison: str) -> bool:
    if comparison == "ge":
        return value >= threshold
    if comparison == "gt":
        return value > threshold
    if comparison == "le":
        return value <= threshold
    return value == threshold


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _summary_metric_aliases(summary: dict[str, Any]) -> dict[str, Any]:
    metrics = dict(summary)
    for key, value in summary.items():
        if key.startswith("avg_"):
            metrics.setdefault(key.removeprefix("avg_"), value)
    return metrics
