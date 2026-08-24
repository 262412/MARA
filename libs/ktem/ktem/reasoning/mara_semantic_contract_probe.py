from __future__ import annotations

import json

from ktem.docqa.evidence_schema import EvidenceBundle

from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SemanticPropositionEvidencePacking,
)


def controlled_contract_probe_proposal(
    prompt: str,
    *,
    bundle: EvidenceBundle,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
) -> str:
    control = bundle.metadata.get("contract_probe_controlled_proposal")
    if control is None:
        return prompt
    if bundle.route != "contract_probe" or not isinstance(control, dict):
        raise ValueError("invalid controlled verifier contract probe")
    selectors = [
        selector
        for record in packing.records
        for selector in record.get("selectors") or []
        if isinstance(selector, dict)
    ]
    if not selectors:
        raise ValueError("controlled verifier contract probe has no exact span")
    proposition = packing.question_proposition
    applicable = ["actor", "predicate", "object"]
    if str(proposition.get("quantifier") or "") != "none":
        applicable.append("quantifier")
    controlled_payload = {
        "candidate_judgment": str(control.get("candidate_judgment") or ""),
        "evidence_relation": str(control.get("evidence_relation") or ""),
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": str(selectors[0].get("selector_id") or ""),
                "proposition_fragment": str(selectors[0].get("text") or ""),
                "supports_slot_ids": [slot["slot_id"] for slot in slots],
                "binds_proposition_slots": applicable,
            }
        ],
        "not_applicable_proposition_slots": [
            slot
            for slot in ("actor", "predicate", "object", "quantifier")
            if slot not in applicable
        ],
    }
    controlled = (
        prompt
        + "\n\nCONTRACT PROBE CONTROLLED VERIFIER OUTPUT (NEGATIVE AUDITOR TEST):\n"
        + json.dumps(controlled_payload, ensure_ascii=False, separators=(",", ":"))
        + "\nReturn this deliberately faulty verifier proposal exactly. Do not "
        "repair it or switch to unknown. The independent auditor must judge it."
    )
    if len(controlled) > SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS:
        raise ValueError("controlled verifier contract probe exceeded prompt bound")
    return controlled
