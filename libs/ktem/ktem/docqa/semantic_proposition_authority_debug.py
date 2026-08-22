from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .evidence_schema import EvidenceBundle

SEMANTIC_PROPOSITION_AUTHORITY_DEBUG_CONTRACT = (
    "semantic_proposition_authority_debug.v1"
)
SEMANTIC_PROPOSITION_AUTHORITY_DEBUG_MAX_ATTEMPTS = 16


def begin_semantic_authority_debug_attempt(
    bundle: EvidenceBundle,
) -> dict[str, Any] | None:
    verifier = bundle.metadata.get("semantic_proposition_verifier")
    verifier_debug = (
        verifier.get("debug_trace") if isinstance(verifier, Mapping) else None
    )
    if not isinstance(verifier_debug, Mapping):
        return None
    authority = bundle.metadata.get("semantic_proposition_authority")
    prior_debug = (
        authority.get("debug_trace") if isinstance(authority, Mapping) else None
    )
    prior_attempts = (
        list(prior_debug.get("attempts") or [])
        if isinstance(prior_debug, Mapping)
        else []
    )
    attempt_index = (
        int(prior_attempts[-1].get("attempt_index", 0)) + 1 if prior_attempts else 1
    )
    prior_attempts.append(
        {
            "attempt_index": attempt_index,
            "verifier_event_count": int(verifier_debug.get("event_count") or 0),
            "stages": [],
        }
    )
    return {
        "contract_id": SEMANTIC_PROPOSITION_AUTHORITY_DEBUG_CONTRACT,
        "attempts": prior_attempts[-SEMANTIC_PROPOSITION_AUTHORITY_DEBUG_MAX_ATTEMPTS:],
    }


def append_semantic_authority_debug_stage(
    debug_trace: dict[str, Any] | None,
    stage: str,
    status: str,
    reason: str,
) -> None:
    if debug_trace is None:
        return
    debug_trace["attempts"][-1]["stages"].append(
        {"stage": stage, "status": status, "reason": reason}
    )
