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
from .metrics import round_metric, safe_mean
from .report_identity_compaction import is_identity_only_projection

STAGE_METRIC_KEYS = (
    "candidate_recall_at_50",
    "candidate_page_coverage_at_50",
    "candidate_pool_recall_at_80",
    "reranked_recall_at_10",
    "selected_evidence_coverage",
    "used_evidence_coverage",
    "generation_context_evidence_coverage",
    "verified_evidence_coverage",
    "cited_evidence_coverage",
    "reranker_lineage_coverage",
    "gold_evidence_support_recall",
    "retrieval_mrr",
    "retrieval_ndcg",
    "all_gold_pages_hit",
    "gold_table_cell_recall",
    "slot_coverage",
    "retrieval_slot_coverage",
    "verified_slot_coverage",
    "unique_pages",
    "duplicate_ratio",
    "executor_activation_rate",
    "all_operands_bound",
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
)


def prediction_stage_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    candidate_pool = (
        _records(metadata.get("candidate_evidence"))[:80]
        if "candidate_evidence" in metadata
        else None
    )
    candidates = candidate_pool[:50] if candidate_pool is not None else None
    reranked_available = reranked_trace_available(metadata)
    reranked = (
        _records(metadata.get("reranked_evidence"))[:10] if reranked_available else None
    )
    gold_keys = _gold_keys(prediction)
    lineage_coverage = (
        reranker_lineage(candidate_pool, reranked)[0]
        if candidate_pool is not None and reranked is not None
        else None
    )
    support_recall = gold_evidence_support_recall(
        candidate_pool,
        _records(prediction.get("gold_evidence")),
    )
    if candidate_pool and is_identity_only_projection(candidate_pool):
        support_recall = (prediction.get("stage_metrics") or {}).get(
            "gold_evidence_support_recall"
        )
    selection = dict(metadata.get("evidence_selection_trace") or {})
    dedupe = dict(metadata.get("dedupe_trace") or {})
    finance = dict(metadata.get("finance_numeric_trace") or {})
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
        "all_gold_pages_hit": _all_gold_pages_hit(prediction),
        "gold_table_cell_recall": _element_recall(prediction),
        "slot_coverage": _float_or_none(metadata.get("slot_coverage")),
        "retrieval_slot_coverage": _float_or_none(metadata.get("slot_coverage")),
        "unique_pages": _float_or_none(selection.get("unique_pages")),
        "duplicate_ratio": _float_or_none(dedupe.get("duplicate_ratio")),
        **calculation_metrics(
            finance,
            applicable=(
                "finance_numeric_trace" in metadata
                or is_finance_numeric_prediction(prediction)
            ),
            rendered_answer=str(prediction.get("answer_for_scoring") or ""),
            gold_numeric_match=_float_or_none(
                (prediction.get("metrics") or {}).get("numeric_match")
            ),
        ),
        "claim_duplicate_rate": _claim_duplicate_rate(prediction),
        "final_answer_duplicate_rate": _final_answer_duplicate_rate(prediction),
        "final_answer_repetition_repair_rate": (
            _final_answer_repetition_repair_rate(prediction)
        ),
        "judge_failure_rate": _judge_failure_rate(prediction),
    }


def prediction_stage_metric_status(
    prediction: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    requirements = gold_requirement_keys(prediction)
    gold_count = len(requirements) if requirements else len(_gold_keys(prediction))
    candidate_count = len(_records(metadata.get("candidate_evidence")))
    reranked_count = len(_records(metadata.get("reranked_evidence")))
    candidate_pool = _records(metadata.get("candidate_evidence"))[:80]
    reranked = _records(metadata.get("reranked_evidence"))[:10]
    stage_trace_keys = (
        "selected_evidence",
        "used_evidence",
        "generation_context_evidence",
        "verified_evidence",
        "cited_evidence",
    )
    candidate_status = _retrieval_metric_status(
        gold_count=gold_count,
        trace_available="candidate_evidence" in metadata,
    )
    reranked_status = _retrieval_metric_status(
        gold_count=gold_count,
        trace_available=reranked_trace_available(metadata),
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
    for trace_key in stage_trace_keys:
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
    status["calculation_pipeline"] = calculation_status(
        dict(metadata.get("finance_numeric_trace") or {}),
        applicable=(
            "finance_numeric_trace" in metadata
            or is_finance_numeric_prediction(prediction)
        ),
        rendered_answer=str(prediction.get("answer_for_scoring") or ""),
    )
    return status


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


def _gold_keys(prediction: dict[str, Any]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for item in _records(prediction.get("gold_evidence")):
        source = str(item.get("source_id") or item.get("document_id") or "")
        page = str(item.get("page_label") or item.get("page") or "")
        element = str(
            item.get("cell_id")
            or item.get("span_id")
            or item.get("element_id")
            or item.get("evidence_id")
            or ""
        )
        if source or page or element:
            keys.add((source, page, element))
    if not keys:
        for page in prediction.get("gold_pages") or []:
            keys.add(("", str(page), ""))
    return keys


def _mrr(
    items: list[dict[str, Any]] | None,
    gold: set[tuple[str, str, str]],
) -> float | None:
    if items is None or not gold:
        return None
    for rank, item in enumerate(items, start=1):
        if matched_gold(item, gold):
            return 1.0 / rank
    return 0.0


def _ndcg(
    items: list[dict[str, Any]] | None,
    gold: set[tuple[str, str, str]],
) -> float | None:
    if items is None or not gold:
        return None
    if not items:
        return 0.0
    seen_gold: set[tuple[str, str, str]] = set()
    gains: list[float] = []
    for item in items:
        new_matches = matched_gold(item, gold) - seen_gold
        gains.append(1.0 if new_matches else 0.0)
        seen_gold.update(new_matches)
    dcg = sum(gain / math.log2(rank + 1) for rank, gain in enumerate(gains, start=1))
    ideal_count = min(len(gold), len(items))
    ideal = sum(1.0 / math.log2(rank + 1) for rank in range(1, ideal_count + 1))
    return dcg / ideal if ideal else None


def _all_gold_pages_hit(prediction: dict[str, Any]) -> float | None:
    gold = {str(page) for page in prediction.get("gold_pages") or []}
    if not gold:
        return None
    predicted = {str(page) for page in prediction.get("predicted_pages") or []}
    return float(gold <= predicted)


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


def _retrieval_metric_status(*, gold_count: int, trace_available: bool) -> str:
    if gold_count == 0:
        return "not_applicable"
    return "measured" if trace_available else "unavailable"


def _metric_is_available(prediction: dict[str, Any], key: str) -> bool:
    status = dict(prediction.get("stage_metric_status") or {}).get(key)
    if isinstance(status, dict):
        return status.get("status") == "measured"
    return (prediction.get("stage_metrics") or {}).get(key) is not None
