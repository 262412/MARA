from __future__ import annotations

from copy import deepcopy
from typing import Any


def frozen_canonical_audit_result(
    raw_audit: dict[str, Any],
    projection: Any,
) -> dict[str, Any]:
    """Project audit authority from one already validated frozen plan."""

    checks = deepcopy(raw_audit.get("premise_checks"))
    premises = tuple(getattr(projection, "premises", ()) or ())
    if (
        not isinstance(checks, list)
        or len(checks) != len(premises)
        or any(not isinstance(check, dict) for check in checks)
    ):
        raise ValueError("frozen_canonical_audit_projection_invalid")
    for index, (check, premise) in enumerate(zip(checks, premises), start=1):
        declared = list(premise.get("binds_proposition_slots") or [])
        slot_checks = check.get("proposition_slot_checks")
        if (
            check.get("premise_ref") != f"P{index}"
            or check.get("declared_proposition_slots") != declared
            or not isinstance(slot_checks, list)
            or [value.get("slot") for value in slot_checks] != declared
        ):
            raise ValueError("frozen_canonical_audit_projection_invalid")
        if (
            check.get("scope_consistent") is not True
            or check.get("proposition_bindings_valid") is not True
            or check.get("evidence_relation_valid") is not True
            or any(
                slot_check.get("binding_valid") is not True
                for slot_check in slot_checks
            )
        ):
            raise ValueError("frozen_canonical_audit_semantic_denial")
        check["fragment_entailed"] = True
    conclusion = deepcopy(raw_audit.get("conclusion_check"))
    if not isinstance(conclusion, dict):
        raise ValueError("frozen_canonical_audit_projection_invalid")
    for field in (
        "conclusion_entailed",
        "actor_consistent",
        "predicate_consistent",
        "object_consistent",
        "polarity_consistent",
        "quantifier_consistent",
        "scope_consistent",
    ):
        if field not in conclusion:
            raise ValueError("frozen_canonical_audit_projection_invalid")
        if conclusion[field] is not True:
            raise ValueError("frozen_canonical_audit_semantic_denial")
    for field in ("jointly_entails", "each_premise_required", "contradiction_free"):
        if raw_audit.get(field) is not True:
            raise ValueError("frozen_canonical_audit_semantic_denial")
    return {
        "premise_checks": checks,
        "jointly_entails": raw_audit["jointly_entails"],
        "each_premise_required": raw_audit["each_premise_required"],
        "contradiction_free": raw_audit["contradiction_free"],
        "conclusion_check": conclusion,
    }
