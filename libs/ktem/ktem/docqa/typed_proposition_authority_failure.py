from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from .typed_proposition_authority_atoms import unknown_claim_result
from .verification_schema import VerifyDecision


def coherent_authority_failure(
    decision: VerifyDecision,
    reason: str,
    *,
    typed_authority: dict[str, Any] | None = None,
) -> VerifyDecision:
    """Downgrade every semantic projection together when authority fails."""

    claim_results = [unknown_claim_result(result) for result in decision.claim_results]
    claims = list(decision.claims)
    return replace(
        decision,
        status="unknown",
        reason=f"Typed proposition authority was not established: {reason}.",
        action="abstain",
        unsupported_claims=[],
        unknown_claims=claims,
        verified_citations=[],
        claim_results=claim_results,
        input_answer_polarity="",
        canonical_answer_polarity="",
        semantic_correction_applied=False,
        boolean_authority_status="missing",
        authoritative_evidence_id="",
        authoritative_evidence_ref="",
        authoritative_span_id="",
        authoritative_quote="",
        authoritative_span_start=None,
        authoritative_span_end=None,
        authoritative_canonical_start=None,
        authoritative_canonical_end=None,
        actor="",
        section_scope="",
        relation="",
        object="",
        predicate_arguments=(),
        qualifier="",
        quantifier="",
        verified_support_slot_ids=[],
        authority_derivations=(),
        selected_derivation_id="",
        authoritative_conflict={},
        typed_authority=deepcopy(typed_authority or {}),
    )
