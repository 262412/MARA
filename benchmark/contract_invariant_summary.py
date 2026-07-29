from __future__ import annotations

from typing import Any

from .contract_gate_metrics import contract_gate_summary
from .metrics import safe_mean


def summarize_contract_invariants(
    metrics: list[dict[str, float | None]],
) -> dict[str, Any]:
    summary = {
        **_identity_summary(metrics),
        **_execution_summary(metrics),
        **_source_summary(metrics),
    }
    summary.update(contract_gate_summary(metrics))
    return summary


def _identity_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        "duplicate_identity_count": _sum(metrics, "duplicate_identity_count"),
        "conflicting_identity_count": _sum(metrics, "conflicting_identity_count"),
        "canonical_id_mismatch_count": _sum(
            metrics,
            "canonical_id_mismatch_count",
        ),
        "atomic_field_roundtrip_rate": _mean(
            metrics,
            "atomic_field_roundtrip_rate",
        ),
        "locator_roundtrip_rate": _mean(metrics, "locator_roundtrip_rate"),
        "lineage_roundtrip_rate": _mean(metrics, "lineage_roundtrip_rate"),
        "representation_roundtrip_rate": _mean(
            metrics,
            "representation_roundtrip_rate",
        ),
        "identity_collision_count": _sum(metrics, "identity_collision_count"),
        "runtime_benchmark_roundtrip": _mean(
            metrics,
            "runtime_benchmark_roundtrip",
        ),
        "citation_provenance_violation_count": _sum(
            metrics,
            "citation_provenance_violation_count",
        ),
        "reranker_lineage_violation_count": _sum(
            metrics,
            "reranker_lineage_violation_count",
        ),
    }


def _execution_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        "missing_execution_slot_answer_count": _sum(
            metrics,
            "missing_execution_slot_answer_count",
        ),
        "required_slot_false_fill_count": _sum(
            metrics,
            "required_slot_false_fill_count",
        ),
        "slot_semantic_false_fill_count": _sum(
            metrics,
            "slot_semantic_false_fill_count",
        ),
        "slot_unresolved_reference_count": _sum(
            metrics,
            "slot_unresolved_reference_count",
        ),
        "plan_evidence_reference_resolution_rate": _mean(
            metrics,
            "plan_evidence_reference_resolution_rate",
        ),
        "source_page_cross_join_count": _sum(
            metrics,
            "source_page_cross_join_count",
        ),
        "calculation_render_mismatch_count": _sum(
            metrics,
            "calculation_render_mismatch_count",
        ),
        "qasper_stale_verifier_state_count": _sum(
            metrics,
            "qasper_stale_verifier_state_count",
        ),
    }


def _source_summary(
    metrics: list[dict[str, float | None]],
) -> dict[str, float | None]:
    return {
        "gold_runtime_source_join_rate": _mean(
            metrics,
            "gold_runtime_source_join_rate",
        ),
        "unresolved_gold_source_count": _sum(
            metrics,
            "unresolved_gold_source_count",
        ),
        "ambiguous_source_alias_count": _sum(
            metrics,
            "ambiguous_source_alias_count",
        ),
        "gold_runtime_source_page_join_rate": _mean(
            metrics,
            "gold_runtime_source_page_join_rate",
        ),
        "gold_source_schema_valid": _mean(metrics, "gold_source_schema_valid"),
        "gold_source_id_count": _sum(metrics, "gold_source_id_count"),
        "gold_evidence_text_support_recall": _mean(
            metrics,
            "gold_evidence_text_support_recall",
        ),
    }


def _sum(metrics: list[dict[str, float | None]], key: str) -> float:
    return sum(float(metric.get(key) or 0.0) for metric in metrics)


def _mean(
    metrics: list[dict[str, float | None]],
    key: str,
) -> float | None:
    return safe_mean(
        [value for metric in metrics if (value := metric.get(key)) is not None]
    )
