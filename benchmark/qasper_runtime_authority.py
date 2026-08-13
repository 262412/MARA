from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_authoritative_conflict import (
    BOOLEAN_AUTHORITATIVE_CONFLICT_CONTRACT,
    authoritative_conflict_complete,
    conflict_authorities,
    conflict_authority_matches_item,
)
from ktem.docqa.evidence_identity import identity_of

from .qasper_answer_normalization import canonical_semantic_label
from .qasper_runtime_projection import typed_boolean_authority_frame_complete
from .qasper_typed_authority_audit import typed_authority_audit


def runtime_boolean_authority(
    prediction: dict[str, Any],
    engine_label: str = "",
) -> dict[str, Any]:
    engine_label = engine_label or canonical_semantic_label(
        str(prediction.get("engine_terminal_answer") or "")
    )
    (
        decision,
        bundle,
        plan,
        slots,
        verified_slots,
        required_ids,
    ) = runtime_authority_inputs(prediction)
    if (
        decision.get("status") == "verified_conflict"
        or isinstance(decision.get("authoritative_conflict"), dict)
        and bool(decision.get("authoritative_conflict"))
    ):
        return _runtime_conflict_authority(
            decision,
            bundle=bundle,
            plan=plan,
            slots=slots,
            verified_slots=verified_slots,
            required_ids=required_ids,
            engine_label=engine_label,
        )
    return _runtime_polarity_authority(
        decision,
        bundle=bundle,
        plan=plan,
        slots=slots,
        verified_slots=verified_slots,
        required_ids=required_ids,
        engine_label=engine_label,
    )


def runtime_typed_proposition_authority(
    prediction: dict[str, Any],
) -> dict[str, Any]:
    (
        decision,
        bundle,
        plan,
        slots,
        verified_slots,
        required_ids,
    ) = runtime_authority_inputs(prediction)
    return typed_authority_audit(
        decision,
        bundle,
        slots,
        verified_slots,
        required_ids,
    )


def _runtime_polarity_authority(
    decision: dict[str, Any],
    *,
    bundle: dict[str, Any],
    plan: dict[str, Any],
    slots: list[dict[str, Any]],
    verified_slots: list[dict[str, Any]],
    required_ids: list[str],
    engine_label: str,
) -> dict[str, Any]:
    evidence_id = str(decision.get("authoritative_evidence_id") or "")
    quote = str(decision.get("authoritative_quote") or "")
    evidence_ref = str(decision.get("authoritative_evidence_ref") or "")
    item = _evidence_item_by_identity(records(bundle.get("items")), evidence_id)
    quote_status = _quote_identity_status(
        item,
        quote,
        decision.get("authoritative_span_start"),
        decision.get("authoritative_span_end"),
    )
    claim_results = [
        result
        for result in decision.get("claim_results") or []
        if isinstance(result, dict)
    ]
    complete = _authority_state_complete(
        decision,
        plan=plan,
        slots=slots,
        verified_slots=verified_slots,
        required_ids=required_ids,
        evidence_id=evidence_id,
        evidence_ref=evidence_ref,
        quote_status=quote_status,
        claim_results=claim_results,
        engine_label=engine_label,
    )
    failure_kind = _runtime_authority_failure_kind(
        decision,
        engine_label=engine_label,
        slots=slots,
        required_ids=required_ids,
        evidence_id=evidence_id,
        claim_results=claim_results,
        quote_status=quote_status,
        complete=complete,
    )
    return {
        "complete": complete,
        "authority_kind": "canonical_polarity",
        "status": "complete" if complete else "missing_or_inconsistent",
        "decision": decision,
        "plan": plan,
        "required_slot_ids": [str(slot.get("slot_id") or "") for slot in slots],
        "required_evidence_ids": required_ids,
        "evidence_id": evidence_id,
        "evidence_ref": evidence_ref,
        "quote": quote,
        "quote_ref_validation_status": quote_status,
        "claim_results": claim_results,
        "failure_kind": failure_kind,
    }


def runtime_authority_inputs(
    prediction: dict[str, Any],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[str],
]:
    decision = prediction.get("engine_verify_decision")
    decision = decision if isinstance(decision, dict) else {}
    bundle = prediction.get("engine_terminal_evidence_bundle")
    bundle = bundle if isinstance(bundle, dict) else {}
    bundle_metadata = bundle.get("metadata")
    bundle_metadata = bundle_metadata if isinstance(bundle_metadata, dict) else {}
    plan = bundle_metadata.get("query_plan") or bundle_metadata.get("bound_query_plan")
    if not isinstance(plan, dict) or not plan:
        metadata = prediction.get("evidence_metadata")
        metadata = metadata if isinstance(metadata, dict) else {}
        plan = metadata.get("query_plan") or metadata.get("bound_query_plan")
    plan = plan if isinstance(plan, dict) else {}
    slots = [
        slot
        for slot in plan.get("evidence_slots") or []
        if isinstance(slot, dict)
        and slot.get("required_for_verification")
        and (
            slot.get("role") == "support"
            or slot.get("statement_kind") == "boolean_proposition"
        )
    ]
    verified_slots = [
        slot
        for slot in slots
        if slot.get("status") in {"verified_support", "verified_conflict"}
    ]
    required_ids = list(
        dict.fromkeys(
            str(evidence_id)
            for slot in verified_slots
            for evidence_id in slot.get("evidence_ids") or []
            if str(evidence_id).strip()
        )
    )
    return decision, bundle, plan, slots, verified_slots, required_ids


def _runtime_conflict_authority(
    decision: dict[str, Any],
    *,
    bundle: dict[str, Any],
    plan: dict[str, Any],
    slots: list[dict[str, Any]],
    verified_slots: list[dict[str, Any]],
    required_ids: list[str],
    engine_label: str,
) -> dict[str, Any]:
    conflict = decision.get("authoritative_conflict")
    conflict = conflict if isinstance(conflict, dict) else {}
    claim_results = records(decision.get("claim_results"))
    quote_status = _conflict_quote_identity_status(
        conflict,
        records(bundle.get("items")),
    )
    slot_ids = [str(slot.get("slot_id") or "") for slot in slots]
    complete = bool(
        engine_label == "unanswerable"
        and decision.get("action") == "abstain"
        and decision.get("reason") == "authoritative_conflict_abstention"
        and decision.get("canonical_answer_polarity") == ""
        and decision.get("boolean_authority_status") == "verified_conflict"
        and plan.get("stage") == "verified"
        and plan.get("state_authority") == BOOLEAN_AUTHORITATIVE_CONFLICT_CONTRACT
        and slots
        and len(verified_slots) == len(slots)
        and all(slot.get("status") == "verified_conflict" for slot in slots)
        and authoritative_conflict_complete(conflict)
        and set(conflict.get("required_slot_ids") or []) == set(slot_ids)
        and set(conflict.get("verified_required_slot_ids") or []) == set(slot_ids)
        and set(conflict.get("required_evidence_ids") or []) == set(required_ids)
        and quote_status == "bound"
        and _conflict_claim_result_complete(claim_results, conflict, slot_ids)
    )
    failure_kind = (
        ""
        if complete
        else (
            "ref_mismatch"
            if quote_status != "bound"
            else (
                "semantic_verifier"
                if decision.get("status") != "verified_conflict"
                else "authority_missing"
            )
        )
    )
    return {
        "complete": complete,
        "authority_kind": "authoritative_conflict",
        "status": "complete" if complete else "missing_or_inconsistent",
        "decision": decision,
        "plan": plan,
        "required_slot_ids": slot_ids,
        "required_evidence_ids": required_ids,
        "evidence_id": "",
        "evidence_ref": "",
        "quote": "",
        "quote_ref_validation_status": quote_status,
        "claim_results": claim_results,
        "authoritative_conflict": conflict,
        "failure_kind": failure_kind,
    }


def _conflict_quote_identity_status(
    conflict: dict[str, Any],
    items: list[dict[str, Any]],
) -> str:
    authorities = conflict_authorities(conflict)
    if not authorities:
        return "evidence_ref_quote_mismatch"
    for authority in authorities:
        item = _evidence_item_by_identity(
            items,
            str(authority.get("evidence_id") or ""),
        )
        if item is None or not conflict_authority_matches_item(authority, item):
            return "evidence_ref_quote_mismatch"
    return "bound"


def _conflict_claim_result_complete(
    claim_results: list[dict[str, Any]],
    conflict: dict[str, Any],
    slot_ids: list[str],
) -> bool:
    matches = [
        result
        for result in claim_results
        if result.get("status") == "conflicting"
        and result.get("authority_status") == "verified_conflict"
        and result.get("verified_slot_state") == "verified_conflict"
        and result.get("authoritative_conflict") == conflict
        and set(result.get("verified_support_slot_ids") or []) == set(slot_ids)
    ]
    return len(matches) == 1 and len(claim_results) == 1


def _authority_state_complete(
    decision: dict[str, Any],
    *,
    plan: dict[str, Any],
    slots: list[dict[str, Any]],
    verified_slots: list[dict[str, Any]],
    required_ids: list[str],
    evidence_id: str,
    evidence_ref: str,
    quote_status: str,
    claim_results: list[dict[str, Any]],
    engine_label: str,
) -> bool:
    decision_frame = typed_boolean_authority_frame_complete(
        decision,
        expected_polarity=engine_label,
        evidence_id=evidence_id,
    )
    supported_claim = any(
        result.get("status") == "supported"
        and evidence_id in (result.get("supporting_evidence_ids") or [])
        and typed_boolean_authority_frame_complete(
            result,
            expected_polarity=engine_label,
            evidence_id=evidence_id,
            require_exact=True,
        )
        for result in claim_results
    )
    return bool(
        engine_label in {"yes", "no"}
        and decision.get("status") == "supported"
        and decision.get("canonical_answer_polarity") == engine_label
        and decision.get("boolean_authority_status") == "verified_support"
        and plan.get("stage") == "verified"
        and plan.get("state_authority") == "verified_claim_support.v1"
        and slots
        and len(verified_slots) == len(slots)
        and evidence_id in required_ids
        and evidence_ref
        and quote_status == "bound"
        and decision_frame
        and supported_claim
    )


def _runtime_authority_failure_kind(
    decision: dict[str, Any],
    *,
    engine_label: str,
    slots: list[dict[str, Any]],
    required_ids: list[str],
    evidence_id: str,
    claim_results: list[dict[str, Any]],
    quote_status: str,
    complete: bool,
) -> str:
    if not slots or not required_ids or not evidence_id:
        return "authority_missing"
    if decision.get("status") != "supported" or (
        decision.get("canonical_answer_polarity") != engine_label
    ):
        return "semantic_verifier"
    claim_reasons = " ".join(
        str(result.get("reason") or "") for result in claim_results
    ).lower()
    if any(
        marker in claim_reasons
        for marker in ("scope", "cited_work", "current_paper", "quantified", "actor")
    ):
        return "scope"
    if quote_status != "bound":
        return "ref_mismatch"
    return "" if complete else "authority_missing"


def _evidence_item_by_identity(
    items: list[dict[str, Any]],
    evidence_id: str,
) -> dict[str, Any] | None:
    if not evidence_id:
        return None
    matches = []
    for item in items:
        try:
            if identity_of(item).key == evidence_id:
                matches.append(item)
        except ValueError:
            continue
    return matches[0] if len(matches) == 1 else None


def _quote_identity_status(
    item: dict[str, Any] | None,
    quote: str,
    start: Any,
    end: Any,
) -> str:
    if item is None or not quote:
        return "evidence_ref_quote_mismatch"
    text = "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )
    if text.count(quote) != 1:
        return "evidence_ref_quote_mismatch"
    if not isinstance(start, int) or not isinstance(end, int):
        return "evidence_ref_quote_mismatch"
    return "bound" if text[start:end] == quote else "evidence_ref_quote_mismatch"


def records(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]
