from __future__ import annotations

from typing import Any

from .qasper_runtime_projection import runtime_projection_present


def qasper_terminal_scoring_commit(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> tuple[str, bool]:
    """Select the immutable non-Boolean QASPER engine answer for scoring."""

    qasper = "qasper" in str(dataset_name or "").strip().lower()
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    preserve = bool(
        qasper
        and answer_type not in {"boolean", "unanswerable"}
        and runtime_projection_present(prediction)
    )
    source = "engine_terminal_answer" if preserve else "predicted_answer"
    return str(prediction.get(source) or ""), preserve
