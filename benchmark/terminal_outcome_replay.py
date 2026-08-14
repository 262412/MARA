from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .terminal_outcome_contract import (
    apply_benchmark_outcome_classification,
    apply_terminal_outcome_record,
)

_ADAPTER_FIELDS = {
    "terminal_outcome",
    "terminal_outcome_reason",
    "terminal_outcome_contract_violation",
    "terminal_outcome_classification",
}


def replay_terminal_outcome_adapter(
    predictions: list[dict[str, Any]],
) -> dict[str, Any]:
    replayed = deepcopy(predictions)
    before = [_unchanged_projection(row) for row in replayed]
    for prediction in replayed:
        apply_terminal_outcome_record(prediction)
        apply_benchmark_outcome_classification(prediction)
    after = [_unchanged_projection(row) for row in replayed]
    matches = [left == right for left, right in zip(before, after, strict=True)]
    return {
        "denominator_before": len(predictions),
        "denominator_after": len(replayed),
        "per_row_score_match_count": sum(matches),
        "per_row_score_mismatch_count": len(matches) - sum(matches),
        "score_projection_hash_before": _projection_hash(before),
        "score_projection_hash_after": _projection_hash(after),
    }


def _unchanged_projection(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in prediction.items()
        if key not in _ADAPTER_FIELDS
    }


def _projection_hash(rows: list[dict[str, Any]]) -> str:
    return hashlib.sha256(
        json.dumps(
            rows,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
