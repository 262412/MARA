from __future__ import annotations

from typing import Any

from .verification_schema import VerifyDecision


def typed_slot_bindings(decision: VerifyDecision) -> dict[str, tuple[str, ...]]:
    authority = decision.typed_authority
    if not isinstance(authority, dict):
        return {}
    payload = authority.get("slot_bindings")
    if not isinstance(payload, dict):
        return {}
    return {
        str(slot_id): tuple(
            str(value).strip() for value in values or [] if str(value).strip()
        )
        for slot_id, values in payload.items()
        if str(slot_id).strip() and isinstance(values, (list, tuple))
    }


def boolean_slot_bindings(
    request: Any,
    required_slots: list[Any],
    atoms: list[dict[str, Any]],
    derivations: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, tuple[str, ...]], list[dict[str, Any]]] | tuple[None, None]:
    """Bind exact atoms to pre-bound slots without inventing slot coverage."""

    atom_by_id: dict[str, list[dict[str, Any]]] = {}
    for atom in atoms:
        evidence_id = str(atom.get("evidence_id") or "")
        if evidence_id:
            atom_by_id.setdefault(evidence_id, []).append(atom)
    if not atom_by_id:
        return None, None

    plan = getattr(request, "query_plan", None)
    constraints = getattr(plan, "constraints", {}) if plan is not None else {}
    requires_distinct = bool(
        isinstance(constraints, dict) and constraints.get("requires_distinct_evidence")
    )
    proposition_slots = [
        slot for slot in required_slots if _is_boolean_proposition_slot(slot)
    ]
    side_slots = [
        slot for slot in required_slots if not _is_boolean_proposition_slot(slot)
    ]
    bindings: dict[str, tuple[str, ...]] = {}
    selected_ids: list[str] = []
    proof_ids = _selected_proof_ids(derivations or [], atoms)
    if derivations and not proof_ids:
        return None, None

    if not side_slots and len(proposition_slots) == 1:
        slot = proposition_slots[0]
        proposition_selection = proof_ids or (next(iter(atom_by_id)),)
        bindings[str(slot.slot_id)] = proposition_selection
        selected_ids.extend(proposition_selection)

    side_binding = _bind_side_slots(side_slots, atom_by_id, requires_distinct)
    if side_binding is None:
        return None, None
    side_bindings, side_ids = side_binding
    bindings.update(side_bindings)
    selected_ids.extend(side_ids)

    proposition_slots_to_bind = (
        proposition_slots if side_slots or len(proposition_slots) != 1 else []
    )
    for slot in proposition_slots_to_bind:
        if proof_ids:
            bindings[str(slot.slot_id)] = proof_ids
            selected_ids.extend(proof_ids)
            continue
        candidate_ids = _slot_atom_ids(slot, atom_by_id)
        if not candidate_ids:
            return None, None
        slot_selection: tuple[str, ...]
        if side_slots:
            selected_side_ids = tuple(dict.fromkeys(selected_ids))
            if any(
                evidence_id not in candidate_ids for evidence_id in selected_side_ids
            ):
                return None, None
            slot_selection = selected_side_ids
        else:
            slot_selection = (candidate_ids[0],)
        bindings[str(slot.slot_id)] = slot_selection
        selected_ids.extend(slot_selection)

    if {str(slot.slot_id) for slot in required_slots} != set(bindings):
        return None, None
    selected_id_set = set(selected_ids)
    selected_atoms = [
        atom for atom in atoms if str(atom.get("evidence_id") or "") in selected_id_set
    ]
    if not selected_atoms:
        return None, None
    return bindings, selected_atoms


def _selected_proof_ids(
    derivations: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
) -> tuple[str, ...]:
    if not derivations:
        return ()
    if len(derivations) != 1:
        return ()
    premise_refs = [
        str(value).strip()
        for value in derivations[0].get("premise_refs") or ()
        if str(value).strip()
    ]
    atom_by_ref = {
        str(atom.get("evidence_ref") or ""): atom
        for atom in atoms
        if str(atom.get("evidence_ref") or "")
    }
    if not premise_refs or set(premise_refs) != set(atom_by_ref):
        return ()
    return tuple(
        dict.fromkeys(
            str(atom_by_ref[reference].get("evidence_id") or "")
            for reference in premise_refs
            if str(atom_by_ref[reference].get("evidence_id") or "")
        )
    )


def _bind_side_slots(
    slots: list[Any],
    atom_by_id: dict[str, list[dict[str, Any]]],
    requires_distinct: bool,
) -> tuple[dict[str, tuple[str, ...]], list[str]] | None:
    bindings: dict[str, tuple[str, ...]] = {}
    selected_ids: list[str] = []
    used_ids: set[str] = set()
    for slot in slots:
        candidate_ids = _slot_atom_ids(slot, atom_by_id)
        if not candidate_ids:
            return None
        selected_id = next(
            (
                evidence_id
                for evidence_id in candidate_ids
                if not requires_distinct or evidence_id not in used_ids
            ),
            None,
        )
        if selected_id is None:
            return None
        bindings[str(slot.slot_id)] = (selected_id,)
        selected_ids.append(selected_id)
        used_ids.add(selected_id)
    return bindings, selected_ids


def _is_boolean_proposition_slot(slot: Any) -> bool:
    return bool(
        str(getattr(slot, "statement_kind", "") or "") == "boolean_proposition"
        or str(getattr(slot, "slot_id", "") or "").endswith("proposition")
    )


def _slot_atom_ids(
    slot: Any,
    atom_by_id: dict[str, list[dict[str, Any]]],
) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            str(evidence_id)
            for evidence_id in getattr(slot, "evidence_ids", ()) or ()
            if str(evidence_id) in atom_by_id
        )
    )
