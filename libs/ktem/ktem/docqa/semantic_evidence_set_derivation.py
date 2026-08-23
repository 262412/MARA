from __future__ import annotations

from typing import Any

from .boolean_authority_derivation import (
    boolean_derivation_id,
    boolean_derivation_identity_payload,
)
from .boolean_authority_schema import (
    SEMANTIC_EVIDENCE_SET_RULE,
    BooleanAuthorityDerivation,
    BooleanEvidenceAuthority,
)
from .boolean_proposition_arguments import _question_argument_tokens
from .boolean_proposition_qualifiers import proposition_qualifier
from .boolean_proposition_tokens import _relation_surface_tokens
from .boolean_relations import primary_boolean_relation
from .boolean_scope_quantifiers import _closed_quantifier


def semantic_evidence_set_derivation(
    question: str,
    verdict: str,
    premises: tuple[BooleanEvidenceAuthority, ...],
    attestation: dict[str, Any],
    *,
    slot_support: dict[str, tuple[str, ...]],
) -> BooleanAuthorityDerivation:
    relation = primary_boolean_relation(question) or "entails"
    required = tuple(
        sorted(
            token
            for token in _question_argument_tokens(
                question,
                _relation_surface_tokens(relation),
            )
            if token
        )
    ) or ("complete_proposition",)
    conclusion = _typed_derivation_conclusion(
        question,
        verdict,
        relation,
        required,
        premises,
        attestation,
    )
    contributions = _premise_contributions(premises, slot_support)
    identity = boolean_derivation_identity_payload(
        rule_id=SEMANTIC_EVIDENCE_SET_RULE,
        premise_refs=tuple(value.evidence_ref for value in premises),
        conclusion=conclusion,
        required_argument_tokens=required,
        support_mode="evidence_set",
        verifier_attestation=attestation,
        premise_contributions=contributions,
    )
    return BooleanAuthorityDerivation(
        derivation_id=boolean_derivation_id(identity),
        rule_id=SEMANTIC_EVIDENCE_SET_RULE,
        premise_refs=tuple(value.evidence_ref for value in premises),
        premise_evidence_ids=tuple(value.evidence_id for value in premises),
        conclusion=conclusion,
        required_argument_tokens=required,
        covered_argument_tokens=required,
        premise_contributions=contributions,
        support_mode="evidence_set",
        verifier_attestation=attestation,
    )


def _typed_derivation_conclusion(
    question: str,
    verdict: str,
    relation: str,
    required: tuple[str, ...],
    premises: tuple[BooleanEvidenceAuthority, ...],
    attestation: dict[str, Any],
) -> dict[str, Any]:
    fallback_object = (
        " ".join(required)
        if required != ("complete_proposition",)
        else question.strip()
    )
    actors = {value.actor for value in premises}
    scopes = {value.section_scope for value in premises}
    typed = attestation.get("typed_conclusion") or {}
    object_value = str(
        typed.get("object_surface") or typed.get("object_type") or fallback_object
    )
    return {
        "contract_id": str(typed.get("contract_id") or "typed_conclusion.v1"),
        "conclusion_id": str(typed.get("conclusion_id") or ""),
        "proposition_id": str(typed.get("proposition_id") or ""),
        "actor": str(typed.get("actor") or "")
        or (next(iter(actors)) if len(actors) == 1 else "current_source"),
        "predicate": str(typed.get("predicate") or relation),
        "relation": str(typed.get("predicate") or relation),
        "object": object_value,
        "object_role": str(typed.get("object_role") or "object"),
        "subject_surface": str(typed.get("subject_surface") or ""),
        "object_surface": str(typed.get("object_surface") or ""),
        "arguments": [object_value],
        "polarity": verdict,
        "qualifier": str(typed.get("qualifier") or proposition_qualifier(question)),
        "quantifier": str(typed.get("quantifier") or _closed_quantifier(question)),
        "modality": str(typed.get("modality") or "asserted"),
        "negated": bool(typed.get("negated")),
        "time_scope": str(typed.get("time_scope") or "unspecified"),
        "scope": str(typed.get("scope") or "")
        or (next(iter(scopes)) if len(scopes) == 1 else "document"),
        "section_scope": next(iter(scopes)) if len(scopes) == 1 else "document",
        "surface": str(typed.get("surface") or question.strip()),
    }


def _premise_contributions(
    premises: tuple[BooleanEvidenceAuthority, ...],
    slot_support: dict[str, tuple[str, ...]],
) -> tuple[dict[str, Any], ...]:
    return tuple(
        {
            "evidence_id": premise.evidence_id,
            "evidence_ref": premise.evidence_ref,
            "role": f"semantic_premise:{index}",
            "order": index,
            "argument_tokens": [],
            "proposition_fragment": premise.object,
            "supports_slot_ids": list(slot_support[premise.evidence_ref]),
            "binds_proposition_slots": [
                slot for slot, _value in premise.proposition_slot_bindings
            ],
            "proposition_slot_bindings": dict(premise.proposition_slot_bindings),
            "evidence_relation": premise.evidence_relation,
        }
        for index, premise in enumerate(premises, start=1)
    )
