from __future__ import annotations

from dataclasses import replace
from typing import Any

from .boolean_evidence_scope import evidence_item_text
from .claim_support import claim_supported
from .evidence_alias_lookup import unambiguous_evidence_alias_lookup
from .evidence_identity import identity_of
from .evidence_schema import EvidenceBundle
from .query_plan_schema import EvidenceSlot, _slot_from_payload
from .query_planning import score_evidence_for_slot
from .verification_evidence_mapping import verification_slots


def claim_aware_slot_support(
    request: Any,
    decision: Any,
    evidence_bundle: EvidenceBundle | None,
    *,
    prompt: str,
    domain: str,
) -> dict[str, tuple[str, ...]]:
    """Map supported claim evidence onto selected, compatible support slots."""

    supported_claims = [
        (
            str(result.get("claim") or "").strip(),
            str(evidence_id).strip(),
            result,
        )
        for result in decision.claim_results
        if str(result.get("status") or "") == "supported"
        for evidence_id in result.get("supporting_evidence_ids") or []
        if str(result.get("claim") or "").strip() and str(evidence_id).strip()
    ]
    if not supported_claims:
        return {}
    selected_items = list(evidence_bundle.items) if evidence_bundle is not None else []
    selected_lookup = unambiguous_evidence_alias_lookup(selected_items)
    resolved_support: list[tuple[str, dict[str, Any]]] = []
    for claim, evidence_id, result in supported_claims:
        item = selected_lookup.get(evidence_id)
        if item is None:
            continue
        try:
            identity = identity_of(item).key
        except ValueError:
            continue
        if _exact_boolean_authority_matches(result, item, identity) or claim_supported(
            claim,
            [item],
            prompt=prompt,
            domain=domain,
        ):
            resolved_support.append((identity, item))

    reconciled: dict[str, tuple[str, ...]] = {}
    for slot in verification_slots(request):
        if str(slot_value(slot, "role") or "") != "support":
            continue
        slot_id = str(slot_value(slot, "slot_id") or "")
        slot_ids = {
            str(value).strip()
            for value in slot_value(slot, "evidence_ids") or ()
            if str(value).strip()
        }
        slot_support_ids = {
            identity_of(selected_lookup[slot_id]).key
            for slot_id in slot_ids
            if slot_id in selected_lookup
        }
        support_ids = []
        for evidence_id, item in resolved_support:
            if evidence_id in slot_support_ids:
                support_ids.append(evidence_id)
            elif (
                evidence_bundle is not None
                and score_evidence_for_slot(scoring_slot(slot), item) > 0
            ):
                support_ids.append(evidence_id)
        if support_ids:
            reconciled[slot_id] = tuple(dict.fromkeys(support_ids))
    return reconciled


def unsupported_verification_slots(
    request: Any,
    reconciled_slots: dict[str, tuple[str, ...]],
) -> list[str]:
    return [
        str(slot_value(slot, "slot_id") or "")
        for slot in verification_slots(request)
        if str(slot_value(slot, "role") or "") == "support"
        and not reconciled_slots.get(str(slot_value(slot, "slot_id") or ""))
    ]


def enforce_verification_slot_support(
    request: Any,
    decision: Any,
    evidence_bundle: EvidenceBundle | None = None,
    *,
    prompt: str = "",
    domain: str = "",
) -> Any:
    if decision.status != "supported":
        return decision
    reconciled_slots = claim_aware_slot_support(
        request,
        decision,
        evidence_bundle,
        prompt=prompt,
        domain=domain,
    )
    unsupported_slots = unsupported_verification_slots(request, reconciled_slots)
    if not unsupported_slots:
        slot_ids = list(reconciled_slots)
        claim_results = [
            {
                **result,
                "verified_slot_state": (
                    "verified_support"
                    if str(result.get("status") or "") == "supported"
                    else str(result.get("verified_slot_state") or "")
                ),
                "verified_support_slot_ids": slot_ids,
            }
            for result in decision.claim_results
        ]
        return replace(
            decision,
            claim_results=claim_results,
            verified_support_slot_ids=slot_ids,
            boolean_authority_status=(
                "verified_support"
                if getattr(decision, "canonical_answer_polarity", "")
                else getattr(decision, "boolean_authority_status", "")
            ),
        )
    return replace(
        decision,
        status="unknown",
        reason=(
            "Verification-required slots did not support any verified claim: "
            + ", ".join(unsupported_slots)
        ),
        action="abstain",
        unknown_claims=decision.claims,
    )


def slot_value(slot: Any, key: str) -> Any:
    if isinstance(slot, dict):
        return slot.get(key)
    return getattr(slot, key, None)


def scoring_slot(slot: Any) -> EvidenceSlot:
    if isinstance(slot, EvidenceSlot):
        return slot
    if not isinstance(slot, dict):
        return EvidenceSlot(slot_id="", role="support")
    return _slot_from_payload(1, slot)


def _exact_boolean_authority_matches(
    result: dict[str, Any],
    item: dict[str, Any],
    identity: str,
) -> bool:
    if str(result.get("authority_status") or "") != "exact":
        return False
    if str(result.get("authoritative_evidence_id") or "") != identity:
        return False
    quote = str(result.get("authoritative_quote") or "")
    if not quote:
        return False
    text = evidence_item_text(item)
    if text.count(quote) != 1:
        return False
    start = result.get("authoritative_span_start")
    end = result.get("authoritative_span_end")
    return (
        isinstance(start, int)
        and isinstance(end, int)
        and start >= 0
        and end > start
        and text[start:end] == quote
    )
