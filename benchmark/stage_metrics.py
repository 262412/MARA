from __future__ import annotations

import math
import re
from typing import Any

from .answer_repetition import final_answer_has_duplicate
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
    "executor_activation_rate",
    "all_operands_bound",
    "operand_accuracy",
    "cell_accuracy",
    "operator_accuracy",
    "program_accuracy",
    "execution_accuracy",
    "unit_accuracy",
    "claim_duplicate_rate",
    "final_answer_duplicate_rate",
    "final_answer_repetition_repair_rate",
    "judge_failure_rate",
)


def prediction_stage_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    metadata = dict(prediction.get("evidence_metadata") or {})
    candidates = (
        _records(metadata.get("candidate_evidence"))[:50]
        if "candidate_evidence" in metadata
        else None
    )
    reranked = (
        _records(metadata.get("reranked_evidence"))[:10]
        if "reranked_evidence" in metadata
        else None
    )
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
        **_calculation_metrics(
            finance,
            applicable=(
                "finance_numeric_trace" in metadata
                or _is_finance_numeric_prediction(prediction)
            ),
            rendered_answer=str(prediction.get("answer_for_scoring") or ""),
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
    gold_count = len(_gold_keys(prediction))
    candidate_count = len(_records(metadata.get("candidate_evidence")))
    reranked_count = len(_records(metadata.get("reranked_evidence")))
    candidate_status = _retrieval_metric_status(
        gold_count=gold_count,
        trace_available="candidate_evidence" in metadata,
    )
    reranked_status = _retrieval_metric_status(
        gold_count=gold_count,
        trace_available="reranked_evidence" in metadata,
    )
    status: dict[str, dict[str, Any]] = {
        "candidate_recall_at_50": {
            "status": candidate_status,
            "gold_identity_count": gold_count,
            "candidate_count": candidate_count,
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
    status["calculation_pipeline"] = _calculation_status(
        dict(metadata.get("finance_numeric_trace") or {}),
        applicable=(
            "finance_numeric_trace" in metadata
            or _is_finance_numeric_prediction(prediction)
        ),
        rendered_answer=str(prediction.get("answer_for_scoring") or ""),
    )
    return status


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
        f"coverage_{key}": round_metric(
            sum(_metric_is_available(prediction, key) for prediction in predictions)
            / len(predictions)
        )
        if predictions
        else None
        for key in STAGE_METRIC_KEYS
    }
    return {**averages, **coverage}


def _calculation_metrics(
    finance: dict[str, Any],
    *,
    applicable: bool,
    rendered_answer: str,
) -> dict[str, float | None]:
    plan = dict(finance.get("calculation_plan") or {})
    verification = dict(finance.get("calculation_verification") or {})
    execution = dict(finance.get("calculation_execution") or {})
    operands = _records(plan.get("operands"))
    steps = _records(plan.get("steps"))
    if not plan:
        return {
            "executor_activation_rate": 0.0 if applicable else None,
            "all_operands_bound": 0.0 if applicable else None,
            "operand_accuracy": None,
            "cell_accuracy": None,
            "operator_accuracy": None,
            "program_accuracy": None,
            "execution_accuracy": None,
            "unit_accuracy": None,
        }
    verified = set(verification.get("verified_operand_ids") or [])
    errors = [str(error) for error in verification.get("errors") or []]
    required_slots = list(verification.get("required_slot_ids") or [])
    verified_required = set(verification.get("verified_required_slot_ids") or [])
    operand_accuracy = (
        len(verified_required) / len(required_slots)
        if required_slots
        else len(verified) / len(operands)
        if operands
        else None
    )
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
    rendered_dimension_error = _rendered_dimension_error(plan, rendered_answer)
    return {
        "executor_activation_rate": 1.0,
        "all_operands_bound": float(
            bool(operands)
            and bool(verification.get("valid"))
            and len(verified) == len(operands)
            and (not required_slots or len(verified_required) == len(required_slots))
        ),
        "operand_accuracy": operand_accuracy,
        "cell_accuracy": 1.0 - len(cell_errors) / len(operands) if operands else None,
        "operator_accuracy": 1.0 - len(operator_errors) / len(steps) if steps else 1.0,
        "program_accuracy": float(bool(verification.get("valid"))),
        "execution_accuracy": float(execution.get("status") == "ok"),
        "unit_accuracy": float(not unit_errors and not rendered_dimension_error),
    }


def _calculation_status(
    finance: dict[str, Any],
    *,
    applicable: bool,
    rendered_answer: str,
) -> dict[str, str]:
    if not applicable:
        return {"status": "not_applicable", "failure_stage": "not_applicable"}
    plan = dict(finance.get("calculation_plan") or {})
    if not plan:
        return {"status": "measured", "failure_stage": "retrieval_or_plan"}
    verification = dict(finance.get("calculation_verification") or {})
    errors = [str(error) for error in verification.get("errors") or []]
    if any("evidence_missing" in error for error in errors):
        failure_stage = "evidence_binding"
    elif any(
        term in error for error in errors for term in ("unit", "scale", "currency")
    ):
        failure_stage = "unit"
    elif not verification.get("valid"):
        failure_stage = "plan_verification"
    elif dict(finance.get("calculation_execution") or {}).get("status") != "ok":
        failure_stage = "execution"
    elif _rendered_dimension_error(plan, rendered_answer):
        failure_stage = "rendered_unit"
    else:
        failure_stage = "none"
    return {"status": "measured", "failure_stage": failure_stage}


def _rendered_dimension_error(
    plan: dict[str, Any],
    rendered_answer: str,
) -> bool:
    answer = str(rendered_answer or "").lower()
    expected_scale = str(plan.get("answer_scale") or "").strip().lower()
    if expected_scale:
        rendered_scale = next(
            (
                scale
                for scale in ("thousand", "million", "billion")
                if re.search(rf"\b{scale}s?\b", answer)
            ),
            "",
        )
        if rendered_scale != expected_scale:
            return True
    expected_unit = str(plan.get("answer_unit") or "").strip().lower()
    if expected_unit in {"percent", "%"}:
        return "%" not in answer and "percent" not in answer
    return False


def _is_finance_numeric_prediction(prediction: dict[str, Any]) -> bool:
    metadata = dict(prediction.get("evidence_metadata") or {})
    query_plan = dict(metadata.get("query_plan") or {})
    constraints = dict(query_plan.get("constraints") or {})
    domains = (
        constraints.get("verification_domain"),
        prediction.get("verification_domain"),
        prediction.get("dataset_name"),
        prediction.get("dataset_family"),
    )
    if not any("finance" in str(value or "").lower() for value in domains):
        return False
    answer_type = (
        str(query_plan.get("answer_type") or prediction.get("answer_type") or "")
        .strip()
        .lower()
    )
    if not answer_type:
        return True
    return answer_type in {
        "calculation",
        "currency",
        "formula",
        "number",
        "numeric",
        "percentage",
        "ratio",
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
            keys.add((source, page, "" if page else element))
    if not keys:
        for page in prediction.get("gold_pages") or []:
            keys.add(("", str(page), ""))
    return keys


def _item_keys(item: dict[str, Any]) -> set[tuple[str, str, str]]:
    sources = _item_sources(item) | {""}
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
    items: list[dict[str, Any]] | None, gold: set[tuple[str, str, str]]
) -> float | None:
    if items is None or not gold:
        return None
    if not items:
        return 0.0
    hits = set().union(*(_matched_gold(item, gold) for item in items))
    return len(hits) / len(gold)


def _mrr(
    items: list[dict[str, Any]] | None,
    gold: set[tuple[str, str, str]],
) -> float | None:
    if items is None or not gold:
        return None
    for rank, item in enumerate(items, start=1):
        if _matched_gold(item, gold):
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
        new_matches = _matched_gold(item, gold) - seen_gold
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


def _item_sources(item: dict[str, Any]) -> set[str]:
    sources = {
        str(item.get("source_id") or ""),
        str(item.get("document_id") or ""),
    }
    source_name = str(item.get("source_name") or item.get("file_name") or "")
    if source_name:
        filename = source_name.rsplit("/", 1)[-1]
        sources.add(filename.rsplit(".", 1)[0])
    for source_ref in item.get("source_backrefs") or []:
        sources.add(str(source_ref or "").split("#", 1)[0])
    return {source for source in sources if source}


def _retrieval_metric_status(*, gold_count: int, trace_available: bool) -> str:
    if gold_count == 0:
        return "not_applicable"
    return "measured" if trace_available else "unavailable"


def _metric_is_available(prediction: dict[str, Any], key: str) -> bool:
    status = dict(prediction.get("stage_metric_status") or {}).get(key)
    if isinstance(status, dict):
        return status.get("status") == "measured"
    return (prediction.get("stage_metrics") or {}).get(key) is not None
