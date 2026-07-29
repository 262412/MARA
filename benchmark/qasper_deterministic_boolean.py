from __future__ import annotations

from typing import Any

from .qasper_boolean_scope import resolve_closed_scope_boolean


def deterministic_closed_scope_result(
    *,
    contract_id: str,
    question: str,
    evidence_items: list[dict[str, Any]],
    candidate_polarity: str,
) -> tuple[str, dict[str, str]] | None:
    resolution = resolve_closed_scope_boolean(question, evidence_items)
    if resolution is None:
        return None
    action = (
        "confirmed_candidate"
        if candidate_polarity == resolution.polarity
        else "corrected_polarity"
    )
    trace = {
        "contract_id": contract_id,
        "status": "ok",
        "verdict": resolution.polarity,
        "action": action,
        "evidence_quote": resolution.evidence_quote,
        "quote_grounded": "true",
        "quote_supports_relation": "true",
        "primary_answer": candidate_polarity or "unanswerable",
        "adjudicated_polarity": resolution.polarity,
        "raw_verifier_verdict": "deterministic_scope",
        "reason": "deterministic_current_scope",
        "parser_status": "not_called_deterministic_scope",
        **resolution.decision.as_trace(),
    }
    return resolution.polarity, trace
