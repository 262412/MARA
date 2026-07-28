from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of


def claim_support_identities_by_claim(
    claim_results: list[dict[str, Any]],
    lookup: dict[str, dict[str, Any]],
) -> dict[str, list[str]]:
    output: dict[str, list[str]] = {}
    for result in claim_results:
        if str(result.get("status") or "") != "supported":
            continue
        claim_id = str(result.get("claim_id") or "").strip()
        if not claim_id:
            continue
        resolved: list[str] = []
        seen: set[str] = set()
        for evidence_id in result.get("supporting_evidence_ids") or []:
            item = lookup.get(str(evidence_id).strip())
            if item is None:
                continue
            identity = identity_of(item).key
            if identity not in seen:
                seen.add(identity)
                resolved.append(identity)
        output[claim_id] = resolved
    return output


def verification_slots(request: Any) -> list[Any]:
    plan = getattr(request, "query_plan", None)
    return [
        slot
        for slot in getattr(plan, "evidence_slots", ()) or ()
        if bool(getattr(slot, "required_for_verification", False))
    ]


def missing_verification_slots(request: Any) -> list[str]:
    return [
        str(getattr(slot, "slot_id", "") or "")
        for slot in verification_slots(request)
        if str(getattr(slot, "status", "") or "") != "filled"
        or not tuple(getattr(slot, "evidence_ids", ()) or ())
    ]
