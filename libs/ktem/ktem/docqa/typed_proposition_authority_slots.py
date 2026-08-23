from __future__ import annotations

from typing import Any

from .boolean_authority_schema import SEMANTIC_EVIDENCE_SET_RULE
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
) -> tuple[
    dict[str, tuple[str, ...]] | None,
    dict[str, tuple[str, ...]] | None,
    list[dict[str, Any]] | None,
]:
    """Bind exact atoms to pre-bound slots without inventing slot coverage."""

    atom_by_id: dict[str, list[dict[str, Any]]] = {}
    for atom in atoms:
        evidence_id = str(atom.get("evidence_id") or "")
        if evidence_id:
            atom_by_id.setdefault(evidence_id, []).append(atom)
    if not atom_by_id:
        return None, None, None

    plan = getattr(request, "query_plan", None)
    constraints = getattr(plan, "constraints", {}) if plan is not None else {}
    requires_distinct = bool(
        isinstance(constraints, dict) and constraints.get("requires_distinct_evidence")
    )
    semantic = _semantic_evidence_set_bindings(
        required_slots,
        derivations or [],
        atoms,
        requires_distinct=requires_distinct,
    )
    if semantic is not None:
        return semantic
    if any(
        str(value.get("rule_id") or "") == SEMANTIC_EVIDENCE_SET_RULE
        for value in derivations or []
    ):
        return None, None, None
    return _single_or_composite_slot_bindings(
        required_slots,
        atom_by_id,
        derivations or [],
        requires_distinct=requires_distinct,
    )


def _single_or_composite_slot_bindings(
    required_slots: list[Any],
    atom_by_id: dict[str, list[dict[str, Any]]],
    derivations: list[dict[str, Any]],
    *,
    requires_distinct: bool,
) -> tuple[
    dict[str, tuple[str, ...]] | None,
    dict[str, tuple[str, ...]] | None,
    list[dict[str, Any]] | None,
]:
    proposition_slots = [
        slot for slot in required_slots if _is_boolean_proposition_slot(slot)
    ]
    side_slots = [
        slot for slot in required_slots if not _is_boolean_proposition_slot(slot)
    ]
    bindings: dict[str, tuple[str, ...]] = {}
    selected_ids: list[str] = []
    atoms = [atom for values in atom_by_id.values() for atom in values]
    proof_ids = _selected_proof_ids(derivations, atoms)
    if derivations and not proof_ids:
        return None, None, None

    if not side_slots and len(proposition_slots) == 1:
        slot = proposition_slots[0]
        candidate_ids = _slot_atom_ids(slot, atom_by_id)
        if proof_ids:
            proposition_selection = proof_ids
        else:
            if not candidate_ids:
                return None, None, None
            proposition_selection = (candidate_ids[0],)
        bindings[str(slot.slot_id)] = proposition_selection
        selected_ids.extend(proposition_selection)

    side_binding = _bind_side_slots(side_slots, atom_by_id, requires_distinct)
    if side_binding is None:
        return None, None, None
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
            return None, None, None
        slot_selection: tuple[str, ...]
        if side_slots:
            selected_side_ids = tuple(dict.fromkeys(selected_ids))
            if any(
                evidence_id not in candidate_ids for evidence_id in selected_side_ids
            ):
                return None, None, None
            slot_selection = selected_side_ids
        else:
            slot_selection = (candidate_ids[0],)
        bindings[str(slot.slot_id)] = slot_selection
        selected_ids.extend(slot_selection)

    if {str(slot.slot_id) for slot in required_slots} != set(bindings):
        return None, None, None
    selected_id_set = set(selected_ids)
    selected_atoms = [
        atom for atom in atoms if str(atom.get("evidence_id") or "") in selected_id_set
    ]
    if not selected_atoms:
        return None, None, None
    return bindings, {}, selected_atoms


def _semantic_evidence_set_bindings(
    slots: list[Any],
    derivations: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
    *,
    requires_distinct: bool,
) -> (
    tuple[
        dict[str, tuple[str, ...]],
        dict[str, tuple[str, ...]],
        list[dict[str, Any]],
    ]
    | None
):
    selected = [
        value
        for value in derivations
        if str(value.get("rule_id") or "") == SEMANTIC_EVIDENCE_SET_RULE
    ]
    if len(selected) != 1:
        return None
    atom_by_ref = {
        str(atom.get("evidence_ref") or ""): atom
        for atom in atoms
        if str(atom.get("evidence_ref") or "")
    }
    slot_ids = {str(slot.slot_id) for slot in slots}
    bound: dict[str, list[str]] = {slot_id: [] for slot_id in slot_ids}
    bound_refs: dict[str, list[str]] = {slot_id: [] for slot_id in slot_ids}
    for contribution in selected[0].get("premise_contributions") or []:
        if not isinstance(contribution, dict):
            return None
        reference = str(contribution.get("evidence_ref") or "")
        atom = atom_by_ref.get(reference)
        supports = {
            str(value).strip()
            for value in contribution.get("supports_slot_ids") or []
            if str(value).strip()
        }
        if atom is None or not supports or not supports <= slot_ids:
            return None
        evidence_id = str(atom.get("evidence_id") or "")
        for slot_id in supports:
            if evidence_id and evidence_id not in bound[slot_id]:
                bound[slot_id].append(evidence_id)
            if reference not in bound_refs[slot_id]:
                bound_refs[slot_id].append(reference)
    if any(not values for values in bound.values()):
        return None
    slot_by_id = {str(slot.slot_id): slot for slot in slots}
    if requires_distinct and not _distinct_semantic_side_bindings(
        bound_refs,
        slot_by_id,
    ):
        return None
    bindings = {slot_id: tuple(values) for slot_id, values in bound.items()}
    ref_bindings = {slot_id: tuple(values) for slot_id, values in bound_refs.items()}
    selected_ids = {value for values in bindings.values() for value in values}
    selected_atoms = [
        atom for atom in atoms if str(atom.get("evidence_id") or "") in selected_ids
    ]
    return (bindings, ref_bindings, selected_atoms) if selected_atoms else None


def _distinct_semantic_side_bindings(
    bindings: dict[str, list[str]],
    slots: dict[str, Any],
) -> bool:
    side_values = [
        values
        for slot_id, values in bindings.items()
        if not _is_boolean_proposition_slot(slots[slot_id])
    ]
    if any(len(values) != 1 for values in side_values):
        return False
    selected = [values[0] for values in side_values]
    return len(selected) == len(set(selected))


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
