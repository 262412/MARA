from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .metrics import is_abstention_answer, round_metric, safe_mean


def verification_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    verify_decision = dict(prediction.get("verify_decision") or {})
    status = str(verify_decision.get("status") or "").strip().lower()
    unsupported_claims = _non_empty_items(verify_decision.get("unsupported_claims"))
    verified_citations = _non_empty_items(verify_decision.get("verified_citations"))
    contradictions = _non_empty_items(verify_decision.get("contradictions"))
    return {
        "unsupported_claim_rate": float(
            status == "unsupported" or bool(unsupported_claims)
        ),
        "not_enough_evidence_rate": float(status == "not_enough_evidence"),
        "unsupported_claim_count": float(len(unsupported_claims)),
        "contradiction_count": float(len(contradictions)),
        "verified_citation_count": float(len(verified_citations)),
        "abstention_correctness": _abstention_correctness(prediction),
    }


def verification_summary(predictions: list[dict[str, Any]]) -> dict[str, float | None]:
    return {
        f"avg_{key}": round_metric(
            safe_mean([item["metrics"].get(key) for item in predictions])
        )
        for key in (
            "unsupported_claim_rate",
            "not_enough_evidence_rate",
            "unsupported_claim_count",
            "contradiction_count",
            "verified_citation_count",
            "abstention_correctness",
        )
    }


def _non_empty_items(value: Any) -> list[str]:
    return [str(item) for item in value or [] if str(item or "").strip()]


def _abstention_correctness(prediction: dict[str, Any]) -> float | None:
    expected = dict(prediction.get("expected_guardrails") or {})
    if "allow_abstention" not in expected:
        return None
    abstained = is_abstention_answer(
        extract_final_answer_text(str(prediction.get("predicted_answer") or ""))
    )
    return float(abstained == bool(expected["allow_abstention"]))
