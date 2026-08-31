from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

FROZEN_CANONICAL_PROJECTION_CONTRACT = "frozen_canonical_proposition_projection.v1"


@dataclass(frozen=True, slots=True)
class FrozenCanonicalPropositionEvidencePlan:
    """Validated, immutable-by-convention semantic projection for one plan."""

    plan_id: str
    plan_digest: str
    polarity_relation: str
    proof_mode: str
    span_refs: tuple[str, ...]
    slot_refs: dict[str, tuple[str, ...]]
    required_slots: tuple[str, ...]
    required_object_tokens: tuple[str, ...]
    covered_object_tokens: tuple[str, ...]
    event_binding_id: str
    event_subplans: tuple[dict[str, Any], ...]
    comparison_relation: Any
    premises: tuple[dict[str, Any], ...]
    slot_evidence: dict[str, dict[str, dict[str, Any]]]
    audit_slot_evidence: dict[str, dict[str, dict[str, Any]]]
    covered_tokens_by_ref: dict[str, tuple[str, ...]]
    semantic_alignment_by_ref: dict[str, dict[str, Any]]

    @property
    def evidence_relations(self) -> dict[str, str]:
        return {ref: self.polarity_relation for ref in self.span_refs}

    @property
    def proposition_slot_bindings(self) -> dict[str, str]:
        return {
            slot: str(value.get("binding") or "")
            for slot, value in self._binding_values.items()
        }

    @property
    def _binding_values(self) -> dict[str, dict[str, str]]:
        values: dict[str, dict[str, str]] = {}
        for premise in self.premises:
            for slot, binding in dict(
                premise.get("proposition_slot_bindings") or {}
            ).items():
                values.setdefault(str(slot), {"binding": str(binding)})
        return values

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": FROZEN_CANONICAL_PROJECTION_CONTRACT,
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "polarity_relation": self.polarity_relation,
            "proof_mode": self.proof_mode,
            "span_refs": list(self.span_refs),
            "slot_refs": {slot: list(refs) for slot, refs in self.slot_refs.items()},
            "required_slots": list(self.required_slots),
            "required_object_tokens": list(self.required_object_tokens),
            "covered_object_tokens": list(self.covered_object_tokens),
            "event_binding_id": self.event_binding_id,
            "event_subplans": deepcopy(list(self.event_subplans)),
            "comparison_relation": deepcopy(self.comparison_relation),
            "premises": deepcopy(list(self.premises)),
            "slot_evidence": deepcopy(self.slot_evidence),
            "audit_slot_evidence": deepcopy(self.audit_slot_evidence),
            "covered_tokens_by_ref": {
                ref: list(tokens) for ref, tokens in self.covered_tokens_by_ref.items()
            },
            "semantic_alignment_by_ref": deepcopy(self.semantic_alignment_by_ref),
        }
