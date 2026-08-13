from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_authoritative_conflict import authoritative_conflict_complete
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.typed_proposition_authority_schema import (
    TYPED_PROPOSITION_AUTHORITY_CONTRACT,
)


def typed_authority_audit(
    decision: dict[str, Any],
    bundle: dict[str, Any],
    slots: list[dict[str, Any]],
    verified_slots: list[dict[str, Any]],
    required_ids: list[str],
) -> dict[str, Any]:
    authority = decision.get("typed_authority")
    authority = authority if isinstance(authority, dict) else {}
    if authority.get("contract_id") != TYPED_PROPOSITION_AUTHORITY_CONTRACT:
        return _not_applicable()
    state = str(authority.get("state") or "")
    slot_ids = [str(slot.get("slot_id") or "") for slot in slots]
    bindings = authority.get("slot_bindings")
    bindings = bindings if isinstance(bindings, dict) else {}
    atoms = _records(authority.get("authority_atoms"))
    diagnostics = _atom_diagnostics(atoms, _records(bundle.get("items")))
    complete, reason = _projection_complete(
        state,
        decision,
        authority,
        slots,
        verified_slots,
        required_ids,
        slot_ids,
        bindings,
        atoms,
        diagnostics["status"],
    )
    return {
        "applicable": True,
        "complete": complete,
        "state": state,
        "reason": reason,
        "authority": authority,
        "required_slot_ids": slot_ids,
        "required_evidence_ids": required_ids,
        "atom_status": diagnostics["status"],
        "identity_status": diagnostics["identity_status"],
        "quote_grounding_status": diagnostics["quote_grounding_status"],
        "frame_status": diagnostics["frame_status"],
    }


def _not_applicable() -> dict[str, Any]:
    return {
        "applicable": False,
        "complete": False,
        "state": "",
        "reason": "typed_authority_projection_not_present",
        "authority": {},
    }


def _projection_complete(
    state: str,
    decision: dict[str, Any],
    authority: dict[str, Any],
    slots: list[dict[str, Any]],
    verified_slots: list[dict[str, Any]],
    required_ids: list[str],
    slot_ids: list[str],
    bindings: dict[str, Any],
    atoms: list[dict[str, Any]],
    atom_status: str,
) -> tuple[bool, str]:
    projected_required = _string_values(authority.get("required_slot_ids"))
    projected_verified = _string_values(authority.get("verified_slot_ids"))
    claim_results = _records(decision.get("claim_results"))
    if state == "missing":
        complete = _missing_complete(
            decision,
            projected_verified,
            bindings,
            atoms,
            claim_results,
        )
        return (
            complete,
            "coherent_missing_authority" if complete else "mixed_missing_state",
        )
    if state == "verified_conflict":
        conflict = decision.get("authoritative_conflict")
        conflict = conflict if isinstance(conflict, dict) else {}
        complete = bool(
            decision.get("status") == "verified_conflict"
            and authoritative_conflict_complete(conflict)
            and set(projected_required) == set(slot_ids)
            and set(projected_verified) == set(slot_ids)
            and atom_status == "bound"
            and len(verified_slots) == len(slots)
        )
        return (
            complete,
            "verified_conflict" if complete else "conflict_projection_mismatch",
        )
    complete = _support_complete(
        decision,
        slots,
        verified_slots,
        required_ids,
        slot_ids,
        projected_required,
        projected_verified,
        bindings,
        atoms,
        atom_status,
        claim_results,
    )
    return complete, "verified_support" if complete else "support_projection_mismatch"


def _missing_complete(
    decision: dict[str, Any],
    projected_verified: list[str],
    bindings: dict[str, Any],
    atoms: list[dict[str, Any]],
    claim_results: list[dict[str, Any]],
) -> bool:
    return bool(
        decision.get("status") in {"not_enough_evidence", "unknown", "unsupported"}
        and decision.get("action") in {"abstain", "retry", "revise"}
        and not decision.get("verified_citations")
        and not decision.get("authoritative_evidence_id")
        and not atoms
        and not projected_verified
        and not bindings
        and not any(
            str(result.get("authority_status") or "") in {"exact", "verified_support"}
            or str(result.get("verified_slot_state") or "")
            in {"verified_support", "verified_conflict"}
            for result in claim_results
        )
    )


def _support_complete(
    decision: dict[str, Any],
    slots: list[dict[str, Any]],
    verified_slots: list[dict[str, Any]],
    required_ids: list[str],
    slot_ids: list[str],
    projected_required: list[str],
    projected_verified: list[str],
    bindings: dict[str, Any],
    atoms: list[dict[str, Any]],
    atom_status: str,
    claim_results: list[dict[str, Any]],
) -> bool:
    bound_ids = {
        str(evidence_id)
        for values in bindings.values()
        for evidence_id in values or []
        if str(evidence_id)
    }
    return bool(
        decision.get("status") == "supported"
        and slots
        and len(verified_slots) == len(slots)
        and set(projected_required) == set(slot_ids)
        and set(projected_verified) == set(slot_ids)
        and set(bindings) == set(slot_ids)
        and set(required_ids) == bound_ids
        and atom_status == "bound"
        and atoms
        and all(
            result.get("status") == "supported"
            and result.get("authority_status") == "exact"
            and result.get("verified_slot_state") == "verified_support"
            and set(result.get("verified_support_slot_ids") or []) == set(slot_ids)
            for result in claim_results
        )
    )


def _atom_diagnostics(
    atoms: list[dict[str, Any]],
    items: list[dict[str, Any]],
) -> dict[str, str]:
    if not atoms:
        return _diagnostics("missing", "missing", "not_evaluated", "not_evaluated")
    for atom in atoms:
        evidence_id = str(atom.get("evidence_id") or "")
        item = _evidence_item_by_identity(items, evidence_id)
        evidence_ref = str(atom.get("evidence_ref") or "")
        if not evidence_id or item is None:
            return _diagnostics(
                "canonical_ref_identity_mismatch",
                "canonical_identity_unresolved",
                "not_evaluated",
                "not_evaluated",
            )
        if not _canonical_ref_bound(atom, evidence_id, evidence_ref):
            return _diagnostics(
                "canonical_ref_identity_mismatch",
                "canonical_ref_identity_mismatch",
                "not_evaluated",
                "not_evaluated",
            )
        if _quote_identity_status(item, atom) != "bound":
            return _diagnostics(
                "quote_semantic_grounding_failure",
                "bound",
                "quote_semantic_grounding_failure",
                "not_evaluated",
            )
        if not _authority_frame_complete(atom):
            return _diagnostics(
                "authority_frame_incomplete",
                "bound",
                "bound",
                "incomplete",
            )
    return _diagnostics("bound", "bound", "bound", "complete")


def _diagnostics(status: str, identity: str, quote: str, frame: str) -> dict[str, str]:
    return {
        "status": status,
        "identity_status": identity,
        "quote_grounding_status": quote,
        "frame_status": frame,
    }


def _canonical_ref_bound(
    atom: dict[str, Any], evidence_id: str, evidence_ref: str
) -> bool:
    return bool(
        evidence_ref
        and evidence_ref == str(atom.get("span_id") or "")
        and evidence_ref.startswith(f"{evidence_id}#quote:")
    )


def _quote_identity_status(item: dict[str, Any], atom: dict[str, Any]) -> str:
    quote = str(atom.get("quote") or "")
    start = atom.get("span_start")
    end = atom.get("span_end")
    text = "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )
    if text.count(quote) != 1 or not isinstance(start, int) or not isinstance(end, int):
        return "mismatch"
    return "bound" if text[start:end] == quote else "mismatch"


def _authority_frame_complete(atom: dict[str, Any]) -> bool:
    return bool(
        str(atom.get("actor") or "") not in {"", "unknown"}
        and str(atom.get("relation") or atom.get("predicate") or "")
        and str(atom.get("object") or "")
        and (atom.get("arguments") or [])
        and str(atom.get("qualifier") or "")
        and str(atom.get("quantifier") or "")
        and str(atom.get("scope") or atom.get("section_scope") or "")
        not in {"", "unknown", "future_work"}
    )


def _evidence_item_by_identity(
    items: list[dict[str, Any]], evidence_id: str
) -> dict[str, Any] | None:
    matches = []
    for item in items:
        try:
            if identity_of(item).key == evidence_id:
                matches.append(item)
        except ValueError:
            continue
    return matches[0] if len(matches) == 1 else None


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
