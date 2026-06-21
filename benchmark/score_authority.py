from __future__ import annotations

from typing import Any

LOCAL_DATASET_NATIVE_LABEL = "Dataset-Native Local Score"
PAPER_GRADE_EXTERNAL_LABEL = "Paper-Grade External Score"


def paper_grade_score_available(predictions: list[dict[str, Any]]) -> bool:
    return any(
        prediction.get("mara_scoring_source") == "external_paper_grade"
        or "paper_grade_score" in dict(prediction.get("metrics") or {})
        for prediction in predictions
    )


def primary_score_label(paper_grade: bool) -> str:
    if paper_grade:
        return PAPER_GRADE_EXTERNAL_LABEL
    return LOCAL_DATASET_NATIVE_LABEL


def score_authority_level(paper_grade: bool) -> str:
    if paper_grade:
        return "paper_grade_external"
    return "local_dataset_native"
