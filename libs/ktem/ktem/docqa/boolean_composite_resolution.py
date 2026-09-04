from __future__ import annotations

from typing import Any

from .boolean_authority_derivation import boolean_derivation_contract_status
from .boolean_authority_schema import BooleanClaimAuthority, supported_boolean_claim
from .boolean_composite_authority import (
    CompositeBooleanProof,
    same_source_argument_conjunctions,
)
from .boolean_entity_type_authority import same_source_typed_entity_derivations


def composite_boolean_claim_authority(
    prompt: str,
    input_polarity: str,
    items: list[dict[str, Any]],
) -> BooleanClaimAuthority | None:
    """Resolve one independently validated multi-premise Boolean proof."""

    proofs = _verified_composite_proofs(prompt, items)
    if not proofs:
        return None
    derivation, premises = proofs[0]
    canonical_polarity = str(derivation.conclusion.get("polarity") or "")
    return supported_boolean_claim(
        prompt,
        input_polarity,
        canonical_polarity,
        premises,
        reason="composite_boolean_proposition",
        authority_derivations=(derivation,),
        selected_derivation_id=derivation.derivation_id,
    )


def _verified_composite_proofs(
    prompt: str,
    items: list[dict[str, Any]],
) -> tuple[CompositeBooleanProof, ...]:
    candidates = (
        *same_source_typed_entity_derivations(prompt, items),
        *same_source_argument_conjunctions(prompt, items),
    )
    verified = [
        proof
        for proof in candidates
        if boolean_derivation_contract_status(
            proof[0].as_dict(),
            [premise.as_dict() for premise in proof[1]],
            question=prompt,
            canonical_polarity=str(proof[0].conclusion.get("polarity") or ""),
        )
        == "bound"
    ]
    return tuple(sorted(verified, key=lambda proof: proof[0].derivation_id))
