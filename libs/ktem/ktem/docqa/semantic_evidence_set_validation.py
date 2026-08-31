from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from .boolean_authority_derivation import boolean_derivation_contract_status
from .boolean_authority_schema import BooleanEvidenceAuthority
from .semantic_evidence_set_derivation import semantic_evidence_set_derivation
from .semantic_evidence_set_header_validation import validated_semantic_header
from .semantic_evidence_set_premise_validation import (
    semantic_proposition_binding_fields,
    validated_semantic_premises,
)

ValidatedPremises: TypeAlias = tuple[
    tuple[BooleanEvidenceAuthority, ...] | None,
    dict[str, tuple[str, ...]],
    str,
    str,
]


def semantic_evidence_set_runtime_validation_reason(
    request: Any,
    question: str,
    response: Mapping[str, Any],
    items: list[dict[str, Any]],
    *,
    release_mode: bool,
    canonical_plan_projection: Any | None = None,
) -> str:
    """Run the final deterministic authority contract before cache commit."""

    header, header_reason = validated_semantic_header(
        response,
        question,
        release_mode=release_mode,
        canonical_plan_projection=canonical_plan_projection,
    )
    if header is None:
        return header_reason
    verdict, attestation = header
    if verdict == "insufficient_evidence":
        return ""
    premises, slot_support, scope_basis, premise_reason = validated_semantic_premises(
        request,
        question,
        verdict,
        response.get("premises"),
        items,
        proof_mode=str(response.get("proof_mode") or ""),
        canonical_plan_projection=canonical_plan_projection,
    )
    if premises is None:
        return premise_reason
    attestation = {
        **attestation,
        "premise_count": len(premises),
        "complete_proposition": True,
        "scope_basis": scope_basis,
        "required_slot_ids": sorted(
            {slot_id for values in slot_support.values() for slot_id in values}
        ),
        **semantic_proposition_binding_fields(
            question,
            verdict,
            premises,
            canonical_plan_projection=canonical_plan_projection,
        ),
    }
    derivation = semantic_evidence_set_derivation(
        question,
        verdict,
        premises,
        attestation,
        slot_support=slot_support,
        canonical_plan_projection=canonical_plan_projection,
    )
    status = boolean_derivation_contract_status(
        derivation.as_dict(),
        [premise.as_dict() for premise in premises],
        question=question,
        canonical_polarity=verdict,
        canonical_plan_projection=canonical_plan_projection,
    )
    return "" if status == "bound" else status
