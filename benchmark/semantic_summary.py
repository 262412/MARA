from __future__ import annotations

from typing import Any

from .metrics import round_metric


def semantic_answer_coverage(
    predictions: list[dict[str, Any]],
) -> dict[str, float | None]:
    applicable = [
        prediction
        for prediction in predictions
        if _judge_status(prediction) != "not_applicable"
    ]
    judge_predictions = [
        prediction
        for prediction in applicable
        if _judge_status(prediction) in {"ok", "error", "not_configured"}
    ]
    scored = sum(
        (prediction.get("metrics") or {}).get("semantic_answer_f1") is not None
        for prediction in applicable
    )
    judged = sum(_judge_status(prediction) == "ok" for prediction in judge_predictions)
    return {
        "semantic_answer_coverage": round_metric(
            scored / len(applicable) if applicable else None
        ),
        "semantic_judge_coverage": round_metric(
            judged / len(judge_predictions) if judge_predictions else None
        ),
    }


def _judge_status(prediction: dict[str, Any]) -> str:
    return str(
        (prediction.get("semantic_answer_evaluation") or {}).get("judge_status") or ""
    )
