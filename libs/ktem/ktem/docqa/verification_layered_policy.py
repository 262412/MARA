from __future__ import annotations

from typing import Any

from .verification_schema import VerifyDecision


def contradictory_extensions(results: list[Any]) -> list[str]:
    return [
        result.claim
        for index, result in enumerate(results)
        if index > 0
        and (
            result.status in {"contradicted", "conflicting"}
            or bool(result.contradicting_evidence_ids)
        )
    ]


def contradictory_extension_decision(
    mode: str,
    claims: list[str],
    serialized: list[dict[str, Any]],
    contradictory_claims: list[str],
    decision_metadata: dict[str, Any],
) -> VerifyDecision:
    return VerifyDecision(
        mode=mode,
        status="unknown",
        reason=(
            f"{mode.title()} verification found contradictory extension content; "
            "the answer is rejected rather than pruned."
        ),
        action="abstain",
        claims=claims,
        unknown_claims=contradictory_claims,
        claim_results=serialized,
        **decision_metadata,
    )
