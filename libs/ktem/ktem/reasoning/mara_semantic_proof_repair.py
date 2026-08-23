from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import replace
from typing import Any

from ktem.docqa.question_proposition import PROPOSITION_EVIDENCE_SLOTS

from .mara_semantic_proposition_stages import ParsedSemanticStage

_PROOF_REPAIR_REASONS = frozenset(
    {
        "auditor_internal_inconsistency",
        "premise_false_jointly_entails_true",
        "premise_fragment_not_entailed",
        "premise_scope_inconsistent",
        "joint_entailment_rejected",
        "premise_not_required",
        "contradiction_detected",
        "joint_entailment_conclusion_inconsistent",
        "conclusion_entailment_without_joint_support",
        "typed_conclusion_not_entailed",
        "typed_conclusion_polarity_rejected",
        "typed_conclusion_quantifier_rejected",
        "typed_conclusion_scope_rejected",
    }
)

_PRUNABLE_PREMISE_REASONS = frozenset(
    {
        "premise_false_jointly_entails_true",
        "premise_fragment_not_entailed",
        "premise_scope_inconsistent",
    }
)


def requires_proof_repair(
    audit: ParsedSemanticStage,
    *,
    reason: str = "",
) -> bool:
    from .mara_semantic_entailment_audit import semantic_entailment_rejection_reason

    return bool(
        audit.value is not None
        and (reason or semantic_entailment_rejection_reason(audit.value))
        in _PROOF_REPAIR_REASONS
    )


def prune_invalid_premises(
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    slots: list[dict[str, str]],
    *,
    reason: str,
) -> ParsedSemanticStage | None:
    if reason not in _PRUNABLE_PREMISE_REASONS:
        return None
    value = deepcopy(proposal.value or {})
    premises = list(value.get("premises") or [])
    checks = list((audit.value or {}).get("premise_checks") or [])
    kept = [
        premise
        for premise, check in zip(premises, checks)
        if check.get("fragment_entailed") is True
        and check.get("scope_consistent") is True
    ]
    required_slots = {str(slot.get("slot_id") or "") for slot in slots}
    covered_slots = {
        str(slot_id)
        for premise in kept
        for slot_id in premise.get("supports_slot_ids") or []
    }
    covered_proposition_slots = {
        str(slot)
        for premise in kept
        for slot in premise.get("binds_proposition_slots") or []
    }
    if (
        not kept
        or covered_slots != required_slots
        or covered_proposition_slots != set(PROPOSITION_EVIDENCE_SLOTS)
        or len(kept) > 4
    ):
        return None
    value["premises"] = kept
    value["proof_mode"] = (
        "atomic_semantic" if len(kept) == 1 else "composite_conjunction"
    )
    value.pop("entailment_audit", None)
    value.pop("typed_conclusion", None)
    return replace(proposal, value=value)


def semantic_proposal_binding_digest(value: dict[str, Any] | None) -> str:
    payload = value or {}
    canonical = {
        "verdict": str(payload.get("verdict") or ""),
        "evidence_relation": str(payload.get("evidence_relation") or ""),
        "proof_mode": str(payload.get("proof_mode") or ""),
        "premises": [
            {
                "span_selector": str(premise.get("span_selector") or ""),
                "supports_slot_ids": sorted(
                    str(slot) for slot in premise.get("supports_slot_ids") or []
                ),
                "binds_proposition_slots": sorted(
                    str(slot) for slot in premise.get("binds_proposition_slots") or []
                ),
                "proposition_slot_bindings": dict(
                    premise.get("proposition_slot_bindings") or {}
                ),
                "evidence_relation": str(premise.get("evidence_relation") or ""),
            }
            for premise in payload.get("premises") or []
            if isinstance(premise, dict)
        ],
    }
    serialized = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def merge_proof_repair_debug(
    initial: dict[str, Any] | None,
    repaired: dict[str, Any] | None,
    *,
    transition: dict[str, Any],
    repaired_proposal: dict[str, Any] | None,
    repair_kind: str,
) -> dict[str, Any] | None:
    if initial is None and repaired is None:
        return None
    merged = deepcopy(repaired or initial or {})
    merged["proof_repair"] = {
        "kind": repair_kind,
        "transition": deepcopy(transition),
        "initial_proposal": deepcopy((initial or {}).get("proposal") or {}),
        "initial_audit": deepcopy((initial or {}).get("audit") or {}),
        "repaired_proposal": deepcopy(repaired_proposal or {}),
        "proof_reaudit": deepcopy((repaired or {}).get("audit") or {}),
    }
    return merged
