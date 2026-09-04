from __future__ import annotations

from typing import Any

SCORE_TIE_PRECISION_DECIMALS = 6
CANONICAL_TIE_BREAKER = "canonical_evidence_identity"


def quantized_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        score = 0.0
    return round(score, SCORE_TIE_PRECISION_DECIMALS)


def ranking_contract_trace() -> dict[str, Any]:
    return {
        "score_tie_precision_decimals": SCORE_TIE_PRECISION_DECIMALS,
        "tie_breaker": CANONICAL_TIE_BREAKER,
    }
