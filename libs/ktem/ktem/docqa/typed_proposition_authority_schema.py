from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .boolean_authority_schema import BooleanAuthorityState

TYPED_PROPOSITION_AUTHORITY_CONTRACT = "typed_proposition_authority.v1"


def qasper_authority_domain(domain: str) -> bool:
    normalized = str(domain or "").strip().lower()
    return normalized == "qasper" or normalized.startswith("qasper_")


def planned_answer_type(request: Any) -> str:
    plan = getattr(request, "query_plan", None)
    value = getattr(plan, "answer_type", None) if plan is not None else None
    return str(value or getattr(request, "task_type", "") or "free_text").lower()


def has_composite_boolean_authority(decision: Any) -> bool:
    return any(
        str(result.get("authority_status") or "") == "composite_exact"
        for result in getattr(decision, "claim_results", ())
        if isinstance(result, dict)
    )


@dataclass(frozen=True)
class TypedPropositionAuthority:
    state: BooleanAuthorityState
    reason: str
    answer_type: str
    question: str
    candidate_answer: str
    required_slot_ids: tuple[str, ...]
    verified_slot_ids: tuple[str, ...] = ()
    slot_bindings: tuple[tuple[str, tuple[str, ...]], ...] = ()
    authority_atoms: tuple[dict[str, Any], ...] = ()
    authority_derivations: tuple[dict[str, Any], ...] = ()
    selected_derivation_id: str = ""
    claim_ids: tuple[str, ...] = ()
    canonical_answer_polarity: str = ""
    query_plan_state_version: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contract_id": TYPED_PROPOSITION_AUTHORITY_CONTRACT,
            "state": self.state,
            "reason": self.reason,
            "answer_type": self.answer_type,
            "question": self.question,
            "candidate_answer": self.candidate_answer,
            "claim_ids": list(self.claim_ids),
            "required_slot_ids": list(self.required_slot_ids),
            "verified_slot_ids": list(self.verified_slot_ids),
            "slot_bindings": {
                slot_id: list(evidence_ids)
                for slot_id, evidence_ids in self.slot_bindings
            },
            "authority_atoms": [deepcopy(atom) for atom in self.authority_atoms],
            "authority_derivations": [
                deepcopy(derivation) for derivation in self.authority_derivations
            ],
            "selected_derivation_id": self.selected_derivation_id,
            "canonical_answer_polarity": self.canonical_answer_polarity,
        }
        if self.query_plan_state_version is not None:
            payload["query_plan_state_version"] = self.query_plan_state_version
        return payload


def missing_authority(
    answer_type: str,
    question: str,
    answer: str,
    required_slot_ids: list[str],
    reason: str,
) -> dict[str, Any]:
    return TypedPropositionAuthority(
        state="missing",
        reason=reason,
        answer_type=answer_type,
        question=question,
        candidate_answer=answer,
        required_slot_ids=tuple(required_slot_ids),
    ).as_dict()


def exact_slot_set_contract(
    required_slot_ids: list[str] | tuple[str, ...],
    verified_support_slot_ids: list[str] | tuple[str, ...],
    slot_bindings: dict[str, Any],
) -> bool:
    """Check the one authoritative set of typed proposition slots."""

    required = {str(value).strip() for value in required_slot_ids if str(value).strip()}
    verified = {
        str(value).strip() for value in verified_support_slot_ids if str(value).strip()
    }
    bound = {str(value).strip() for value in slot_bindings if str(value).strip()}
    return required == verified == bound


def verified_authority(
    answer_type: str,
    question: str,
    answer: str,
    claim_results: list[dict[str, Any]],
    bindings: dict[str, tuple[str, ...]],
    atoms: list[dict[str, Any]],
    *,
    state: BooleanAuthorityState,
    reason: str,
    canonical_answer_polarity: str = "",
    query_plan_state_version: int,
    required_slot_ids: list[str] | tuple[str, ...] | None = None,
    authority_derivations: list[dict[str, Any]] | None = None,
    selected_derivation_id: str = "",
) -> dict[str, Any]:
    required = (
        list(required_slot_ids) if required_slot_ids is not None else list(bindings)
    )
    verified = list(bindings)
    if not exact_slot_set_contract(required, verified, bindings):
        raise ValueError(
            "Typed proposition authority requires exact required, verified, and "
            "bound slot sets."
        )
    return TypedPropositionAuthority(
        state=state,
        reason=reason,
        answer_type=answer_type,
        question=question,
        candidate_answer=answer,
        claim_ids=tuple(
            str(result.get("claim_id") or "")
            for result in claim_results
            if str(result.get("claim_id") or "")
        ),
        required_slot_ids=tuple(required),
        verified_slot_ids=tuple(verified),
        slot_bindings=tuple(bindings.items()),
        authority_atoms=tuple(atoms),
        authority_derivations=tuple(authority_derivations or ()),
        selected_derivation_id=selected_derivation_id,
        canonical_answer_polarity=canonical_answer_polarity,
        query_plan_state_version=query_plan_state_version,
    ).as_dict()
