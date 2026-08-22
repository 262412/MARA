from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any

from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
)
from .mara_semantic_proposition_stages import ParsedSemanticStage


def requires_proof_repair(audit: ParsedSemanticStage) -> bool:
    from .mara_semantic_entailment_audit import semantic_entailment_cross_field_reason

    return bool(
        audit.value is not None
        and semantic_entailment_cross_field_reason(audit.value)
        == "premise_false_jointly_entails_true"
    )


def prune_invalid_premises(
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    slots: list[dict[str, str]],
) -> ParsedSemanticStage | None:
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
    if not kept or covered_slots != required_slots or len(kept) > 4:
        return None
    value["premises"] = kept
    value["proof_mode"] = (
        "atomic_semantic" if len(kept) == 1 else "composite_conjunction"
    )
    value.pop("entailment_audit", None)
    value.pop("typed_conclusion", None)
    return replace(proposal, value=value)


def proof_rebuild_prompt(
    proposal_prompt: str,
    audit: ParsedSemanticStage,
) -> str | None:
    invalid_refs = [
        str(check.get("premise_ref") or "")
        for check in (audit.value or {}).get("premise_checks") or []
        if check.get("fragment_entailed") is not True
        or check.get("scope_consistent") is not True
    ]
    instruction = (
        "\n\nPROOF REPAIR: the independent audit rejected premise refs "
        f"{','.join(invalid_refs) or 'unknown'}. Rebuild the complete proof from "
        "the canonical span selectors. Do not reuse a rejected fragment. Return "
        "insufficient_evidence if no atomic proof or genuine 2-4 premise "
        "conjunction covers every required slot."
    )
    if len(proposal_prompt) + len(instruction) > (
        SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS
    ):
        return None
    return proposal_prompt + instruction


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
