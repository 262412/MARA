from __future__ import annotations

import math
from typing import Any

from .metrics import round_metric, safe_mean

STAGE_METRIC_KEYS = (
    "candidate_recall_at_50",
    "reranked_recall_at_10",
    "retrieval_mrr",
    "retrieval_ndcg",
    "all_gold_pages_hit",
    "gold_table_cell_recall",
    "slot_coverage",
    "unique_pages",
    "duplicate_ratio",
    "operand_accuracy",
    "cell_accuracy",
    "operator_accuracy",
    "program_accuracy",
    "execution_accuracy",
    "unit_accuracy",
    "claim_duplicate_rate",
    "judge_failure_rate",
)


def prediction_stage_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    candidates = _records(metadata.get("candidate_evidence"))[:50]
    reranked = _records(metadata.get("reranked_evidence"))[:10]
    gold_keys = _gold_keys(prediction)
    selection = dict(metadata.get("evidence_selection_trace") or {})
    dedupe = dict(metadata.get("dedupe_trace") or {})
    finance = dict(metadata.get("finance_numeric_trace") or {})
    return {
        "candidate_recall_at_50": _recall(candidates, gold_keys),
        "reranked_recall_at_10": _recall(reranked, gold_keys),
        "retrieval_mrr": _mrr(reranked, gold_keys),
        "retrieval_ndcg": _ndcg(reranked, gold_keys),
        "all_gold_pages_hit": _all_gold_pages_hit(prediction),
        "gold_table_cell_recall": _element_recall(prediction),
        "slot_coverage": _float_or_none(metadata.get("slot_coverage")),
        "unique_pages": _float_or_none(selection.get("unique_pages")),
        "duplicate_ratio": _float_or_none(dedupe.get("duplicate_ratio")),
        **_calculation_metrics(finance),
        "claim_duplicate_rate": _claim_duplicate_rate(prediction),
        "judge_failure_rate": _judge_failure_rate(prediction),
    }


def stage_metric_summary(predictions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
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


def _calculation_metrics(finance: dict[str, Any]) -> dict[str, float | None]:
    plan = dict(finance.get("calculation_plan") or {})
    verification = dict(finance.get("calculation_verification") or {})
    execution = dict(finance.get("calculation_execution") or {})
    operands = _records(plan.get("operands"))
    steps = _records(plan.get("steps"))
    if not plan:
        return {
            "operand_accuracy": None,
            "cell_accuracy": None,
            "operator_accuracy": None,
            "program_accuracy": None,
            "execution_accuracy": None,
            "unit_accuracy": None,
        }
    verified = set(verification.get("verified_operand_ids") or [])
    errors = [str(error) for error in verification.get("errors") or []]
    operand_accuracy = len(verified) / len(operands) if operands else None
    cell_errors = [error for error in errors if "evidence_missing" in error]
    operator_errors = [
        error
        for error in errors
        if "operator" in error or "step_input" in error or "arity" in error
    ]
    unit_errors = [
        error
        for error in errors
        if any(term in error for term in ("unit", "scale", "currency"))
    ]
    return {
        "operand_accuracy": operand_accuracy,
        "cell_accuracy": 1.0 - len(cell_errors) / len(operands) if operands else None,
        "operator_accuracy": 1.0 - len(operator_errors) / len(steps) if steps else 1.0,
        "program_accuracy": float(bool(verification.get("valid"))),
        "execution_accuracy": float(execution.get("status") == "ok"),
        "unit_accuracy": float(not unit_errors),
    }


def _gold_keys(prediction: dict[str, Any]) -> set[tuple[str, str, str]]:
    keys: set[tuple[str, str, str]] = set()
    for item in _records(prediction.get("gold_evidence")):
        source = str(item.get("source_id") or item.get("document_id") or "")
        page = str(item.get("page_label") or item.get("page") or "")
        element = str(
            item.get("element_id")
            or item.get("cell_id")
            or item.get("evidence_id")
            or ""
        )
        if source or page or element:
            keys.add((source, page, element))
    if not keys:
        for page in prediction.get("gold_pages") or []:
            keys.add(("", str(page), ""))
    return keys


def _item_keys(item: dict[str, Any]) -> set[tuple[str, str, str]]:
    sources = {
        str(item.get("source_id") or item.get("document_id") or ""),
        "",
    }
    pages = {str(item.get("page_label") or item.get("page") or ""), ""}
    elements = {
        str(
            item.get("element_id")
            or item.get("cell_id")
            or item.get("evidence_id")
            or ""
        ),
        "",
    }
    return {
        (source, page, element)
        for source in sources
        for page in pages
        for element in elements
    }


def _matched_gold(
    item: dict[str, Any], gold: set[tuple[str, str, str]]
) -> set[tuple[str, str, str]]:
    item_keys = _item_keys(item)
    return {
        key
        for key in gold
        if any(
            (not key[0] or key[0] == candidate[0])
            and (not key[1] or key[1] == candidate[1])
            and (not key[2] or key[2] == candidate[2])
            for candidate in item_keys
        )
    }


def _recall(
    items: list[dict[str, Any]], gold: set[tuple[str, str, str]]
) -> float | None:
    if not items or not gold:
        return None
    hits = set().union(*(_matched_gold(item, gold) for item in items))
    return len(hits) / len(gold)


def _mrr(items: list[dict[str, Any]], gold: set[tuple[str, str, str]]) -> float | None:
    if not items or not gold:
        return None
    for rank, item in enumerate(items, start=1):
        if _matched_gold(item, gold):
            return 1.0 / rank
    return 0.0


def _ndcg(items: list[dict[str, Any]], gold: set[tuple[str, str, str]]) -> float | None:
    if not items or not gold:
        return None
    gains = [1.0 if _matched_gold(item, gold) else 0.0 for item in items]
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
        str(item.get("element_id") or item.get("cell_id") or "")
        for item in _records(prediction.get("gold_evidence"))
        if item.get("element_id") or item.get("cell_id")
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


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]


def _float_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
