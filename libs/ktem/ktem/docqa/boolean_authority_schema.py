from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

BooleanAuthorityState: TypeAlias = Literal[
    "missing",
    "retrieved_unverified",
    "verified_support",
    "verified_conflict",
]
BOOLEAN_AUTHORITY_STATES: tuple[BooleanAuthorityState, ...] = (
    "missing",
    "retrieved_unverified",
    "verified_support",
    "verified_conflict",
)
BOOLEAN_AUTHORITY_DERIVATION_CONTRACT = "boolean_authority_derivation.v1"
ARGUMENT_CONJUNCTION_RULE = "same_source_argument_conjunction.v1"
ENTITY_TYPE_JOIN_RULE = "same_source_entity_type_join.v1"
SEMANTIC_EVIDENCE_SET_RULE = "grounded_semantic_evidence_set_entailment.v2"
SEMANTIC_PROPOSITION_VERDICT_CONTRACT = "semantic_proposition_verdict.v2"
GROUNDED_SEMANTIC_VERIFIER_CONTRACT = "grounded_semantic_verifier.v1"
SEMANTIC_ENTAILMENT_AUDIT_CONTRACT = "semantic_entailment_audit.v1"
GROUNDED_SEMANTIC_AUDITOR_CONTRACT = "grounded_semantic_auditor.v1"


def candidate_authority_state(relevant: bool) -> BooleanAuthorityState:
    return "retrieved_unverified" if relevant else "missing"


@dataclass(frozen=True)
class BooleanEvidenceAuthority:
    evidence_id: str
    evidence_ref: str
    span_id: str
    quote: str
    span_start: int
    span_end: int
    canonical_start: int | None
    canonical_end: int | None
    actor: str
    section_scope: str
    relation: str
    object: str
    quantifier: str
    polarity: str
    reason: str
    qualifier: str = "none"
    source_id: str = ""
    page_label: str = ""

    @property
    def predicate(self) -> str:
        return self.relation

    @property
    def scope(self) -> str:
        return self.section_scope

    @property
    def arguments(self) -> tuple[str, ...]:
        return (self.object,) if self.object else ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_ref": self.evidence_ref,
            "span_id": self.span_id,
            "quote": self.quote,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "canonical_start": self.canonical_start,
            "canonical_end": self.canonical_end,
            "actor": self.actor,
            "predicate": self.predicate,
            "section_scope": self.section_scope,
            "scope": self.scope,
            "relation": self.relation,
            "object": self.object,
            "arguments": list(self.arguments),
            "quantifier": self.quantifier,
            "polarity": self.polarity,
            "qualifier": self.qualifier,
            "reason": self.reason,
            "source_id": self.source_id,
            "page_label": self.page_label,
        }


@dataclass(frozen=True)
class BooleanAuthorityDerivation:
    """One verified proof alternative whose premises are jointly required."""

    derivation_id: str
    rule_id: str
    premise_refs: tuple[str, ...]
    premise_evidence_ids: tuple[str, ...]
    conclusion: dict[str, Any]
    required_argument_tokens: tuple[str, ...]
    covered_argument_tokens: tuple[str, ...]
    premise_contributions: tuple[dict[str, Any], ...]
    bindings: tuple[tuple[str, str], ...] = ()
    premise_mode: str = "all_required"
    semantics: str = "open_world"
    status: str = "verified"
    support_mode: str = ""
    verifier_attestation: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "contract_id": BOOLEAN_AUTHORITY_DERIVATION_CONTRACT,
            "derivation_id": self.derivation_id,
            "rule_id": self.rule_id,
            "premise_mode": self.premise_mode,
            "semantics": self.semantics,
            "status": self.status,
            "premise_refs": list(self.premise_refs),
            "premise_evidence_ids": list(self.premise_evidence_ids),
            "premise_contributions": [
                deepcopy(value) for value in self.premise_contributions
            ],
            "conclusion": deepcopy(self.conclusion),
            "required_argument_tokens": list(self.required_argument_tokens),
            "covered_argument_tokens": list(self.covered_argument_tokens),
            "bindings": dict(self.bindings),
        }
        if self.support_mode:
            payload["support_mode"] = self.support_mode
        if self.verifier_attestation:
            payload["verifier_attestation"] = deepcopy(self.verifier_attestation)
        return payload


@dataclass(frozen=True)
class BooleanClaimAuthority:
    claim: str
    status: str
    input_answer_polarity: str
    canonical_answer_polarity: str
    semantic_correction_applied: bool
    supporting: tuple[BooleanEvidenceAuthority, ...] = ()
    contradicting: tuple[BooleanEvidenceAuthority, ...] = ()
    reason: str = ""
    authoritative_conflict: dict[str, Any] | None = None
    authority_derivations: tuple[BooleanAuthorityDerivation, ...] = ()
    selected_derivation_id: str = ""


def supported_boolean_claim(
    prompt: str,
    input_polarity: str,
    canonical_polarity: str,
    supporting: tuple[BooleanEvidenceAuthority, ...],
    *,
    contradicting: tuple[BooleanEvidenceAuthority, ...] = (),
    reason: str,
    authority_derivations: tuple[BooleanAuthorityDerivation, ...] = (),
    selected_derivation_id: str = "",
) -> BooleanClaimAuthority:
    return BooleanClaimAuthority(
        claim=f"{canonical_polarity}: {prompt}",
        status="supported",
        input_answer_polarity=input_polarity,
        canonical_answer_polarity=canonical_polarity,
        semantic_correction_applied=input_polarity != canonical_polarity,
        supporting=supporting,
        contradicting=contradicting,
        reason=reason,
        authority_derivations=authority_derivations,
        selected_derivation_id=selected_derivation_id,
    )
