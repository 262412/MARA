from __future__ import annotations

import math
from typing import Any

from .answer_repetition import final_answer_has_duplicate
from .calculation_stage_metrics import (
    calculation_metrics,
    calculation_status,
    is_finance_numeric_prediction,
)
from .evidence_identity_metrics import gold_evidence_support_recall, reranker_lineage
from .evidence_stage_coverage import (
    gold_requirement_keys,
    matched_gold,
    reranked_trace_available,
    stage_coverage_values,
)
from .metrics import is_abstention_answer, round_metric, safe_mean
from .page_stage_metrics import (
    all_gold_pages_hit,
    legacy_all_gold_pages_hit,
    stage_all_gold_pages_hit,
)
from .report_identity_compaction import is_identity_only_projection

STAGE_METRIC_KEYS = (
    "candidate_recall_at_50",
    "candidate_page_coverage_at_50",
    "candidate_pool_recall_at_80",
    "canonical_candidate_evidence_coverage",
    "post_fusion_evidence_coverage",
    "reranked_recall_at_10",
    "fused_evidence_coverage",
    "reranker_input_evidence_coverage",
    "selected_evidence_coverage",
    "used_evidence_coverage",
    "generation_context_evidence_coverage",
    "execution_operand_evidence_coverage",
    "verified_evidence_coverage",
    "verified_claim_support_evidence_coverage",
    "cited_evidence_coverage",
    "emitted_citation_evidence_coverage",
    "reranker_lineage_coverage",
    "gold_evidence_support_recall",
    "retrieval_mrr",
    "retrieval_ndcg",
    "all_gold_pages_hit",
    "candidate_all_gold_pages_hit",
    "selected_all_gold_pages_hit",
    "generation_context_all_gold_pages_hit",
    "cited_all_gold_pages_hit",
    "legacy_page_only_all_gold_pages_hit",
    "gold_table_cell_recall",
    "slot_coverage",
    "retrieval_slot_coverage",
    "verified_slot_coverage",
    "unique_pages",
    "duplicate_ratio",
    "executor_activation_rate",
    "all_operands_bound",
    "overall_all_operands_bound",
    "answerable_all_operands_bound",
    "expected_missing_slot_detection",
    "overall_slot_coverage",
    "answerable_required_slot_coverage",
    "operand_accuracy",
    "cell_accuracy",
    "operator_accuracy",
    "program_accuracy",
    "execution_accuracy",
    "binding_verifier_pass_rate",
    "program_validity_rate",
    "execution_success_rate",
    "executed_answer_accuracy",
    "unit_accuracy",
    "successful_execution_unit_accuracy",
    "claim_duplicate_rate",
    "final_answer_duplicate_rate",
    "final_answer_repetition_repair_rate",
    "judge_failure_rate",
    "parent_table_candidate_count",
    "materialized_table_count",
    "materialized_cell_count",
    "materialization_cache_hit_rate",
    "materialized_cells_per_required_slot",
    "candidate_count_before_materialization",
    "candidate_count_after_materialization",
    "materialization_seconds",
)
_EVIDENCE_STAGE_TRACE_KEYS = (
    "fused_evidence",
    "reranker_input_evidence",
    "selected_evidence",
    "used_evidence",
    "generation_context_evidence",
    "execution_operand_evidence",
    "verified_evidence",
    "cited_evidence",
)


def prediction_stage_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    (
        candidate_pool,
        candidates,
        reranked,
        gold_keys,
        lineage_coverage,
    ) = _stage_retrieval_context(prediction, metadata)
    support_recall = _stage_support_recall(prediction, candidate_pool)
    selection = dict(metadata.get("evidence_selection_trace") or {})
    dedupe = dict(metadata.get("dedupe_trace") or {})
    materialization = dict(metadata.get("materialization_trace") or {})
    finance = dict(metadata.get("finance_numeric_trace") or {})
    calculation = calculation_metrics(
        finance,
        applicable=(
            "finance_numeric_trace" in metadata
            or is_finance_numeric_prediction(prediction)
        ),
        rendered_answer=str(prediction.get("answer_for_scoring") or ""),
        gold_numeric_match=_float_or_none(
            (prediction.get("metrics") or {}).get("numeric_match")
        ),
        answerable=_gold_answerable(prediction),
    )
    verified_slot_coverage = calculation.get("verified_slot_coverage")
    if verified_slot_coverage is None:
        verified_slot_coverage = _final_visual_slot_coverage(metadata)
    return {
        **stage_coverage_values(
            prediction,
            metadata,
            candidates=candidates,
            candidate_pool=candidate_pool,
            reranked=reranked,
            gold=gold_keys,
        ),
        "reranker_lineage_coverage": lineage_coverage,
        "gold_evidence_support_recall": support_recall,
        "retrieval_mrr": _mrr(reranked, gold_keys),
        "retrieval_ndcg": _ndcg(reranked, gold_keys),
        **_stage_page_hit_metrics(prediction),
        "gold_table_cell_recall": _element_recall(prediction),
        "slot_coverage": _float_or_none(metadata.get("slot_coverage")),
        "retrieval_slot_coverage": _float_or_none(metadata.get("slot_coverage")),
        "unique_pages": _float_or_none(selection.get("unique_pages")),
        "duplicate_ratio": _float_or_none(dedupe.get("duplicate_ratio")),
        **{
            key: _float_or_none(materialization.get(key))
            for key in (
                "parent_table_candidate_count",
                "materialized_table_count",
                "materialized_cell_count",
                "materialization_cache_hit_rate",
                "materialized_cells_per_required_slot",
                "candidate_count_before_materialization",
                "candidate_count_after_materialization",
                "materialization_seconds",
            )
        },
        **calculation,
        "verified_slot_coverage": verified_slot_coverage,
        "claim_duplicate_rate": _claim_duplicate_rate(prediction),
        "final_answer_duplicate_rate": _final_answer_duplicate_rate(prediction),
        "final_answer_repetition_repair_rate": (
            _final_answer_repetition_repair_rate(prediction)
        ),
        "judge_failure_rate": _judge_failure_rate(prediction),
    }


def _gold_answerable(prediction: dict[str, Any]) -> bool:
    return any(
        str(answer or "").strip() and not is_abstention_answer(str(answer))
        for answer in prediction.get("gold_answers") or []
    )


def _stage_retrieval_context(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[
    list[dict[str, Any]] | None,
    list[dict[str, Any]] | None,
    list[dict[str, Any]] | None,
    set[tuple[str, str, str, str]],
    float | None,
]:
    candidate_pool = (
        _records(metadata.get("canonical_candidate_evidence"))
        if "canonical_candidate_evidence" in metadata
        else (
            _records(metadata.get("candidate_evidence"))
            if "candidate_evidence" in metadata
            else None
        )
    )
    ranked = (
        _records(metadata.get("candidate_ranked_evidence"))
        if "candidate_ranked_evidence" in metadata
        else (
            _records(metadata.get("fused_evidence"))
            if "fused_evidence" in metadata
            else candidate_pool
        )
    )
    candidates = ranked[:50] if ranked is not None else None
    reranked = (
        _records(metadata.get("reranked_evidence"))[:10]
        if reranked_trace_available(metadata)
        else None
    )
    gold_keys = _gold_keys(prediction)
    lineage = (
        reranker_lineage(candidate_pool, reranked)[0]
        if candidate_pool is not None and reranked is not None
        else None
    )
    return candidate_pool, candidates, reranked, gold_keys, lineage


def _stage_support_recall(
    prediction: dict[str, Any],
    candidate_pool: list[dict[str, Any]] | None,
) -> float | None:
    support_recall = gold_evidence_support_recall(
        candidate_pool,
        _records(prediction.get("gold_evidence")),
    )
    if candidate_pool and is_identity_only_projection(candidate_pool):
        return (prediction.get("stage_metrics") or {}).get(
            "gold_evidence_support_recall"
        )
    return support_recall


def _stage_page_hit_metrics(
    prediction: dict[str, Any],
) -> dict[str, float | None]:
    return {
        "all_gold_pages_hit": all_gold_pages_hit(prediction),
        "candidate_all_gold_pages_hit": stage_all_gold_pages_hit(
            prediction, "candidate_evidence"
        ),
        "selected_all_gold_pages_hit": stage_all_gold_pages_hit(
            prediction, "selected_evidence"
        ),
        "generation_context_all_gold_pages_hit": stage_all_gold_pages_hit(
            prediction, "generation_context_evidence"
        ),
        "cited_all_gold_pages_hit": stage_all_gold_pages_hit(
            prediction, "cited_evidence"
        ),
        "legacy_page_only_all_gold_pages_hit": legacy_all_gold_pages_hit(prediction),
    }


def prediction_stage_metric_status(
    prediction: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    (
        gold_count,
        candidate_count,
        reranked_count,
        candidate_pool,
        reranked,
        candidate_status,
        reranked_status,
    ) = _retrieval_status_inputs(
        prediction,
        metadata,
    )
    status: dict[str, dict[str, Any]] = {
        "candidate_recall_at_50": {
            "status": candidate_status,
            "gold_identity_count": gold_count,
            "candidate_count": candidate_count,
        },
        "candidate_pool_recall_at_80": {
            "status": candidate_status,
            "gold_identity_count": gold_count,
            "candidate_count": len(candidate_pool),
        },
        "reranked_recall_at_10": {
            "status": reranked_status,
            "gold_identity_count": gold_count,
            "candidate_count": reranked_count,
        },
        "retrieval_mrr": {
            "status": reranked_status,
            "gold_identity_count": gold_count,
            "candidate_count": reranked_count,
        },
        "retrieval_ndcg": {
            "status": reranked_status,
            "gold_identity_count": gold_count,
            "candidate_count": reranked_count,
        },
    }
    for trace_key in _EVIDENCE_STAGE_TRACE_KEYS:
        metric_key = f"{trace_key}_coverage"
        records = _records(metadata.get(trace_key))
        status[metric_key] = {
            "status": _retrieval_metric_status(
                gold_count=gold_count,
                trace_available=trace_key in metadata,
            ),
            "gold_identity_count": gold_count,
            "candidate_count": len(records),
        }
    status.update(
        _identity_metric_status(
            prediction,
            metadata=metadata,
            candidate_pool=candidate_pool,
            reranked=reranked,
        )
    )
    if _final_visual_slot_coverage(metadata) is not None:
        status["verified_slot_coverage"] = {
            "status": "measured",
            "source": "visual_final_binding_projection.v1",
        }
    status["calculation_pipeline"] = calculation_status(
        dict(metadata.get("finance_numeric_trace") or {}),
        applicable=(
            "finance_numeric_trace" in metadata
            or is_finance_numeric_prediction(prediction)
        ),
        rendered_answer=str(prediction.get("answer_for_scoring") or ""),
    )
    return status


def _retrieval_status_inputs(
    prediction: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[int, int, int, list[dict[str, Any]], list[dict[str, Any]], str, str]:
    requirements = gold_requirement_keys(prediction)
    gold_count = len(requirements) if requirements else len(_gold_keys(prediction))
    candidate_trace_key = (
        "canonical_candidate_evidence"
        if "canonical_candidate_evidence" in metadata
        else "candidate_evidence"
    )
    candidate_pool = _records(metadata.get(candidate_trace_key))
    reranked = _records(metadata.get("reranked_evidence"))[:10]
    candidate_status = _retrieval_metric_status(
        gold_count=gold_count,
        trace_available=candidate_trace_key in metadata,
    )
    reranked_status = _retrieval_metric_status(
        gold_count=gold_count,
        trace_available=reranked_trace_available(metadata),
    )
    return (
        gold_count,
        len(candidate_pool),
        len(reranked),
        candidate_pool,
        reranked,
        candidate_status,
        reranked_status,
    )


def _identity_metric_status(
    prediction: dict[str, Any],
    *,
    metadata: dict[str, Any],
    candidate_pool: list[dict[str, Any]],
    reranked: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    traces_available = "candidate_evidence" in metadata and reranked_trace_available(
        metadata
    )
    violation_count = (
        reranker_lineage(candidate_pool, reranked)[1] if traces_available else None
    )
    gold_support_count = sum(
        any(
            str(item.get(key) or "").strip()
            for key in ("span", "text", "quote", "evidence")
        )
        for item in _records(prediction.get("gold_evidence"))
    )
    identity_only = is_identity_only_projection(candidate_pool)
    preserved_support = (prediction.get("stage_metrics") or {}).get(
        "gold_evidence_support_recall"
    )
    support_available = "candidate_evidence" in metadata and (
        not identity_only or preserved_support is not None
    )
    return {
        "reranker_lineage_coverage": {
            "status": "measured" if traces_available else "unavailable",
            "candidate_pool_count": len(candidate_pool),
            "reranked_count": len(reranked),
            "violation_count": violation_count,
        },
        "gold_evidence_support_recall": {
            "status": (
                "measured"
                if gold_support_count and support_available
                else "not_applicable"
                if not gold_support_count
                else "unavailable"
            ),
            "gold_identity_count": gold_support_count,
            "candidate_count": len(candidate_pool),
        },
    }


def stage_metric_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    averages = {
        f"avg_{key}": round_metric(
            safe_mean(
                [
                    (prediction.get("stage_metrics") or {}).get(key)
                    for prediction in predictions
                ]
            )
        )
        for key in STAGE_METRIC_KEYS
    }
    coverage = {
        f"coverage_{key}": (
            round_metric(
                sum(_metric_is_available(prediction, key) for prediction in predictions)
                / len(predictions)
            )
            if predictions
            else None
        )
        for key in STAGE_METRIC_KEYS
    }
    return {**averages, **coverage}


def _gold_keys(prediction: dict[str, Any]) -> set[tuple[str, str, str, str]]:
    keys: set[tuple[str, str, str, str]] = set()
    for item in _records(prediction.get("gold_evidence")):
        source = str(item.get("source_id") or item.get("document_id") or "")
        page = str(item.get("page_label") or item.get("page") or "")
        identity = item.get("identity")
        identity = identity if isinstance(identity, dict) else {}
        kind, element = _gold_kind_and_local_id(item, identity)
        if source or page or element:
            keys.add((source, page, kind, element))
    if not keys:
        for page in prediction.get("gold_pages") or []:
            keys.add(("", str(page), "", ""))
    return keys


def _mrr(
    items: list[dict[str, Any]] | None,
    gold: set[tuple[str, str, str, str]],
) -> float | None:
    if items is None or not gold:
        return None
    for rank, item in enumerate(items, start=1):
        if matched_gold(item, gold):
            return 1.0 / rank
    return 0.0


def _ndcg(
    items: list[dict[str, Any]] | None,
    gold: set[tuple[str, str, str, str]],
) -> float | None:
    if items is None or not gold:
        return None
    if not items:
        return 0.0
    seen_gold: set[tuple[str, str, str, str]] = set()
    gains: list[float] = []
    for item in items:
        new_matches = matched_gold(item, gold) - seen_gold
        gains.append(1.0 if new_matches else 0.0)
        seen_gold.update(new_matches)
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, start=1))
    ideal_count = min(len(gold), len(items))
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return dcg / ideal if ideal else None


def _element_recall(prediction: dict[str, Any]) -> float | None:
    gold = {
        str(item.get("cell_id") or item.get("span_id") or item.get("element_id") or "")
        for item in _records(prediction.get("gold_evidence"))
        if item.get("cell_id") or item.get("span_id") or item.get("element_id")
    }
    if not gold:
        return None
    predicted = {str(item) for item in prediction.get("predicted_element_ids") or []}
    return len(gold & predicted) / len(gold)


def _gold_kind_and_local_id(
    item: dict[str, Any],
    identity: dict[str, Any],
) -> tuple[str, str]:
    if item.get("cell_id"):
        return "cell", str(item["cell_id"])
    if item.get("span_id"):
        return "span", str(item["span_id"])
    if item.get("element_id"):
        return "element", str(item["element_id"])
    if identity.get("local_id"):
        return str(identity.get("kind") or ""), str(identity["local_id"])
    if item.get("evidence_id"):
        return "evidence", str(item["evidence_id"])
    return "", ""


def _claim_duplicate_rate(prediction: dict[str, Any]) -> float | None:
    for event in prediction.get("controller_trace") or []:
        if not isinstance(event, dict) or event.get("stage") != "claim_aggregation":
            continue
        before = int(event.get("input_claim_count") or 0)
        after = int(event.get("output_claim_count") or 0)
        return (before - after) / before if before else 0.0
    return None


def _judge_failure_rate(prediction: dict[str, Any]) -> float | None:
    evaluation = dict(prediction.get("semantic_answer_evaluation") or {})
    status = str(evaluation.get("judge_status") or "")
    if status not in {"ok", "error"}:
        return None
    return float(status == "error")


def _final_answer_duplicate_rate(prediction: dict[str, Any]) -> float | None:
    finalization = prediction.get("answer_finalization")
    if not isinstance(finalization, dict) or "repetition_removed" not in finalization:
        return None
    return float(final_answer_has_duplicate(prediction))


def _final_answer_repetition_repair_rate(
    prediction: dict[str, Any],
) -> float | None:
    finalization = prediction.get("answer_finalization")
    if not isinstance(finalization, dict) or "repetition_removed" not in finalization:
        return None
    return float(bool(finalization.get("repetition_removed")))


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _final_visual_slot_coverage(metadata: dict[str, Any]) -> float | None:
    projection = metadata.get("final_binding_projection")
    if not isinstance(projection, dict):
        return None
    if (
        projection.get("contract_id") != "visual_final_binding_projection.v1"
        or projection.get("status") != "verified_support"
    ):
        return None
    return _float_or_none(projection.get("verified_slot_coverage"))


def _retrieval_metric_status(*, gold_count: int, trace_available: bool) -> str:
    if gold_count == 0:
        return "not_applicable"
    return "measured" if trace_available else "unavailable"


def _metric_is_available(prediction: dict[str, Any], key: str) -> bool:
    status = dict(prediction.get("stage_metric_status") or {}).get(key)
    if isinstance(status, dict):
        return status.get("status") == "measured"
    return (prediction.get("stage_metrics") or {}).get(key) is not None
