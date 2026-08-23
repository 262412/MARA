from __future__ import annotations

from typing import Any

from .boolean_authority_schema import BooleanClaimAuthority
from .evidence_text import extract_final_answer_text


def structured_boolean_candidate_label(answer: str) -> str:
    text = extract_final_answer_text(answer).strip().casefold().rstrip(".")
    aliases = {"true": "yes", "false": "no"}
    text = aliases.get(text, text)
    return text if text in {"yes", "no", "unanswerable"} else ""


def candidate_bound_boolean_claim_authority(
    prompt: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
) -> BooleanClaimAuthority:
    """Assess one structured candidate without substituting its opposite."""

    candidate = structured_boolean_candidate_label(answer)
    if candidate not in {"yes", "no"}:
        return BooleanClaimAuthority(
            claim=f"{candidate or 'invalid'}: {prompt}",
            status="unknown",
            input_answer_polarity=candidate,
            canonical_answer_polarity="",
            semantic_correction_applied=False,
            reason=(
                "unanswerable_requires_candidate_verifier"
                if candidate == "unanswerable"
                else "structured_boolean_candidate_invalid"
            ),
        )
    from .boolean_claim_verification import boolean_claim_authority

    assessment = boolean_claim_authority(prompt, candidate, evidence_items)
    if assessment is None:
        return BooleanClaimAuthority(
            claim=f"{candidate}: {prompt}",
            status="unknown",
            input_answer_polarity=candidate,
            canonical_answer_polarity="",
            semantic_correction_applied=False,
            reason="candidate_authority_missing",
        )
    if assessment.status != "supported":
        return assessment
    if assessment.canonical_answer_polarity == candidate:
        return assessment
    return BooleanClaimAuthority(
        claim=f"{candidate}: {prompt}",
        status="contradicted",
        input_answer_polarity=candidate,
        canonical_answer_polarity="",
        semantic_correction_applied=False,
        contradicting=assessment.supporting,
        reason="candidate_explicitly_contradicted",
        authority_derivations=assessment.authority_derivations,
        selected_derivation_id=assessment.selected_derivation_id,
    )
