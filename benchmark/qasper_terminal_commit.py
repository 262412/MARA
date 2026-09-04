from __future__ import annotations

from typing import Any

from .qasper_runtime_projection import (
    runtime_projection_present,
    runtime_terminal_commit,
)


def qasper_terminal_scoring_commit(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> tuple[str, bool]:
    """Select the immutable runtime semantic answer for benchmark projection."""

    del dataset_name
    commit = runtime_terminal_commit(prediction)
    preserve = bool(commit and runtime_projection_present(prediction))
    if preserve:
        return str(commit.get("semantic_answer") or ""), True
    return str(prediction.get("predicted_answer") or ""), False
