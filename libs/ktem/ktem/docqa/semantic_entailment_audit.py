from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from .boolean_authority_schema import (
    GROUNDED_SEMANTIC_AUDITOR_CONTRACT,
    SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
)


def semantic_entailment_proposal_digest(
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
) -> str:
    """Bind an entailment audit to the exact proposed proof transaction."""

    payload = {
        "question": str(question or "").strip(),
        "verdict": str(verdict or ""),
        "premises": [
            {
                "evidence_id": str(value.get("evidence_id") or ""),
                "quote": str(value.get("quote") or ""),
                "proposition_fragment": str(value.get("proposition_fragment") or ""),
                "supports_slot_ids": sorted(
                    str(slot_id) for slot_id in value.get("supports_slot_ids") or []
                ),
            }
            for value in premises
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def semantic_entailment_audit_attestation(
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    *,
    model: str,
    seed: int,
) -> dict[str, Any]:
    """Create the verified audit record after every audit check passed."""

    return {
        "contract_id": SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
        "status": "verified",
        "proposal_digest": semantic_entailment_proposal_digest(
            question,
            verdict,
            premises,
        ),
        "verdict": verdict,
        "premise_count": len(premises),
        "premise_checks": [
            {
                "premise_index": index,
                "evidence_id": str(premise.get("evidence_id") or ""),
                "quote_digest": _text_digest(str(premise.get("quote") or "")),
                "fragment_digest": _text_digest(
                    str(premise.get("proposition_fragment") or "")
                ),
                "fragment_entailed": True,
                "scope_consistent": True,
            }
            for index, premise in enumerate(premises, start=1)
        ],
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "auditor": {
            "contract_id": GROUNDED_SEMANTIC_AUDITOR_CONTRACT,
            "model": str(model or ""),
            "seed": seed,
        },
    }


def semantic_entailment_audit_validation_reason(
    question: str,
    verdict: str,
    premises: Sequence[Mapping[str, Any]],
    audit: Any,
) -> str:
    """Return an empty reason only for a complete, proposal-bound audit."""

    if not isinstance(audit, Mapping):
        return "semantic_entailment_audit_missing"
    if (
        audit.get("contract_id") != SEMANTIC_ENTAILMENT_AUDIT_CONTRACT
        or audit.get("status") != "verified"
        or audit.get("verdict") != verdict
        or _as_int(audit.get("premise_count")) != len(premises)
        or audit.get("proposal_digest")
        != semantic_entailment_proposal_digest(question, verdict, premises)
    ):
        return "semantic_entailment_audit_binding_invalid"
    if (
        audit.get("jointly_entails") is not True
        or audit.get("each_premise_required") is not True
        or audit.get("contradiction_free") is not True
    ):
        return "semantic_entailment_audit_verdict_invalid"
    auditor = audit.get("auditor")
    if not isinstance(auditor, Mapping) or (
        auditor.get("contract_id") != GROUNDED_SEMANTIC_AUDITOR_CONTRACT
        or not str(auditor.get("model") or "").strip()
    ):
        return "semantic_entailment_auditor_attestation_invalid"
    raw_checks = audit.get("premise_checks")
    if not isinstance(raw_checks, list) or len(raw_checks) != len(premises):
        return "semantic_entailment_premise_audit_incomplete"
    for index, (check, premise) in enumerate(zip(raw_checks, premises), start=1):
        if not isinstance(check, Mapping) or (
            _as_int(check.get("premise_index")) != index
            or check.get("evidence_id") != str(premise.get("evidence_id") or "")
            or check.get("quote_digest")
            != _text_digest(str(premise.get("quote") or ""))
            or check.get("fragment_digest")
            != _text_digest(str(premise.get("proposition_fragment") or ""))
            or check.get("fragment_entailed") is not True
            or check.get("scope_consistent") is not True
        ):
            return "semantic_entailment_premise_audit_invalid"
    return ""


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
