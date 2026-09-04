from __future__ import annotations

import random
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
    category: Literal[
        "contract",
        "judge_calibration",
        "paired_regression",
        "capability_target",
    ]


def _zero_contract_gate(metric: str, failure_stage: str) -> ReleaseGate:
    return ReleaseGate(metric, 0.0, "eq", failure_stage, "contract")


CONTRACT_GATES = (
    ReleaseGate("token_f1_rescore_delta", 0.0, "eq", "evaluation", "contract"),
    ReleaseGate("qasper_structure_valid", 1.0, "ge", "task_contract", "contract"),
    ReleaseGate("ragtruth_json_valid", 0.99, "ge", "task_contract", "contract"),
    ReleaseGate("ragtruth_execution_error", 0.0, "eq", "task_contract", "contract"),
    ReleaseGate("duplicate_identity_count", 0.0, "eq", "identity", "contract"),
    ReleaseGate("conflicting_identity_count", 0.0, "eq", "identity", "contract"),
    ReleaseGate(
        "canonical_id_mismatch_count",
        0.0,
        "eq",
        "identity",
        "contract",
    ),
    ReleaseGate("identity_collision_count", 0.0, "eq", "identity", "contract"),
    ReleaseGate(
        "atomic_field_roundtrip_rate",
        1.0,
        "ge",
        "projection",
        "contract",
    ),
    ReleaseGate(
        "locator_roundtrip_rate",
        1.0,
        "ge",
        "projection",
        "contract",
    ),
    ReleaseGate(
        "lineage_roundtrip_rate",
        1.0,
        "ge",
        "projection",
        "contract",
    ),
    ReleaseGate(
        "representation_roundtrip_rate",
        1.0,
        "ge",
        "projection",
        "contract",
    ),
    ReleaseGate(
        "runtime_benchmark_roundtrip",
        1.0,
        "ge",
        "projection",
        "contract",
    ),
    ReleaseGate(
        "citation_provenance_violation_count",
        0.0,
        "eq",
        "citation",
        "contract",
    ),
    ReleaseGate(
        "reranker_lineage_violation_count",
        0.0,
        "eq",
        "reranking",
        "contract",
    ),
    ReleaseGate(
        "missing_execution_slot_answer_count",
        0.0,
        "eq",
        "calculation",
        "contract",
    ),
    _zero_contract_gate("required_slot_false_fill_count", "planning"),
    _zero_contract_gate("source_page_cross_join_count", "citation"),
    _zero_contract_gate("calculation_render_mismatch_count", "calculation"),
    _zero_contract_gate("qasper_stale_verifier_state_count", "task_contract"),
)
JUDGE_CALIBRATION_GATES = (
    ReleaseGate(
        "semantic_calibration_examples",
        200.0,
        "ge",
        "judge",
        "judge_calibration",
    ),
    ReleaseGate(
        "semantic_calibration_agreement",
        0.90,
        "ge",
        "judge",
        "judge_calibration",
    ),
    ReleaseGate(
        "semantic_judge_coverage",
        0.995,
        "ge",
        "judge",
        "judge_calibration",
    ),
)
PAIRED_REGRESSION_GATES = (
    ReleaseGate(
        "deployed_native_score_delta",
        0.0,
        "ge",
        "native_score",
        "paired_regression",
    ),
    ReleaseGate(
        "false_abstention_delta",
        0.0,
        "le",
        "controller",
        "paired_regression",
    ),
    ReleaseGate(
        "citation_score_delta",
        0.0,
        "ge",
        "citation",
        "paired_regression",
    ),
    ReleaseGate(
        "execution_error_delta",
        0.0,
        "le",
        "execution",
        "paired_regression",
    ),
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
RELEASE_GATES = (
    CONTRACT_GATES
    + JUDGE_CALIBRATION_GATES
    + PAIRED_REGRESSION_GATES
    + CAPABILITY_TARGETS
)


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
    paired_diagnostics = _paired_regression_diagnostics(phase_b, phase_g)
    metrics.update(
        {
            metric: diagnostic["value"]
            for metric, diagnostic in paired_diagnostics.items()
        }
    )
    results = {
        gate.metric: _evaluate_gate(gate, metrics.get(gate.metric))
        for gate in RELEASE_GATES
    }
    for metric, diagnostic in paired_diagnostics.items():
        if metric in results:
            results[metric].update(
                {key: value for key, value in diagnostic.items() if key != "value"}
            )
    semantic_diagnostic = _paired_metric_statistics(
        phase_b,
        phase_g,
        ("semantic_answer_f1", "avg_semantic_answer_f1"),
    )
    semantic_delta = semantic_diagnostic["value"]
    delta = semantic_delta * 100.0 if semantic_delta is not None else None
    results["semantic_f1_delta_pp"] = _custom_result(
        value=delta,
        threshold=8.0,
        comparison="ge",
        failure_stage="end_to_end",
        category="capability_target",
    )
    results["semantic_f1_delta_pp"].update(
        {
            "paired_example_count": semantic_diagnostic["paired_example_count"],
            "paired_wins": semantic_diagnostic["paired_wins"],
            "paired_losses": semantic_diagnostic["paired_losses"],
            "paired_ties": semantic_diagnostic["paired_ties"],
            "paired_ci_low": _scaled_value(semantic_diagnostic["paired_ci_low"], 100.0),
            "paired_ci_high": _scaled_value(
                semantic_diagnostic["paired_ci_high"], 100.0
            ),
        }
    )
    results["semantic_f1_ci_low"] = _custom_result(
        value=_number(paired_semantic_ci_low),
        threshold=0.0,
        comparison="gt",
        failure_stage="end_to_end",
        category="capability_target",
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
    category: Literal[
        "contract",
        "judge_calibration",
        "paired_regression",
        "capability_target",
    ],
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


def _paired_regression_deltas(
    phase_b: dict[str, Any],
    phase_g: dict[str, Any],
) -> dict[str, float | None]:
    return {
        metric: diagnostic["value"]
        for metric, diagnostic in _paired_regression_diagnostics(
            phase_b,
            phase_g,
        ).items()
    }


def _paired_regression_diagnostics(
    phase_b: dict[str, Any],
    phase_g: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    specs = {
        "deployed_native_score_delta": ("primary_score", "avg_native_score"),
        "false_abstention_delta": ("avg_false_abstention",),
        "citation_score_delta": (
            "avg_citation_f1",
            "avg_citation_metadata_recall",
        ),
        "execution_error_delta": (
            "execution_error_rate",
            "avg_execution_error",
        ),
    }
    return {
        metric: _paired_metric_statistics(phase_b, phase_g, aliases)
        for metric, aliases in specs.items()
    }


def _paired_metric_delta(
    phase_b: dict[str, Any],
    phase_g: dict[str, Any],
    aliases: tuple[str, ...],
) -> float | None:
    return _paired_metric_statistics(phase_b, phase_g, aliases)["value"]


def _paired_metric_statistics(
    phase_b: dict[str, Any],
    phase_g: dict[str, Any],
    aliases: tuple[str, ...],
) -> dict[str, Any]:
    baseline_records = _per_example_records(phase_b)
    candidate_records = _per_example_records(phase_g)
    if baseline_records and candidate_records:
        baseline = {_record_key(record): record for record in baseline_records}
        candidate = {_record_key(record): record for record in candidate_records}
        paired_keys = sorted((set(baseline) & set(candidate)) - {("", "", "")})
        for alias in aliases:
            deltas = []
            for key in paired_keys:
                baseline_value = _record_number(baseline[key], alias)
                candidate_value = _record_number(candidate[key], alias)
                if baseline_value is None or candidate_value is None:
                    continue
                deltas.append(candidate_value - baseline_value)
            if deltas:
                ci_low, ci_high = _bootstrap_mean_ci(deltas)
                return {
                    "value": sum(deltas) / len(deltas),
                    "paired_example_count": len(deltas),
                    "paired_wins": sum(delta > 0 for delta in deltas),
                    "paired_losses": sum(delta < 0 for delta in deltas),
                    "paired_ties": sum(delta == 0 for delta in deltas),
                    "paired_ci_low": ci_low,
                    "paired_ci_high": ci_high,
                }
    return {
        "value": None,
        "paired_example_count": 0,
        "paired_wins": 0,
        "paired_losses": 0,
        "paired_ties": 0,
        "paired_ci_low": None,
        "paired_ci_high": None,
    }


def _per_example_records(summary: dict[str, Any]) -> list[dict[str, Any]]:
    values = summary.get("per_example_metric_records")
    return [record for record in values or [] if isinstance(record, dict)]


def _record_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("dataset") or record.get("dataset_name") or "").strip(),
        str(record.get("example_id") or record.get("question_id") or "").strip(),
        str(record.get("route") or "").strip(),
    )


def _record_number(record: dict[str, Any], alias: str) -> float | None:
    values: Any = record
    for key in alias.split("."):
        values = values.get(key) if isinstance(values, dict) else None
    parsed = _number(values)
    if parsed is not None:
        return parsed
    metrics = record.get("metrics")
    parsed = _number(metrics.get(alias)) if isinstance(metrics, dict) else None
    if parsed is not None:
        return parsed
    if str(record.get("error_type") or "") != "route_timeout":
        return None
    return 1.0 if "error" in alias or "abstention" in alias else 0.0


def _bootstrap_mean_ci(
    deltas: list[float],
    *,
    iterations: int = 1000,
    seed: int = 13,
) -> tuple[float, float]:
    if len(deltas) == 1:
        return deltas[0], deltas[0]
    rng = random.Random(seed)
    means = sorted(
        sum(deltas[rng.randrange(len(deltas))] for _ in deltas) / len(deltas)
        for _ in range(iterations)
    )
    return (_percentile(means, 0.025), _percentile(means, 0.975))


def _percentile(values: list[float], fraction: float) -> float:
    index = min(max(round((len(values) - 1) * fraction), 0), len(values) - 1)
    return values[index]


def _scaled_value(value: Any, scale: float) -> float | None:
    parsed = _number(value)
    return parsed * scale if parsed is not None else None


def _first_number(
    values: dict[str, Any],
    aliases: tuple[str, ...],
) -> float | None:
    for alias in aliases:
        parsed = _number(values.get(alias))
        if parsed is not None:
            return parsed
    return None
