from __future__ import annotations

import re
from typing import Any

from ktem.docqa.evidence_identity import identity_of

from .qasper_boolean_scope import (
    evidence_item_text,
    resolve_closed_scope_boolean,
    scope_valid_support_items,
)


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
        **_deterministic_input_trace(
            question,
            resolution.polarity,
            evidence_items,
        ),
        **resolution.decision.as_trace(),
    }
    return resolution.polarity, trace


def _deterministic_input_trace(
    question: str,
    polarity: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, str]:
    support_items = scope_valid_support_items(question, polarity, evidence_items)
    support = min(support_items, key=lambda item: len(evidence_item_text(item)))
    support_id = identity_of(support).key
    dropped_ids: list[str] = []
    for item in evidence_items:
        identity = identity_of(item).key
        if identity != support_id and identity not in dropped_ids:
            dropped_ids.append(identity)
    text = evidence_item_text(support)
    return {
        "evidence_budget_status": "deterministic_scope",
        "verifier_input_evidence_ids": support_id,
        "verifier_dropped_evidence_ids": ",".join(dropped_ids),
        "verifier_input_character_count": str(len(text)),
        "verifier_input_token_count": str(len(re.findall(r"\S+", text))),
        "verifier_budget_exhausted": "false",
    }
