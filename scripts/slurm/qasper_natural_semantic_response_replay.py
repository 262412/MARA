from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_validation import (
    premise_slot_evidence_for_audit,
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_candidate_unknown_audit import parse_candidate_unknown_audit
from ktem.reasoning.mara_qasper_semantic_pack import (
    qasper_canonical_evidence_plans,
    qasper_canonical_selector_bindings,
)
from ktem.reasoning.mara_semantic_entailment_audit import (
    parse_semantic_entailment_audit,
)
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from scripts.slurm.qasper_natural_semantic_io_replay import (
    semantic_io_replay_observation,
)

_VERIFIER_FIELDS = (
    "contract_id",
    "status",
    "reason",
    "audit_reason",
    "candidate_verification_status",
    "proposal_status",
    "audit_status",
    "model",
    "audit_model",
    "auditor_relationship",
    "proposal_model_call_count",
    "audit_model_call_count",
    "actual_model_call_count",
)


def replay_frozen_semantic_verifier(
    online_verifier: Mapping[str, Any],
    *,
    question: str,
    bundle: Any,
    slots: list[dict[str, Any]],
    binding: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
    local_lineage: Mapping[str, Any],
) -> dict[str, Any]:
    verifier = {
        field: deepcopy(online_verifier.get(field)) for field in _VERIFIER_FIELDS
    }
    verifier["semantic_data_lineage"] = deepcopy(dict(local_lineage))
    event = _latest_model_event(online_verifier)
    if not event:
        verifier["semantic_response_replay"] = _no_event_observation(online_verifier)
        return verifier
    replayed_event, observation = _replay_event(
        event,
        question=question,
        bundle=bundle,
        slots=slots,
        binding=binding,
        candidate_generation=candidate_generation,
    )
    verifier["debug_trace"] = {
        "contract_id": "semantic_proposition_debug_trace.v3",
        "event_count": 1,
        "dropped_event_count": 0,
        "events": [replayed_event],
    }
    verifier["semantic_response_replay"] = observation
    verifier["semantic_io_replay"] = semantic_io_replay_observation(
        replayed_event,
        question=question,
        bundle=bundle,
        slots=slots,
        candidate_generation=candidate_generation,
    )
    return verifier


def _latest_model_event(verifier: Mapping[str, Any]) -> dict[str, Any]:
    trace = _mapping(verifier.get("debug_trace"))
    for event in reversed(trace.get("events") or []):
        if isinstance(event, Mapping) and event.get("event") == "model_transaction":
            return deepcopy(dict(event))
    return {}


def _no_event_observation(verifier: Mapping[str, Any]) -> dict[str, Any]:
    status = str(verifier.get("status") or "")
    reasons = (
        []
        if status == "not_run_after_candidate_response_replay"
        else ["semantic_model_event_missing"]
    )
    return _observation(reasons, frozen={}, replayed={})


def _replay_event(
    event: dict[str, Any],
    *,
    question: str,
    bundle: Any,
    slots: list[dict[str, Any]],
    binding: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    frozen = _mapping(event.get("transaction"))
    if not frozen:
        reasons = _typed_empty_transaction_reasons(event)
        return event, _observation(reasons, frozen=frozen, replayed=frozen)
    replayed, reasons = _replay_transaction(
        frozen,
        event=event,
        question=question,
        bundle=bundle,
        slots=slots,
        binding=binding,
        candidate_generation=candidate_generation,
    )
    event["transaction"] = replayed
    return event, _observation(reasons, frozen=frozen, replayed=replayed)


def _typed_empty_transaction_reasons(event: Mapping[str, Any]) -> list[str]:
    outcome = _mapping(event.get("outcome"))
    return (
        []
        if (
            outcome.get("status") == "failed"
            and outcome.get("reason")
            and outcome.get("audit_status") == "not_started"
        )
        else ["semantic_empty_transaction_without_typed_stop"]
    )


def _replay_transaction(
    frozen: Mapping[str, Any],
    *,
    event: Mapping[str, Any],
    question: str,
    bundle: Any,
    slots: list[dict[str, Any]],
    binding: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    replayed = deepcopy(dict(frozen))
    proposal, proposal_value, reasons = _replay_proposal(
        _mapping(frozen.get("proposal")),
        bundle=bundle,
        slots=slots,
        binding=binding,
        candidate_generation=candidate_generation,
        model=str(frozen.get("proposal_model") or ""),
    )
    replayed["proposal"] = proposal
    audit, audit_reasons = _replay_audit(
        _mapping(frozen.get("audit")),
        proposal_value=proposal_value,
        question=question,
        auditor_relationship=str(event.get("auditor_relationship") or ""),
        candidate_generation=candidate_generation,
    )
    replayed["audit"] = audit
    reasons.extend(audit_reasons)
    return replayed, reasons


def _replay_proposal(
    frozen: Mapping[str, Any],
    *,
    bundle: Any,
    slots: list[dict[str, Any]],
    binding: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
    model: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    replayed = deepcopy(dict(frozen))
    records = list(
        getattr(bundle, "metadata", {})
        .get("qasper_canonical_semantic_pack", {})
        .get("records")
        or []
    )
    plans = qasper_canonical_evidence_plans(bundle) or {}
    slot_ids = {str(slot.get("slot_id") or "") for slot in slots}
    attempts = []
    reasons: list[str] = []
    final_value = None
    for attempt in frozen.get("attempts") or []:
        replayed_attempt, value, attempt_reasons = _reparse_proposal_attempt(
            _mapping(attempt),
            records=records,
            slots=slots,
            slot_ids=slot_ids,
            binding=binding,
            plans=plans,
            candidate_generation=candidate_generation,
            model=model,
        )
        attempts.append(replayed_attempt)
        reasons.extend(attempt_reasons)
        final_value = value
    replayed["attempts"] = attempts
    reasons.extend(_stage_shape_reasons("proposal", frozen, replayed))
    return replayed, final_value, reasons


def _reparse_proposal_attempt(
    frozen: dict[str, Any],
    *,
    records: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    slot_ids: set[str],
    binding: Mapping[str, Any],
    plans: Mapping[str, Mapping[str, Any]],
    candidate_generation: Mapping[str, Any],
    model: str,
) -> tuple[dict[str, Any], dict[str, Any] | None, list[str]]:
    replayed = deepcopy(frozen)
    raw = str(frozen.get("raw_response") or "")
    if not raw:
        return replayed, None, _missing_attempt_reasons("proposal", frozen)
    parsed = parse_semantic_proposition_response(
        raw,
        packed=records,
        slot_ids=slot_ids,
        model=model,
        seed=_attempt_seed(frozen, candidate_generation),
        candidate=str(candidate_generation.get("typed_candidate") or ""),
        applicable_proposition_slots=tuple(binding.get("applicable_slots") or ()),
        allowed_proposition_slot_bindings=qasper_canonical_selector_bindings(records),
        slot_evidence_refs=_slot_evidence_refs(slots),
        allowed_proposition_evidence_plans=plans,
    )
    replayed["parsed_value"] = deepcopy(parsed.value)
    replayed["parse_failure_reason"] = str(parsed.failure_reason or "")
    reasons = _parsed_attempt_reasons("proposal", frozen, replayed)
    return replayed, deepcopy(parsed.value), reasons


def _replay_audit(
    frozen: Mapping[str, Any],
    *,
    proposal_value: Mapping[str, Any] | None,
    question: str,
    auditor_relationship: str,
    candidate_generation: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    replayed = deepcopy(dict(frozen))
    attempts = list(frozen.get("attempts") or [])
    if not attempts:
        return replayed, []
    if proposal_value is None:
        return replayed, ["semantic_audit_without_local_proposal"]
    unknown_audit = proposal_value.get("verdict") == "insufficient_evidence"
    expectations: dict[str, tuple[str, ...]] = {}
    evidence: dict[str, dict[str, Any]] = {}
    if not unknown_audit:
        expectations, evidence = _audit_parse_inputs(
            proposal_value,
            question=question,
            auditor_relationship=auditor_relationship,
        )
    replayed_attempts = []
    reasons: list[str] = []
    for attempt in attempts:
        replayed_attempt, attempt_reasons = _reparse_audit_attempt(
            _mapping(attempt),
            expectations=expectations,
            evidence=evidence,
            proposal_value=proposal_value,
            candidate_generation=candidate_generation,
        )
        replayed_attempts.append(replayed_attempt)
        reasons.extend(attempt_reasons)
    replayed["attempts"] = replayed_attempts
    reasons.extend(_stage_shape_reasons("audit", frozen, replayed))
    return replayed, reasons


def _audit_parse_inputs(
    proposal: Mapping[str, Any],
    *,
    question: str,
    auditor_relationship: str,
) -> tuple[dict[str, tuple[str, ...]], dict[str, dict[str, Any]]]:
    premises = [
        dict(premise)
        for premise in proposal.get("premises") or []
        if isinstance(premise, Mapping)
    ]
    expectations = {
        f"P{index}": tuple(
            str(slot) for slot in premise.get("binds_proposition_slots") or []
        )
        for index, premise in enumerate(premises, start=1)
    }
    constraint = semantic_relation_evidence_set_constraint(
        premises,
        build_question_proposition(question),
        str(proposal.get("verdict") or ""),
        auditor_relationship=auditor_relationship,
    )
    return expectations, premise_slot_evidence_for_audit(constraint)


def _reparse_audit_attempt(
    frozen: dict[str, Any],
    *,
    expectations: Mapping[str, tuple[str, ...]],
    evidence: Mapping[str, Mapping[str, Any]],
    proposal_value: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    replayed = deepcopy(frozen)
    raw = str(frozen.get("raw_response") or "")
    if not raw:
        return replayed, _missing_attempt_reasons("audit", frozen)
    parsed: Any
    if proposal_value.get("verdict") == "insufficient_evidence":
        parsed = parse_candidate_unknown_audit(
            raw,
            candidate=str(candidate_generation.get("typed_candidate") or ""),
            verifier_judgment=str(proposal_value.get("candidate_judgment") or ""),
        )
    else:
        parsed = parse_semantic_entailment_audit(
            raw,
            premise_labels=list(expectations),
            premise_slot_expectations=expectations,
            premise_slot_evidence=evidence,
        )
    replayed["parsed_value"] = deepcopy(parsed.value)
    replayed["parse_failure_reason"] = str(parsed.failure_reason or "")
    return replayed, _parsed_attempt_reasons("audit", frozen, replayed)


def _missing_attempt_reasons(stage: str, attempt: Mapping[str, Any]) -> list[str]:
    return (
        []
        if attempt.get("provider_failure_reason")
        else [f"semantic_{stage}_raw_response_missing"]
    )


def _parsed_attempt_reasons(
    stage: str,
    frozen: Mapping[str, Any],
    replayed: Mapping[str, Any],
) -> list[str]:
    reasons = []
    if frozen.get("parsed_value") != replayed.get("parsed_value"):
        reasons.append(f"semantic_{stage}_parser_replay_mismatch")
    if frozen.get("parse_failure_reason") != replayed.get("parse_failure_reason"):
        reasons.append(f"semantic_{stage}_parse_reason_mismatch")
    return reasons


def _stage_shape_reasons(
    stage: str,
    frozen: Mapping[str, Any],
    replayed: Mapping[str, Any],
) -> list[str]:
    attempts = list(replayed.get("attempts") or [])
    attempt_ids = [
        str(_mapping(attempt).get("attempt_id") or "") for attempt in attempts
    ]
    reasons = []
    if "attempt_ids" in frozen and frozen.get("attempt_ids") != attempt_ids:
        reasons.append(f"semantic_{stage}_attempt_ids_mismatch")
    if "call_count" in frozen and frozen.get("call_count") != len(attempts):
        reasons.append(f"semantic_{stage}_call_count_mismatch")
    return reasons


def _attempt_seed(
    attempt: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
) -> int:
    snapshot = _mapping(attempt.get("request_snapshot"))
    parameters = _mapping(snapshot.get("parameters"))
    value = parameters.get("seed", candidate_generation.get("effective_seed", 0))
    return int(value or 0)


def _slot_evidence_refs(
    slots: list[dict[str, Any]],
) -> dict[str, tuple[str, ...]]:
    return {
        str(slot.get("slot_id") or ""): tuple(
            str(ref) for ref in slot.get("evidence_refs") or ()
        )
        for slot in slots
        if str(slot.get("slot_id") or "")
    }


def _observation(
    reasons: list[str],
    *,
    frozen: Mapping[str, Any],
    replayed: Mapping[str, Any],
) -> dict[str, Any]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return {
        "contract_id": "qasper_frozen_semantic_response_replay.v1",
        "status": "matched" if not unique else "failed",
        "reasons": unique,
        "frozen_transaction_digest": canonical_digest(frozen),
        "replayed_transaction_digest": canonical_digest(replayed),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
