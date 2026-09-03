from __future__ import annotations

from dataclasses import replace
from typing import Any

from .boolean_authoritative_conflict import (
    conflict_authorities,
    conflict_authority_matches_item,
    conflict_sides_are_complete,
    with_verified_conflict_slots,
)
from .boolean_evidence_scope import evidence_item_text
from .claim_support import claim_supported
from .evidence_alias_lookup import unambiguous_evidence_alias_lookup
from .evidence_identity import identity_of
from .evidence_schema import EvidenceBundle
from .layered_claim_support import layered_claim_supporting_ids
from .query_plan_schema import EvidenceSlot, _slot_from_payload
from .query_planning import score_evidence_for_slot
from .typed_proposition_authority import coherent_authority_failure
from .typed_proposition_authority_atoms import (
    bound_boolean_derivations,
    exact_boolean_atoms,
)
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
    boolean_authority_required = _requires_typed_boolean_authority(request)
    composite_ids = _validated_composite_support_ids(
        decision,
        evidence_bundle,
        prompt=prompt,
    )
    resolved_support = _resolved_claim_support(
        supported_claims,
        selected_lookup,
        boolean_authority_required=boolean_authority_required,
        composite_ids=composite_ids,
        prompt=prompt,
        domain=domain,
    )

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
    used_ids = {value for values in reconciled.values() for value in values}
    if composite_ids and not composite_ids <= used_ids:
        return {}
    return reconciled


def _resolved_claim_support(
    supported_claims: list[tuple[str, str, dict[str, Any]]],
    selected_lookup: dict[str, dict[str, Any]],
    *,
    boolean_authority_required: bool,
    composite_ids: set[str],
    prompt: str,
    domain: str,
) -> list[tuple[str, dict[str, Any]]]:
    resolved = []
    for claim, evidence_id, result in supported_claims:
        item = selected_lookup.get(evidence_id)
        if item is None:
            continue
        try:
            identity = identity_of(item).key
        except ValueError:
            continue
        if _claim_result_supports_item(
            claim,
            result,
            item,
            identity,
            boolean_authority_required=boolean_authority_required,
            prompt=prompt,
            domain=domain,
            composite_ids=composite_ids,
        ):
            resolved.append((identity, item))
    return resolved


def _claim_result_supports_item(
    claim: str,
    result: dict[str, Any],
    item: dict[str, Any],
    identity: str,
    *,
    boolean_authority_required: bool,
    prompt: str,
    domain: str,
    composite_ids: set[str],
) -> bool:
    if str(result.get("authority_status") or "") == "visual_page":
        return True
    if _exact_boolean_authority_matches(result, item, identity):
        return True
    if str(result.get("authority_status") or "") == "composite_exact":
        return identity in composite_ids
    if boolean_authority_required:
        return False
    return claim_supported(
        claim,
        [item],
        prompt=prompt,
        domain=domain,
    ) or identity in layered_claim_supporting_ids(
        claim,
        [item],
        prompt=prompt,
    )


def _validated_composite_support_ids(
    decision: Any,
    evidence_bundle: EvidenceBundle | None,
    *,
    prompt: str,
) -> set[str]:
    if evidence_bundle is None:
        return set()
    if not any(
        str(result.get("authority_status") or "") == "composite_exact"
        for result in decision.claim_results
    ):
        return set()
    atoms = exact_boolean_atoms(decision, evidence_bundle, question=prompt)
    derivations = bound_boolean_derivations(
        decision,
        atoms,
        question=prompt,
    )
    if len(derivations) != 1:
        return set()
    return {
        str(value).strip()
        for value in derivations[0].get("premise_evidence_ids") or ()
        if str(value).strip()
    }


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


def conflict_aware_slot_support(
    request: Any,
    decision: Any,
    evidence_bundle: EvidenceBundle | None,
) -> dict[str, tuple[str, ...]]:
    """Map both exact conflict sides onto every required support slot."""

    conflict = getattr(decision, "authoritative_conflict", None)
    if (
        not isinstance(conflict, dict)
        or not conflict_sides_are_complete(conflict)
        or evidence_bundle is None
    ):
        return {}
    selected_lookup = unambiguous_evidence_alias_lookup(evidence_bundle.items)
    resolved: dict[str, dict[str, Any]] = {}
    for authority in conflict_authorities(conflict):
        evidence_id = str(authority.get("evidence_id") or "")
        item = selected_lookup.get(evidence_id)
        if item is None or not conflict_authority_matches_item(authority, item):
            return {}
        resolved[identity_of(item).key] = item
    if not resolved:
        return {}

    reconciled: dict[str, tuple[str, ...]] = {}
    for slot in verification_slots(request):
        if str(slot_value(slot, "role") or "") != "support":
            continue
        slot_id = str(slot_value(slot, "slot_id") or "")
        bound_ids = _selected_slot_identities(slot, selected_lookup)
        support_ids = [
            evidence_id
            for evidence_id, item in resolved.items()
            if evidence_id in bound_ids
            or score_evidence_for_slot(scoring_slot(slot), item) > 0
        ]
        if support_ids:
            reconciled[slot_id] = tuple(dict.fromkeys(support_ids))
    used_ids = {evidence_id for values in reconciled.values() for evidence_id in values}
    return reconciled if set(resolved) <= used_ids else {}


def enforce_verification_slot_support(
    request: Any,
    decision: Any,
    evidence_bundle: EvidenceBundle | None = None,
    *,
    prompt: str = "",
    domain: str = "",
) -> Any:
    if decision.status == "verified_conflict":
        return _enforce_conflict_slot_support(request, decision, evidence_bundle)
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
    reason = "verification_required_slots_unsupported:" + ",".join(unsupported_slots)
    if _requires_typed_boolean_authority(request) or str(domain).startswith("qasper"):
        return coherent_authority_failure(decision, reason)
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


def _enforce_conflict_slot_support(
    request: Any,
    decision: Any,
    evidence_bundle: EvidenceBundle | None,
) -> Any:
    reconciled_slots = conflict_aware_slot_support(
        request,
        decision,
        evidence_bundle,
    )
    unsupported_slots = unsupported_verification_slots(request, reconciled_slots)
    if unsupported_slots:
        return coherent_authority_failure(
            decision,
            "authoritative_conflict_slots_unsupported:" + ",".join(unsupported_slots),
        )
    conflict = with_verified_conflict_slots(
        decision.authoritative_conflict,
        reconciled_slots,
    )
    slot_ids = list(reconciled_slots)
    claim_results = [
        {
            **result,
            "authority_status": (
                "verified_conflict"
                if result.get("authoritative_conflict")
                else str(result.get("authority_status") or "")
            ),
            "authoritative_conflict": (
                conflict if result.get("authoritative_conflict") else {}
            ),
            "verified_slot_state": (
                "verified_conflict"
                if result.get("authoritative_conflict")
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
        boolean_authority_status="verified_conflict",
        authoritative_conflict=conflict,
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


def _selected_slot_identities(
    slot: Any,
    selected_lookup: dict[str, dict[str, Any]],
) -> set[str]:
    return {
        identity_of(selected_lookup[evidence_id]).key
        for value in slot_value(slot, "evidence_ids") or ()
        if (evidence_id := str(value).strip()) in selected_lookup
    }


def _exact_boolean_authority_matches(
    result: dict[str, Any],
    item: dict[str, Any],
    identity: str,
) -> bool:
    if str(result.get("authority_status") or "") != "exact":
        return False
    if str(result.get("authoritative_evidence_id") or "") != identity:
        return False
    if not all(
        _typed_authority_value(result, key)
        for key in (
            "actor",
            "predicate",
            "arguments",
            "polarity",
            "qualifier",
            "quantifier",
            "scope",
        )
    ):
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


def _typed_authority_value(result: dict[str, Any], key: str) -> Any:
    aliases = {
        "predicate": "relation",
        "arguments": "object",
        "polarity": "canonical_answer_polarity",
        "scope": "section_scope",
    }
    return result.get(key) or result.get(aliases.get(key, ""))


def _requires_typed_boolean_authority(request: Any) -> bool:
    plan = getattr(request, "query_plan", None)
    answer_type = slot_value(plan, "answer_type")
    domain = str(getattr(request, "verification_domain", "") or "").lower()
    evidence_slots = slot_value(plan, "evidence_slots") or ()
    explicit_boolean_proposition = any(
        str(slot_value(slot, "statement_kind") or "") == "boolean_proposition"
        for slot in evidence_slots
    )
    if explicit_boolean_proposition:
        return True
    if str(answer_type or getattr(request, "task_type", "")).lower() != "boolean":
        return False
    return domain not in {"finance", "financial", "financebench"}
