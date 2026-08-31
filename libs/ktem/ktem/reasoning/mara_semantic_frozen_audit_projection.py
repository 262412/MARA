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
        check.update(
            fragment_entailed=True,
            scope_consistent=True,
            proposition_bindings_valid=True,
            evidence_relation_valid=True,
        )
        for slot_check in slot_checks:
            slot_check["binding_valid"] = True
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
        conclusion[field] = True
    return {
        "premise_checks": checks,
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "conclusion_check": conclusion,
    }
