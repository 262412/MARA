from __future__ import annotations

import hashlib
import json
from typing import Any

from scripts.slurm.qasper_debug_contract_identity import _normalized_candidate
from scripts.slurm.qasper_debug_contract_support import (
    _CANDIDATE_VERIFIER_AUDIT_CONTRACT,
    _controlled_negative_safe_abstention_allowed,
    _mapping,
)
from scripts.slurm.qasper_slot_reference_audit import (
    _canonical_parent_span_ref,
    _canonical_slot_span_ref,
    _child_span_contained,
    _child_span_identity,
    _parent_span_identity,
    _parse_parent_span_ref,
    _parse_slot_span_ref,
    _parsed_parent_span_refs,
    _projected_slot_evidence_children,
)

_PROPOSITION_BINDING_SLOTS = {"actor", "predicate", "object", "quantifier"}


def _candidate_audit_complete(
    verifier: dict[str, Any],
    audit: dict[str, Any],
) -> bool:
    candidate = _normalized_candidate(verifier.get("candidate_label"))
    relation = str(verifier.get("candidate_verification_status") or "")
    base_complete = bool(
        audit.get("contract_id") == _CANDIDATE_VERIFIER_AUDIT_CONTRACT
        and audit.get("status") in {"passed", "failed"}
        and audit.get("mode")
        and audit.get("mode") != "deterministic_schema_audit"
        and audit.get("audited_candidate") == candidate
        and audit.get("audited_judgment") == relation
        and audit.get("replacement_candidate_allowed") is False
        and str(audit.get("reason") or "").strip()
    )
    if not base_complete or audit.get("status") == "failed":
        return base_complete
    if relation != "unknown" and audit.get("mode") != "candidate_bound_unknown_audit":
        return True
    return _unknown_audit_premises_complete(verifier, audit, candidate)


def _unknown_audit_premises_complete(
    verifier: dict[str, Any],
    audit: dict[str, Any],
    candidate: str,
) -> bool:
    conclusion = audit.get("audited_typed_conclusion")
    if not isinstance(conclusion, dict) or not conclusion:
        return False
    if conclusion.get("polarity") != candidate:
        return False
    premises = _normalized_audited_premises(audit.get("audited_premises"))
    if not premises or audit.get("audited_premises") != premises:
        return False
    if audit.get("audited_premise_digest") != _premise_digest(premises):
        return False
    evidence_ids = [item["evidence_id"] for item in premises]
    if audit.get("reviewed_evidence_ids") != evidence_ids:
        return False
    assessment = _mapping(verifier.get("unknown_assessment"))
    reviewed = _normalized_audited_premises(assessment.get("reviewed_evidence"))
    if not reviewed or reviewed != premises:
        return False
    known_ids = _known_evidence_ids(verifier)
    return bool(known_ids and set(evidence_ids) <= known_ids)


def _normalized_audited_premises(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not value:
        return []
    premises: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            return []
        premise = {
            "span_selector": str(item.get("span_selector") or ""),
            "evidence_id": str(item.get("evidence_id") or ""),
            "quote": str(item.get("quote") or ""),
            "span_start": item.get("span_start"),
            "span_end": item.get("span_end"),
        }
        if (
            not premise["span_selector"]
            or not premise["evidence_id"]
            or not premise["quote"]
            or not isinstance(premise["span_start"], int)
            or not isinstance(premise["span_end"], int)
            or premise["span_end"] <= premise["span_start"]
        ):
            return []
        premises.append(premise)
    return premises


def _premise_digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _known_evidence_ids(verifier: dict[str, Any]) -> set[str]:
    evidence_map = _mapping(verifier.get("evidence_label_map"))
    return {
        str(evidence_id).strip()
        for evidence_id in evidence_map.values()
        if str(evidence_id).strip()
    }


def _typed_conclusion_present(
    verifier: dict[str, Any],
    audit: dict[str, Any],
) -> bool:
    candidates = [
        verifier.get("typed_conclusion"),
        verifier.get("audited_typed_conclusion"),
        audit.get("typed_conclusion"),
        audit.get("audited_typed_conclusion"),
    ]
    debug = _mapping(verifier.get("debug_trace"))
    events = debug.get("events")
    events = events if isinstance(events, list) else []
    for event in reversed(events):
        if not isinstance(event, dict) or event.get("event") != "model_transaction":
            continue
        candidates.append(_mapping(event.get("outcome")).get("typed_conclusion"))
        transaction = _mapping(event.get("transaction"))
        candidates.extend(
            [
                transaction.get("typed_conclusion"),
                transaction.get("audited_typed_conclusion"),
            ]
        )
    return any(isinstance(value, dict) and bool(value) for value in candidates)


def _semantic_audit_failure_flags(
    verifier: dict[str, Any],
    audit: dict[str, Any],
    prediction: dict[str, Any],
) -> tuple[bool, bool]:
    """Classify semantic-audit failure/rejection without hiding safe negatives."""

    if audit.get("status") == "failed" and _controlled_negative_safe_abstention_allowed(
        verifier, prediction
    ):
        return False, False
    statuses: list[str] = []
    reasons: list[str] = []
    for field in (
        "audit_status",
        "runtime_semantic_entailment_audit_status",
        "semantic_entailment_audit_status",
    ):
        value = str(verifier.get(field) or "").strip().casefold()
        if value:
            statuses.append(value)
    for field in (
        "audit_reason",
        "audit_parse_failure_reason",
        "audit_provider_failure_reason",
        "runtime_semantic_entailment_audit_reason",
        "semantic_entailment_audit_reason",
    ):
        value = str(verifier.get(field) or "").strip().casefold()
        if value:
            reasons.append(value)
    for field in ("entailment_audit", "semantic_entailment_audit"):
        nested = _mapping(verifier.get(field))
        status = str(nested.get("status") or "").strip().casefold()
        reason = str(nested.get("reason") or "").strip().casefold()
        if status:
            statuses.append(status)
        if reason:
            reasons.append(reason)
    for nested in (audit, _mapping(verifier.get("candidate_verification_audit"))):
        status = str(nested.get("status") or "").strip().casefold()
        reason = str(nested.get("reason") or "").strip().casefold()
        if status:
            statuses.append(status)
        if reason:
            reasons.append(reason)
    debug = _mapping(verifier.get("debug_trace"))
    events = debug.get("events")
    events = events if isinstance(events, list) else []
    for event in events:
        if not isinstance(event, dict) or event.get("event") != "model_transaction":
            continue
        outcome = _mapping(event.get("outcome"))
        status = str(outcome.get("audit_status") or "").strip().casefold()
        reason = str(outcome.get("audit_reason") or "").strip().casefold()
        if status:
            statuses.append(status)
        if reason:
            reasons.append(reason)
    rejected = any(
        status in {"rejected", "audit_rejected", "semantic_rejected"}
        or "rejected" in status
        or "rejection" in status
        or "rejected" in reason
        or "rejection" in reason
        for status in statuses
        for reason in reasons or [""]
    )
    failed = any(
        status in {"failed", "provider_failed", "parse_failed", "audit_failed"}
        or "failed" in status
        or "failure" in status
        or "provider" in reason
        or "invalid" in reason
        or "truncated" in reason
        for status in statuses
        for reason in reasons or [""]
    )
    return failed, rejected


def _supported_row_required_slot_unverified(
    verifier: dict[str, Any],
    audit: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    if (
        verifier.get("candidate_verification_status")
        not in {"supported", "contradicted"}
        or audit.get("status") != "passed"
    ):
        return False
    return _required_slot_state_unverified(verifier, audit, metadata)


def _required_slot_state_unverified(
    verifier: dict[str, Any],
    audit: dict[str, Any],
    metadata: dict[str, Any],
) -> bool:
    generation = _mapping(metadata.get("qasper_candidate_generation"))
    required: set[str] = set()
    verified: set[str] = set()
    for source in (generation, verifier, audit):
        for field in (
            "required_slot_ids",
            "verifier_required_slot_ids",
            "required_slots",
        ):
            required.update(_slot_ids(source.get(field)))
        for field in ("verified_slot_ids", "verified_support_slot_ids"):
            verified.update(_string_set(source.get(field)))
    for slot in generation.get("required_slots") or []:
        if isinstance(slot, dict):
            slot_id = str(slot.get("slot_id") or "").strip()
            if slot_id:
                required.add(slot_id)
    semantic_authority = _mapping(metadata.get("semantic_proposition_authority"))
    authority = _mapping(metadata.get("typed_authority"))
    authority.update(_mapping(verifier.get("typed_authority")))
    required.update(_string_set(authority.get("required_slot_ids")))
    verified.update(_string_set(authority.get("verified_slot_ids")))
    verified.update(_string_set(authority.get("verified_support_slot_ids")))
    required.update(_string_set(semantic_authority.get("required_slot_ids")))
    verified.update(_string_set(semantic_authority.get("verified_slot_ids")))
    verified.update(_string_set(semantic_authority.get("verified_support_slot_ids")))
    if _proposition_binding_state_unverified(verifier, semantic_authority):
        return True
    if not required:
        return True
    return not required <= verified


def _proposition_binding_state_unverified(
    verifier: dict[str, Any],
    authority: dict[str, Any],
) -> bool:
    proposition = _mapping(verifier.get("question_proposition")) or _mapping(
        authority.get("question_proposition")
    )
    quantifier = " ".join(str(proposition.get("quantifier") or "").casefold().split())
    if not quantifier:
        return True
    not_applicable = {"quantifier"} if quantifier == "none" else set()
    required_proposition_slots = _PROPOSITION_BINDING_SLOTS - not_applicable
    bindings = _mapping(authority.get("proposition_slot_bindings"))
    verdict = str(verifier.get("verdict") or "").strip().casefold()
    expected_relation = {
        "yes": "proposition_support",
        "no": "explicit_contradiction",
    }.get(verdict)
    if (
        authority.get("status") != "verified"
        or _string_set(authority.get("required_proposition_slots"))
        != required_proposition_slots
        or _string_set(authority.get("not_applicable_proposition_slots"))
        != not_applicable
        or set(bindings) != required_proposition_slots
        or any(not str(bindings[slot] or "").strip() for slot in bindings)
        or expected_relation is None
        or authority.get("evidence_relation") != expected_relation
    ):
        return True
    return not _proposition_binding_evidence_valid(
        authority,
        required_proposition_slots=required_proposition_slots,
        not_applicable_proposition_slots=not_applicable,
        bindings=bindings,
        expected_relation=expected_relation,
    )


def _proposition_binding_evidence_valid(
    authority: dict[str, Any],
    *,
    required_proposition_slots: set[str],
    not_applicable_proposition_slots: set[str],
    bindings: dict[str, Any],
    expected_relation: str,
) -> bool:
    """Validate parent quote spans and per-slot child spans independently."""

    parent_refs = authority.get("proposition_binding_evidence_set_refs")
    parsed_parents = _parsed_parent_span_refs(parent_refs)
    if parsed_parents is None:
        return False
    parent_identities = {_parent_span_identity(parsed) for parsed in parsed_parents}

    raw_slot_refs = authority.get("proposition_slot_evidence_refs")
    if (
        not isinstance(raw_slot_refs, dict)
        or set(raw_slot_refs) != required_proposition_slots
    ):
        return False
    declared_children: dict[str, dict[tuple[Any, ...], str]] = {}
    for slot in sorted(required_proposition_slots):
        refs = raw_slot_refs.get(slot)
        if not isinstance(refs, list) or not refs:
            return False
        parsed_refs = [_parse_slot_span_ref(value) for value in refs]
        if any(parsed is None for parsed in parsed_refs):
            return False
        children: dict[tuple[Any, ...], str] = {}
        for raw_ref, parsed in zip(refs, parsed_refs):
            assert parsed is not None
            parent_ref, parsed_slot, start, end = parsed
            parent = _parse_parent_span_ref(parent_ref)
            if (
                parent is None
                or parsed_slot != slot
                or _parent_span_identity(parent) not in parent_identities
                or not _child_span_contained(parent, start, end)
            ):
                return False
            identity = _child_span_identity(parent, parsed_slot, start, end)
            canonical_ref = _canonical_slot_span_ref(parent, parsed_slot, start, end)
            if identity in children or raw_ref != canonical_ref:
                return False
            children[identity] = canonical_ref
        declared_children[slot] = children

    slot_evidence = authority.get("proposition_slot_evidence")
    projected_children = _projected_slot_evidence_children(
        slot_evidence,
        required_proposition_slots=required_proposition_slots,
        parent_identities=parent_identities,
    )
    if projected_children is None:
        return False
    if set(projected_children) != set(required_proposition_slots):
        return False
    if any(
        projected_children[slot] != declared_children[slot]
        for slot in required_proposition_slots
    ):
        return False

    digest = _proposition_binding_digest(
        expected_relation,
        bindings,
        declared_children,
        parsed_parents,
        not_applicable_proposition_slots,
    )
    return authority.get("proposition_evidence_set_digest") == digest


def _proposition_binding_digest(
    expected_relation: str,
    bindings: dict[str, Any],
    declared_children: dict[str, dict[tuple[Any, ...], str]],
    parsed_parents: list[tuple[str, int, int]],
    not_applicable_proposition_slots: set[str],
) -> str:
    payload = {
        "evidence_relation": expected_relation,
        "proposition_slot_bindings": bindings,
        "proposition_slot_evidence_refs": {
            slot: sorted(declared_children[slot].values())
            for slot in sorted(declared_children)
        },
        "proposition_binding_evidence_set_refs": sorted(
            _canonical_parent_span_ref(parsed) for parsed in parsed_parents
        ),
        "not_applicable_proposition_slots": sorted(not_applicable_proposition_slots),
    }
    return _premise_digest(payload)


def _slot_ids(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    output: set[str] = set()
    for item in value:
        if isinstance(item, dict):
            slot_id = str(item.get("slot_id") or "").strip()
            if slot_id:
                output.add(slot_id)
        else:
            slot_id = str(item or "").strip()
            if slot_id:
                output.add(slot_id)
    return output


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {str(item).strip() for item in value if str(item).strip()}


def _nonempty_mapping_keys(value: Any) -> set[str]:
    if not isinstance(value, dict):
        return set()
    return {
        str(key).strip()
        for key, bound in value.items()
        if str(key).strip() and bool(bound)
    }
