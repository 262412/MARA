from __future__ import annotations

import hashlib
import json
from typing import Any

from .boolean_authority_derivation_support import _strings
from .boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from .question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    applicable_proposition_evidence_slots,
    build_question_proposition,
    not_applicable_proposition_evidence_slots,
    proposition_evidence_bindings,
    typed_conclusion,
)
from .semantic_entailment_audit import semantic_entailment_audit_validation_reason


def _semantic_header_complete(derivation: dict[str, Any]) -> bool:
    attestation = derivation.get("verifier_attestation")
    required_slots, not_applicable_slots = _attested_proposition_slots(attestation)
    return bool(
        derivation.get("support_mode") == "evidence_set"
        and isinstance(attestation, dict)
        and attestation.get("contract_id") == GROUNDED_SEMANTIC_VERIFIER_CONTRACT
        and attestation.get("verdict_contract_id")
        == SEMANTIC_PROPOSITION_VERDICT_CONTRACT
        and str(attestation.get("model") or "")
        and attestation.get("verdict") in {"yes", "no"}
        and bool(attestation.get("complete_proposition"))
        and attestation.get("scope_basis")
        in {
            "explicit_current_actor",
            "explicit_prior_work_actor",
            "named_question_subject",
        }
        and attestation.get("jointly_complete") is True
        and attestation.get("each_premise_required") is True
        and attestation.get("proof_mode")
        in {"atomic_semantic", "composite_conjunction"}
        and isinstance(attestation.get("entailment_audit"), dict)
        and attestation.get("evidence_relation")
        in {"proposition_support", "explicit_contradiction"}
        and attestation.get("required_proposition_slots") == required_slots
        and attestation.get("not_applicable_proposition_slots") == not_applicable_slots
        and isinstance(attestation.get("proposition_slot_bindings"), dict)
        and isinstance(attestation.get("proposition_slot_evidence_refs"), dict)
        and isinstance(attestation.get("proposition_binding_evidence_set_refs"), list)
        and bool(str(attestation.get("proposition_evidence_set_digest") or ""))
    )


def _semantic_evidence_set_status(
    derivation: dict[str, Any],
    contributions: list[dict[str, Any]],
    *,
    atom_by_ref: dict[str, dict[str, Any]],
    conclusion: dict[str, Any],
    question: str,
) -> str:
    attestation = derivation.get("verifier_attestation")
    attestation = attestation if isinstance(attestation, dict) else {}
    premise_refs = _strings(derivation.get("premise_refs"))
    if int(attestation.get("premise_count") or 0) != len(premise_refs) or str(
        attestation.get("verdict") or ""
    ) != str(conclusion.get("polarity") or ""):
        return "semantic_attestation_mismatch"
    (
        proposition,
        applicable_slots,
        not_applicable_slots,
        canonical_bindings,
    ) = _semantic_status_context(question)
    evidence_relation = (
        "proposition_support"
        if str(conclusion.get("polarity") or "") == "yes"
        else "explicit_contradiction"
    )
    if not _semantic_attestation_bindings_match(
        attestation,
        evidence_relation=evidence_relation,
        canonical_bindings=canonical_bindings,
        applicable_slots=applicable_slots,
        not_applicable_slots=not_applicable_slots,
    ):
        return "semantic_proposition_binding_attestation_mismatch"
    contribution_by_ref = {
        str(value.get("evidence_ref") or ""): value for value in contributions
    }
    projections, projection_reason = _semantic_premise_projections(
        premise_refs,
        contribution_by_ref,
        atom_by_ref,
        conclusion=conclusion,
        canonical_bindings=canonical_bindings,
        applicable_slots=applicable_slots,
        evidence_relation=evidence_relation,
    )
    if projection_reason:
        return projection_reason
    projection_state, projection_reason = _semantic_projection_state(
        projections,
        premise_refs=premise_refs,
        canonical_bindings=canonical_bindings,
        applicable_slots=applicable_slots,
        not_applicable_slots=not_applicable_slots,
        evidence_relation=evidence_relation,
        attestation=attestation,
    )
    if projection_reason:
        return projection_reason
    audit_reason = semantic_entailment_audit_validation_reason(
        question,
        str(conclusion.get("polarity") or ""),
        projection_state["audit_premises"],
        attestation.get("entailment_audit"),
        proof_mode=str(attestation.get("proof_mode") or ""),
        proposition=proposition,
        conclusion=typed_conclusion(
            proposition,
            str(conclusion.get("polarity") or ""),
        ),
        release_mode=bool(attestation.get("release_mode")),
    )
    if audit_reason:
        return audit_reason
    return (
        "bound"
        if projection_state["supported_slots"]
        == set(_strings(attestation.get("required_slot_ids")))
        else "semantic_slot_coverage_mismatch"
    )


def _semantic_attestation_bindings_match(
    attestation: dict[str, Any],
    *,
    evidence_relation: str,
    canonical_bindings: dict[str, str],
    applicable_slots: tuple[str, ...],
    not_applicable_slots: tuple[str, ...],
) -> bool:
    return bool(
        attestation.get("evidence_relation") == evidence_relation
        and dict(attestation.get("proposition_slot_bindings") or {})
        == canonical_bindings
        and attestation.get("required_proposition_slots") == list(applicable_slots)
        and attestation.get("not_applicable_proposition_slots")
        == list(not_applicable_slots)
    )


def _semantic_status_context(
    question: str,
) -> tuple[Any, tuple[str, ...], tuple[str, ...], dict[str, str]]:
    proposition = build_question_proposition(question)
    applicable_slots = applicable_proposition_evidence_slots(proposition)
    not_applicable_slots = not_applicable_proposition_evidence_slots(proposition)
    all_bindings = proposition_evidence_bindings(proposition)
    canonical_bindings = {slot: all_bindings[slot] for slot in applicable_slots}
    return proposition, applicable_slots, not_applicable_slots, canonical_bindings


def _semantic_premise_projections(
    premise_refs: list[str],
    contribution_by_ref: dict[str, dict[str, Any]],
    atom_by_ref: dict[str, dict[str, Any]],
    *,
    conclusion: dict[str, Any],
    canonical_bindings: dict[str, str],
    applicable_slots: tuple[str, ...],
    evidence_relation: str,
) -> tuple[list[dict[str, Any]], str]:
    projections: list[dict[str, Any]] = []
    for index, reference in enumerate(premise_refs, start=1):
        projection, reason = _semantic_premise_projection(
            index,
            contribution_by_ref[reference],
            atom_by_ref[reference],
            conclusion=conclusion,
            canonical_bindings=canonical_bindings,
            applicable_slots=set(applicable_slots),
            evidence_relation=evidence_relation,
        )
        if projection is None:
            return [], reason
        projections.append(projection)
    return projections, ""


def _semantic_premise_projection(
    index: int,
    contribution: dict[str, Any],
    atom: dict[str, Any],
    *,
    conclusion: dict[str, Any],
    canonical_bindings: dict[str, str],
    applicable_slots: set[str],
    evidence_relation: str,
) -> tuple[dict[str, Any] | None, str]:
    slot_ids = set(_strings(contribution.get("supports_slot_ids")))
    declared_proposition_slots = _strings(contribution.get("binds_proposition_slots"))
    proposition_slots = set(declared_proposition_slots)
    bindings = dict(contribution.get("proposition_slot_bindings") or {})
    expected = {slot: canonical_bindings[slot] for slot in proposition_slots}
    fragment = str(contribution.get("proposition_fragment") or "").strip()
    invalid = bool(
        contribution.get("role") != f"semantic_premise:{index}"
        or int(contribution.get("order") or 0) != index
        or str(atom.get("relation") or atom.get("predicate") or "")
        != "semantic_premise"
        or not fragment
        or str(atom.get("object") or "") != fragment
        or str(atom.get("polarity") or "") != str(conclusion.get("polarity") or "")
        or str(atom.get("reason") or "") != "semantic_evidence_set_premise"
        or not slot_ids
        or not proposition_slots
        or not proposition_slots <= applicable_slots
        or bindings != expected
        or dict(atom.get("proposition_slot_bindings") or {}) != expected
        or contribution.get("evidence_relation") != evidence_relation
        or atom.get("evidence_relation") != evidence_relation
    )
    if invalid:
        return None, "semantic_premise_projection_mismatch"
    return {
        "reference": str(contribution.get("evidence_ref") or ""),
        "supported_slots": slot_ids,
        "proposition_slots": proposition_slots,
        "normalized_fragment": " ".join(fragment.casefold().split()),
        "audit_premise": {
            "evidence_id": str(atom.get("evidence_id") or ""),
            "quote": str(atom.get("quote") or ""),
            "proposition_fragment": fragment,
            "supports_slot_ids": sorted(slot_ids),
            "binds_proposition_slots": declared_proposition_slots,
            "proposition_slot_bindings": bindings,
            "evidence_relation": evidence_relation,
        },
    }, ""


def _semantic_projection_state(
    projections: list[dict[str, Any]],
    *,
    premise_refs: list[str],
    canonical_bindings: dict[str, str],
    applicable_slots: tuple[str, ...],
    not_applicable_slots: tuple[str, ...],
    evidence_relation: str,
    attestation: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    fragments = [value["normalized_fragment"] for value in projections]
    if len(fragments) != len(set(fragments)):
        return {}, "semantic_premise_fragment_duplicate"
    slot_refs = {
        slot: sorted(
            value["reference"]
            for value in projections
            if slot in value["proposition_slots"]
        )
        for slot in applicable_slots
    }
    payload = {
        "evidence_relation": evidence_relation,
        "proposition_slot_bindings": canonical_bindings,
        "proposition_slot_evidence_refs": slot_refs,
        "proposition_binding_evidence_set_refs": sorted(premise_refs),
        "not_applicable_proposition_slots": list(not_applicable_slots),
    }
    digest_value = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    bound_slots = set().union(*(value["proposition_slots"] for value in projections))
    if (
        bound_slots != set(applicable_slots)
        or dict(attestation.get("proposition_slot_evidence_refs") or {}) != slot_refs
        or list(attestation.get("proposition_binding_evidence_set_refs") or [])
        != sorted(premise_refs)
        or attestation.get("proposition_evidence_set_digest") != digest_value
    ):
        return {}, "semantic_proposition_evidence_set_binding_mismatch"
    return {
        "supported_slots": set().union(
            *(value["supported_slots"] for value in projections)
        ),
        "audit_premises": [value["audit_premise"] for value in projections],
    }, ""


def _attested_proposition_slots(attestation: Any) -> tuple[list[str], list[str]]:
    if not isinstance(attestation, dict):
        return [], []
    proposition = attestation.get("question_proposition")
    quantifier = (
        str(proposition.get("quantifier") or "")
        if isinstance(proposition, dict)
        else ""
    )
    not_applicable = ["quantifier"] if quantifier == "none" else []
    required = [
        slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot not in not_applicable
    ]
    return required, not_applicable
