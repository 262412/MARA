from __future__ import annotations

from copy import deepcopy
from typing import Any

from .qasper_semantic_trace_projection import (
    semantic_proposition_authority_trace_fields,
    semantic_proposition_verifier_trace_fields,
)


def answerability_trace(
    prediction: dict[str, Any],
    *,
    engine_answer: str,
    engine_label: str,
    scored_answer: str,
    scored_label: str,
    authority: dict[str, Any],
    typed_authority: dict[str, Any],
    action: str,
    projection_present: bool,
    semantic_rewrite: bool,
    invalid_typed_label: bool,
    typed_label_required: bool,
    runtime_boolean_authority_applicable: bool,
    runtime_boolean_polarity_authority_required: bool,
    runtime_boolean_conflict_authority_required: bool,
    runtime_boolean_projection_required: bool,
    runtime_typed_authority_applicable: bool,
    runtime_typed_authority_complete: bool,
) -> dict[str, Any]:
    complete = bool(authority["complete"])
    typed_state = str(typed_authority.get("state") or "")
    typed_verified = bool(
        runtime_typed_authority_applicable
        and runtime_typed_authority_complete
        and typed_state in {"verified_support", "verified_conflict"}
    )
    conflict_complete = bool(
        complete and authority.get("authority_kind") == "authoritative_conflict"
    )
    authority_required = bool(
        runtime_boolean_polarity_authority_required
        or runtime_boolean_conflict_authority_required
    )
    failure_kind = runtime_authority_failure(
        authority,
        complete=complete,
        authority_required=authority_required,
        projection_required=runtime_boolean_projection_required,
        projection_present=projection_present,
    )
    if runtime_typed_authority_applicable and not runtime_typed_authority_complete:
        failure_kind = str(typed_authority.get("reason") or "authority_missing")
    authority_fields = (
        typed_authority_trace_fields(
            typed_authority,
            authority,
            authority_established=typed_verified,
        )
        if runtime_typed_authority_applicable
        else authority_trace_fields(authority, complete=complete)
    )
    values = {
        "engine_answer": engine_answer,
        "engine_label": engine_label,
        "scored_answer": scored_answer,
        "scored_label": scored_label,
        "action": action,
        "semantic_rewrite": semantic_rewrite,
        "invalid_typed_label": invalid_typed_label,
        "typed_label_required": typed_label_required,
        "boolean_applicable": runtime_boolean_authority_applicable,
        "polarity_required": runtime_boolean_polarity_authority_required,
        "conflict_required": runtime_boolean_conflict_authority_required,
        "projection_required": runtime_boolean_projection_required,
        "projection_present": projection_present,
        "typed_applicable": runtime_typed_authority_applicable,
        "typed_complete": runtime_typed_authority_complete,
        "authority_kind": authority.get("authority_kind", ""),
    }
    return _trace_payload(
        prediction,
        typed_authority,
        values,
        complete=complete,
        conflict_complete=conflict_complete,
        failure_kind=failure_kind,
        authority_fields=authority_fields,
    )


def _trace_payload(
    prediction: dict[str, Any],
    typed_authority: dict[str, Any],
    values: dict[str, Any],
    *,
    complete: bool,
    conflict_complete: bool,
    failure_kind: str,
    authority_fields: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_runtime_authority_audit.v1",
        "status": (
            "violation" if str(values["action"]).startswith("hard_violation") else "ok"
        ),
        "verdict": values["engine_label"] if complete else "insufficient_evidence",
        "raw_verifier_verdict": runtime_verifier_verdict(
            values["engine_label"],
            complete=complete,
            conflict_complete=conflict_complete,
        ),
        "action": values["action"],
        "reason": authority_reason(
            typed_authority,
            complete=complete,
            conflict_complete=conflict_complete,
            authority_required=bool(
                values["polarity_required"] or values["conflict_required"]
            ),
            authority_applicable=values["boolean_applicable"],
            projection_required=values["projection_required"],
            projection_present=values["projection_present"],
            typed_applicable=values["typed_applicable"],
            typed_complete=values["typed_complete"],
        ),
        "primary_answer": values["engine_answer"],
        "adjudicated_polarity": "" if conflict_complete else values["engine_label"],
        "final_post_contract_answer": values["scored_answer"],
        "post_contract_answer": values["scored_answer"],
        "engine_terminal_answer": values["engine_answer"],
        "engine_semantic_label": values["engine_label"],
        "scored_semantic_label": values["scored_label"],
        "contract_action": values["action"],
        "contract_semantic_rewrite": values["semantic_rewrite"],
        "invalid_typed_label": values["invalid_typed_label"],
        "typed_label_required": values["typed_label_required"],
        "runtime_projection_present": values["projection_present"],
        "runtime_boolean_authority_applicable": values["boolean_applicable"],
        "runtime_boolean_polarity_authority_required": values["polarity_required"],
        "runtime_boolean_conflict_authority_required": values["conflict_required"],
        "runtime_boolean_projection_required": values["projection_required"],
        "runtime_typed_authority_applicable": values["typed_applicable"],
        "runtime_typed_authority_complete": values["typed_complete"],
        "runtime_typed_authority_state": typed_authority["state"],
        "runtime_typed_authority_reason": typed_authority["reason"],
        "runtime_typed_authority_atom_status": typed_authority.get("atom_status", ""),
        "runtime_typed_authority_identity_status": typed_authority.get(
            "identity_status", ""
        ),
        "runtime_typed_authority_quote_grounding_status": typed_authority.get(
            "quote_grounding_status", ""
        ),
        "runtime_typed_authority_frame_status": typed_authority.get("frame_status", ""),
        **typed_derivation_trace_fields(typed_authority),
        "runtime_boolean_authority_kind": values["authority_kind"],
        "runtime_authority_failure_kind": failure_kind,
        "post_engine_answerability_llm_call_count": 0,
        "runtime_semantic_recovery_transition": _latest_recovery_transition(prediction),
        **semantic_proposition_authority_trace_fields(prediction),
        **semantic_proposition_verifier_trace_fields(prediction),
        **authority_fields,
        "engine_verify_decision": deepcopy(
            prediction.get("engine_verify_decision") or {}
        ),
    }


def _latest_recovery_transition(prediction: dict[str, Any]) -> dict[str, Any]:
    for event in reversed(prediction.get("controller_trace") or []):
        if not isinstance(event, dict):
            continue
        transition = event.get("recovery_transition")
        if isinstance(transition, dict):
            return deepcopy(transition)
    return {}


def typed_derivation_trace_fields(
    typed_authority: dict[str, Any],
) -> dict[str, Any]:
    return {
        "runtime_typed_authority_kind": typed_authority.get("authority_kind", ""),
        "runtime_typed_authority_derivation_status": typed_authority.get(
            "derivation_status", ""
        ),
        "runtime_typed_authority_derivation_count": typed_authority.get(
            "derivation_count", 0
        ),
        "runtime_typed_authority_selected_derivation_id": typed_authority.get(
            "selected_derivation_id", ""
        ),
        "runtime_typed_authority_premise_refs": list(
            typed_authority.get("derivation_premise_refs") or []
        ),
        "runtime_typed_authority_premise_evidence_ids": list(
            typed_authority.get("derivation_premise_evidence_ids") or []
        ),
        "runtime_typed_authority_slot_ref_bindings": deepcopy(
            typed_authority.get("slot_ref_bindings") or {}
        ),
    }


def runtime_authority_failure(
    authority: dict[str, Any],
    *,
    complete: bool,
    authority_required: bool,
    projection_required: bool,
    projection_present: bool,
) -> str:
    if projection_required and not projection_present:
        return "authority_missing"
    if complete or not authority_required:
        return ""
    return str(authority.get("failure_kind") or "authority_missing")


def runtime_verifier_verdict(
    engine_label: str,
    *,
    complete: bool,
    conflict_complete: bool,
) -> str:
    if conflict_complete:
        return "conflict_complete"
    return (
        f"{engine_label}_complete" if complete and engine_label in {"yes", "no"} else ""
    )


def authority_reason(
    typed_authority: dict[str, Any],
    *,
    complete: bool,
    conflict_complete: bool,
    authority_required: bool,
    authority_applicable: bool,
    projection_required: bool,
    projection_present: bool,
    typed_applicable: bool,
    typed_complete: bool,
) -> str:
    if typed_applicable and not typed_complete:
        return str(typed_authority.get("reason") or "runtime_authority_missing")
    if conflict_complete:
        return "runtime_authoritative_conflict"
    if complete:
        return "runtime_authority_verified"
    if projection_required and not projection_present:
        return "runtime_projection_missing"
    if not authority_required:
        return "runtime_safe_abstention"
    if authority_applicable:
        return "runtime_authority_missing_or_inconsistent"
    return "runtime_boolean_authority_not_applicable"


def authority_trace_fields(
    authority: dict[str, Any], *, complete: bool
) -> dict[str, Any]:
    slot_ids = authority["required_slot_ids"]
    evidence_ids = authority["required_evidence_ids"]
    return _common_authority_fields(
        slot_ids,
        evidence_ids,
        complete=complete,
        quote=str(authority["quote"]),
        evidence_ref=str(authority["evidence_ref"]),
        evidence_id=str(authority["evidence_id"]),
        quote_status=str(authority["quote_ref_validation_status"]),
        conflict=authority.get("authoritative_conflict") or {},
    )


def typed_authority_trace_fields(
    typed_authority: dict[str, Any],
    boolean_authority: dict[str, Any],
    *,
    authority_established: bool,
) -> dict[str, Any]:
    projection = typed_authority.get("authority")
    projection = projection if isinstance(projection, dict) else {}
    atoms = [
        atom
        for atom in projection.get("authority_atoms") or []
        if isinstance(atom, dict)
    ]
    first = atoms[0] if atoms else {}
    derived = typed_authority.get("authority_kind") in {
        "composite",
        "semantic_evidence_set",
    }
    return _common_authority_fields(
        list(typed_authority.get("required_slot_ids") or []),
        list(typed_authority.get("required_evidence_ids") or []),
        complete=authority_established,
        quote="" if derived else str(first.get("quote") or ""),
        evidence_ref="" if derived else str(first.get("evidence_ref") or ""),
        evidence_id="" if derived else str(first.get("evidence_id") or ""),
        quote_status=str(typed_authority.get("atom_status") or ""),
        conflict=boolean_authority.get("authoritative_conflict") or {},
    )


def _common_authority_fields(
    slot_ids: list[str],
    evidence_ids: list[str],
    *,
    complete: bool,
    quote: str,
    evidence_ref: str,
    evidence_id: str,
    quote_status: str,
    conflict: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_quote": quote,
        "evidence_ref": evidence_ref,
        "authoritative_quote_evidence_id": evidence_id,
        "quote_ref_validation_status": "bound" if complete else quote_status,
        "quote_grounded": str(complete).lower(),
        "quote_supports_relation": str(complete).lower(),
        "boolean_scope_valid": str(complete).lower(),
        "verifier_required_slot_ids": ",".join(slot_ids),
        "verifier_required_slot_count": str(len(slot_ids)),
        "verifier_required_slot_authority_count": str(len(slot_ids) if complete else 0),
        "verifier_required_evidence_ids": ",".join(evidence_ids),
        "verifier_missing_required_slot_ids": "" if complete else ",".join(slot_ids),
        "verifier_missing_required_evidence_ids": (
            "" if complete else ",".join(evidence_ids)
        ),
        "verifier_required_authority_status": (
            "complete" if complete else "missing_required_evidence"
        ),
        "verifier_required_evidence_coverage": "1.000000" if complete else "0.000000",
        "final_support_evidence_ids": evidence_ids if complete else [],
        "authoritative_conflict": deepcopy(conflict),
    }
