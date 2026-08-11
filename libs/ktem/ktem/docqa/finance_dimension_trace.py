from __future__ import annotations

from typing import Any

from .finance_scale import valid_dimension_binding_scope


def finance_dimension_bindings(
    calculation_plan: dict[str, Any],
) -> list[dict[str, Any]]:
    bindings: dict[tuple[str, str, str], dict[str, Any]] = {}
    for operand in calculation_plan.get("operands") or []:
        if not isinstance(operand, dict):
            continue
        evidence_id = str(
            operand.get("scale_evidence_identity")
            or operand.get("scale_evidence_id")
            or ""
        ).strip()
        scale = str(operand.get("scale") or "").strip()
        scope = str(operand.get("dimension_binding_scope") or "").strip()
        if not evidence_id or not scale or not valid_dimension_binding_scope(scope):
            continue
        key = (evidence_id, scale, scope)
        binding = bindings.setdefault(
            key,
            {
                "dimension_slot_id": "dimension:scale",
                "dimension_evidence_id": evidence_id,
                "detected_scale": scale,
                "applied_operand_ids": [],
                "binding_scope": scope,
            },
        )
        binding["applied_operand_ids"].append(str(operand.get("operand_id") or ""))
    return list(bindings.values())
