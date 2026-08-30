from __future__ import annotations

import hashlib
import json
from typing import Any

from jsonschema import Draft202012Validator
from ktem.docqa.evidence_schema import EvidenceBundle

from .mara_qasper_semantic_pack import (
    qasper_canonical_evidence_plans,
    qasper_canonical_selector_bindings,
)
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SemanticPropositionEvidencePacking,
)
from .mara_semantic_proposition_schema import parse_semantic_proposition_response
from .mara_semantic_proposition_schema_contract import semantic_proposition_schema


class ControlledContractProbeIdentityError(ValueError):
    """The controlled proposal is not identical across schema and parser."""


def controlled_contract_probe_proposal(
    prompt: str,
    *,
    bundle: EvidenceBundle,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    candidate: str,
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
    allowed_bindings = qasper_canonical_selector_bindings(packing.records)
    allowed_plans = qasper_canonical_evidence_plans(bundle)
    selector_id = str(selectors[0].get("selector_id") or "")
    selector_bindings = list(allowed_bindings.get(selector_id, ()))
    if set(selector_bindings) != set(applicable):
        raise ControlledContractProbeIdentityError(
            "controlled_payload_selector_not_locally_complete"
        )
    controlled_payload: dict[str, Any] = {
        "candidate_judgment": str(control.get("candidate_judgment") or ""),
        "support_mode": "evidence_set",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": selector_id,
                "proposition_fragment": str(selectors[0].get("text") or ""),
                "supports_slot_ids": [slot["slot_id"] for slot in slots],
                "binds_proposition_slots": selector_bindings,
            }
        ],
        "not_applicable_proposition_slots": [
            slot
            for slot in ("actor", "predicate", "object", "quantifier")
            if slot not in applicable
        ],
    }
    normalized_candidate = str(candidate or "").strip().casefold()
    if (
        normalized_candidate == "unanswerable"
        and controlled_payload["candidate_judgment"] == "contradicted"
    ):
        controlled_payload["evidence_relation"] = str(
            control.get("evidence_relation") or ""
        )
    control["payload_identity_gate"] = _validate_controlled_payload_identity(
        controlled_payload,
        packing=packing,
        slots=slots,
        candidate=normalized_candidate,
        applicable_proposition_slots=applicable,
        allowed_proposition_slot_bindings=allowed_bindings,
        allowed_proposition_evidence_plans=allowed_plans,
    )
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


def _validate_controlled_payload_identity(
    payload: dict[str, Any],
    *,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    candidate: str,
    applicable_proposition_slots: list[str],
    allowed_proposition_slot_bindings: dict[str, tuple[str, ...]],
    allowed_proposition_evidence_plans: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    slot_ids = [str(slot.get("slot_id") or "") for slot in slots]
    schema = semantic_proposition_schema(
        slot_ids,
        candidate=candidate,
        applicable_proposition_slots=applicable_proposition_slots,
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )
    errors = sorted(
        Draft202012Validator(schema).iter_errors(payload),
        key=lambda error: tuple(str(value) for value in error.absolute_path),
    )
    if errors:
        error = errors[0]
        path = ".".join(str(value) for value in error.absolute_path) or "<root>"
        raise ControlledContractProbeIdentityError(
            f"controlled_payload_schema_rejected:{path}:{error.validator}"
        )
    parsed = parse_semantic_proposition_response(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        packed=packing.records,
        slot_ids=set(slot_ids),
        model="contract-probe-identity-gate",
        seed=0,
        candidate=candidate,
        applicable_proposition_slots=applicable_proposition_slots,
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )
    if parsed.value is None:
        raise ControlledContractProbeIdentityError(
            "controlled_payload_parser_rejected:"
            f"{parsed.failure_reason or 'unknown_parser_failure'}"
        )
    return {
        "status": "passed",
        "candidate": candidate,
        "schema_status": "accepted",
        "parser_status": "accepted",
        "payload_digest": _digest(payload),
        "candidate_schema_digest": _digest(schema),
    }


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
