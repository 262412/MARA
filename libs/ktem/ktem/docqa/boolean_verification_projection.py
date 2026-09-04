from __future__ import annotations

from typing import Any

from .boolean_authority_schema import (
    SEMANTIC_EVIDENCE_SET_RULE,
    BooleanClaimAuthority,
    BooleanEvidenceAuthority,
)
from .boolean_claim_verification import boolean_claim_authority
from .verification_schema import VerifiedClaim


def boolean_verification(
    prompt: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
    *,
    allow_missing_polarity: bool = False,
) -> tuple[list[str], list[VerifiedClaim]] | None:
    """Project a validated Boolean assessment into the verifier contract."""

    assessment = boolean_claim_authority(
        prompt,
        answer,
        evidence_items,
        allow_missing_polarity=allow_missing_polarity,
    )
    if assessment is None:
        return None
    return project_boolean_assessment(assessment)


def project_boolean_assessment(
    assessment: BooleanClaimAuthority,
) -> tuple[list[str], list[VerifiedClaim]]:
    derivations = tuple(value.as_dict() for value in assessment.authority_derivations)
    selected = next(
        (
            value
            for value in derivations
            if value.get("derivation_id") == assessment.selected_derivation_id
        ),
        None,
    )
    conclusion = selected.get("conclusion") if isinstance(selected, dict) else {}
    conclusion = conclusion if isinstance(conclusion, dict) else {}
    authority = _single_authority(assessment.status, assessment.supporting, selected)
    result = VerifiedClaim(
        claim_id="claim:1",
        claim=assessment.claim,
        status=assessment.status,
        supporting_evidence_ids=_unique_evidence_ids(assessment.supporting),
        contradicting_evidence_ids=_unique_evidence_ids(assessment.contradicting),
        input_answer_polarity=assessment.input_answer_polarity,
        canonical_answer_polarity=assessment.canonical_answer_polarity,
        semantic_correction_applied=assessment.semantic_correction_applied,
        authority_status=_authority_status(
            conflict=bool(assessment.authoritative_conflict),
            selected=selected,
            single=authority is not None,
        ),
        **_authority_identity_fields(authority),
        **_conclusion_frame_fields(authority, conclusion),
        supporting_evidence_spans=tuple(
            value.as_dict() for value in assessment.supporting
        ),
        contradicting_evidence_spans=tuple(
            value.as_dict() for value in assessment.contradicting
        ),
        authority_derivations=derivations,
        selected_derivation_id=assessment.selected_derivation_id,
        authoritative_conflict=assessment.authoritative_conflict or {},
    )
    return [assessment.claim], [result]


def _single_authority(
    status: str,
    supporting: tuple[BooleanEvidenceAuthority, ...],
    selected: dict[str, Any] | None,
) -> BooleanEvidenceAuthority | None:
    return (
        supporting[0] if status == "supported" and supporting and not selected else None
    )


def _unique_evidence_ids(
    authorities: tuple[BooleanEvidenceAuthority, ...],
) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value.evidence_id for value in authorities))


def _authority_status(
    *,
    conflict: bool,
    selected: dict[str, Any] | None,
    single: bool,
) -> str:
    if conflict:
        return "exact_conflict"
    if selected and selected.get("rule_id") == SEMANTIC_EVIDENCE_SET_RULE:
        return "semantic_evidence_set"
    if selected:
        return "composite_exact"
    return "exact" if single else "missing"


def _authority_identity_fields(
    authority: BooleanEvidenceAuthority | None,
) -> dict[str, Any]:
    return {
        "authoritative_evidence_id": authority.evidence_id if authority else "",
        "authoritative_evidence_ref": authority.evidence_ref if authority else "",
        "authoritative_span_id": authority.span_id if authority else "",
        "authoritative_quote": authority.quote if authority else "",
        "authoritative_span_start": authority.span_start if authority else None,
        "authoritative_span_end": authority.span_end if authority else None,
        "authoritative_canonical_start": (
            authority.canonical_start if authority else None
        ),
        "authoritative_canonical_end": authority.canonical_end if authority else None,
    }


def _conclusion_frame_fields(
    authority: BooleanEvidenceAuthority | None,
    conclusion: dict[str, Any],
) -> dict[str, Any]:
    object_value = (
        authority.object if authority else str(conclusion.get("object") or "")
    )
    return {
        "actor": authority.actor if authority else str(conclusion.get("actor") or ""),
        "section_scope": (
            authority.section_scope
            if authority
            else str(conclusion.get("section_scope") or conclusion.get("scope") or "")
        ),
        "relation": (
            authority.relation
            if authority
            else str(conclusion.get("relation") or conclusion.get("predicate") or "")
        ),
        "object": object_value,
        "predicate_arguments": (
            (object_value,)
            if authority and object_value
            else tuple(str(value) for value in conclusion.get("arguments") or ())
        ),
        "qualifier": (
            authority.qualifier if authority else str(conclusion.get("qualifier") or "")
        ),
        "quantifier": (
            authority.quantifier
            if authority
            else str(conclusion.get("quantifier") or "")
        ),
    }
