from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.question_proposition import (
    build_question_proposition,
    resolve_question_proposition,
    typed_conclusion,
)
from ktem.docqa.semantic_relation_clause_validation import (
    premise_slot_evidence_for_audit,
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_candidate_unknown_audit import candidate_unknown_audit_prompt
from ktem.reasoning.mara_semantic_entailment_audit import (
    semantic_entailment_audit_prompt,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    semantic_proposition_verifier_prompt,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest


def semantic_io_replay_observation(
    event: Mapping[str, Any],
    *,
    question: str,
    bundle: Any,
    slots: list[dict[str, Any]],
    candidate_generation: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate frozen verifier/auditor IO against locally frozen authority."""

    pack = _mapping(
        getattr(bundle, "metadata", {}).get("qasper_canonical_semantic_pack")
    )
    records = deepcopy(pack.get("records") or [])
    proposition = build_question_proposition(question)
    resolution = resolve_question_proposition(question)
    identity = _semantic_pack_identity(pack, candidate_generation)
    reasons = _event_input_reasons(
        event,
        question=question,
        records=records,
        slots=slots,
        proposition=proposition.as_dict(),
    )
    transaction = _mapping(event.get("transaction"))
    if not transaction:
        return _observation(
            reasons,
            mode="typed_pre_audit_stop",
            transaction=transaction,
        )

    proposal_input = _mapping(transaction.get("proposal_input"))
    proposal = _latest_parsed_value(_mapping(transaction.get("proposal")))
    reasons.extend(
        _proposal_input_reasons(
            transaction,
            proposal_input=proposal_input,
            question=question,
            records=records,
            slots=slots,
            proposition=proposition.as_dict(),
            resolution=resolution.as_dict(),
            identity=identity,
            candidate=str(candidate_generation.get("typed_candidate") or ""),
        )
    )
    audit = _mapping(transaction.get("audit"))
    if audit.get("attempts"):
        reasons.extend(
            _audit_input_reasons(
                transaction,
                audit_input=_mapping(transaction.get("audit_input")),
                proposal=proposal,
                question=question,
                proposition=proposition,
                identity=identity,
                candidate=str(candidate_generation.get("typed_candidate") or ""),
                auditor_relationship=str(event.get("auditor_relationship") or ""),
            )
        )
    return _observation(reasons, mode="model_transaction", transaction=transaction)


def _event_input_reasons(
    event: Mapping[str, Any],
    *,
    question: str,
    records: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    proposition: Mapping[str, Any],
) -> list[str]:
    reasons = []
    if str(event.get("question") or "") != question:
        reasons.append("semantic_event_question_mismatch")
    if event.get("question_proposition") != dict(proposition):
        reasons.append("semantic_event_question_proposition_mismatch")
    if event.get("packed_evidence") != records:
        reasons.append("semantic_event_packed_evidence_mismatch")
    if event.get("required_slots") != slots:
        reasons.append("semantic_event_required_slots_mismatch")
    return reasons


def _proposal_input_reasons(
    transaction: Mapping[str, Any],
    *,
    proposal_input: Mapping[str, Any],
    question: str,
    records: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    proposition: Mapping[str, Any],
    resolution: Mapping[str, Any],
    identity: Mapping[str, str],
    candidate: str,
) -> list[str]:
    if not proposal_input:
        return ["semantic_proposal_input_missing"]
    reasons = _input_digest_reasons(
        "proposal",
        proposal_input,
        transaction.get("proposal_input_digest"),
    )
    expected = {
        "question": question,
        "packed_evidence": records,
        "required_slots": slots,
        "question_proposition": dict(proposition),
        "question_proposition_resolution": dict(resolution),
        "semantic_pack_identity": dict(identity),
    }
    for field, value in expected.items():
        if proposal_input.get(field) != value:
            reasons.append(f"semantic_proposal_{field}_mismatch")
    try:
        prompt = semantic_proposition_verifier_prompt(
            question,
            _prompt_slots(slots),
            _prompt_records(records),
            candidate=candidate,
        )
    except (KeyError, ValueError):
        reasons.append("semantic_proposal_prompt_reconstruction_failed")
    else:
        if proposal_input.get("prompt") != prompt:
            reasons.append("semantic_proposal_prompt_mismatch")
    reasons.extend(
        _model_request_reasons(
            "proposal",
            proposal_input,
            _mapping(transaction.get("proposal")),
        )
    )
    return reasons


def _audit_input_reasons(
    transaction: Mapping[str, Any],
    *,
    audit_input: Mapping[str, Any],
    proposal: Mapping[str, Any],
    question: str,
    proposition: Any,
    identity: Mapping[str, str],
    candidate: str,
    auditor_relationship: str,
) -> list[str]:
    if not audit_input:
        return ["semantic_audit_input_missing"]
    reasons = _input_digest_reasons(
        "audit",
        audit_input,
        transaction.get("audit_input_digest"),
    )
    if audit_input.get("question") != question:
        reasons.append("semantic_audit_question_mismatch")
    if not _same_local_proposal(audit_input.get("candidate_proposal"), proposal):
        reasons.append("semantic_audit_candidate_proposal_mismatch")
    if proposal.get("verdict") == "insufficient_evidence":
        reasons.extend(
            _unknown_audit_input_reasons(
                audit_input,
                proposal=proposal,
                proposition=proposition,
                identity=identity,
                candidate=candidate,
            )
        )
    else:
        reasons.extend(
            _entailment_audit_input_reasons(
                audit_input,
                proposal=proposal,
                proposition=proposition,
                identity=identity,
                candidate=candidate,
                auditor_relationship=auditor_relationship,
            )
        )
    reasons.extend(
        _model_request_reasons(
            "audit",
            audit_input,
            _mapping(transaction.get("audit")),
        )
    )
    return reasons


def _entailment_audit_input_reasons(
    audit_input: Mapping[str, Any],
    *,
    proposal: Mapping[str, Any],
    proposition: Any,
    identity: Mapping[str, str],
    candidate: str,
    auditor_relationship: str,
) -> list[str]:
    premises = [
        dict(value)
        for value in proposal.get("premises") or []
        if isinstance(value, Mapping)
    ]
    conclusion = typed_conclusion(proposition, str(proposal.get("verdict") or ""))
    constraint = semantic_relation_evidence_set_constraint(
        premises,
        proposition,
        str(proposal.get("verdict") or ""),
        auditor_relationship=auditor_relationship,
    )
    evidence = premise_slot_evidence_for_audit(constraint)
    prompt = semantic_entailment_audit_prompt(
        proposition,
        conclusion,
        str(proposal.get("proof_mode") or ""),
        premises,
        original_candidate=candidate,
        candidate_judgment=str(proposal.get("candidate_judgment") or ""),
        premise_slot_evidence=evidence,
        semantic_pack_identity=identity,
    )
    expected = {
        "typed_conclusion": conclusion.as_dict(),
        "premise_slot_evidence": evidence,
        "independent_semantic_constraint": constraint,
        "prompt": prompt,
    }
    return [
        f"semantic_audit_{field}_mismatch"
        for field, value in expected.items()
        if audit_input.get(field) != value
    ]


def _unknown_audit_input_reasons(
    audit_input: Mapping[str, Any],
    *,
    proposal: Mapping[str, Any],
    proposition: Any,
    identity: Mapping[str, str],
    candidate: str,
) -> list[str]:
    assessment = _mapping(proposal.get("unknown_assessment"))
    try:
        prompt, conclusion = candidate_unknown_audit_prompt(
            proposition,
            candidate,
            assessment,
            verifier_judgment=str(proposal.get("candidate_judgment") or ""),
            semantic_pack_identity=identity,
        )
    except ValueError:
        return ["semantic_unknown_audit_input_reconstruction_failed"]
    expected = {
        "typed_conclusion": conclusion,
        "unknown_assessment": assessment,
        "semantic_pack_identity": dict(identity),
        "prompt": prompt,
    }
    return [
        f"semantic_audit_{field}_mismatch"
        for field, value in expected.items()
        if audit_input.get(field) != value
    ]


def _model_request_reasons(
    stage: str,
    stage_input: Mapping[str, Any],
    stage_output: Mapping[str, Any],
) -> list[str]:
    attempts = [
        _mapping(value)
        for value in stage_output.get("attempts") or []
        if isinstance(value, Mapping)
    ]
    requests = list(stage_input.get("model_requests") or [])
    if len(requests) != len(attempts):
        return [f"semantic_{stage}_model_request_count_mismatch"]
    reasons = []
    prompt = str(stage_input.get("prompt") or "")
    for index, (request, attempt) in enumerate(zip(requests, attempts), start=1):
        snapshot = _mapping(attempt.get("request_snapshot"))
        if request != snapshot:
            reasons.append(f"semantic_{stage}_request_{index}_snapshot_mismatch")
        if canonical_digest(snapshot) != attempt.get("request_snapshot_digest"):
            reasons.append(f"semantic_{stage}_request_{index}_digest_mismatch")
        messages = list(snapshot.get("messages") or [])
        if not messages or not str(
            _mapping(messages[-1]).get("content") or ""
        ).startswith(prompt):
            reasons.append(f"semantic_{stage}_request_{index}_prompt_mismatch")
    return reasons


def _input_digest_reasons(
    stage: str, value: Mapping[str, Any], digest: Any
) -> list[str]:
    return (
        []
        if canonical_digest(value) == digest
        else [f"semantic_{stage}_input_digest_mismatch"]
    )


def _semantic_pack_identity(
    pack: Mapping[str, Any],
    candidate_generation: Mapping[str, Any],
) -> dict[str, str]:
    return {
        "semantic_pack_digest": str(
            pack.get("semantic_pack_digest")
            or candidate_generation.get("canonical_semantic_pack_digest")
            or ""
        ),
        "span_universe_digest": str(
            pack.get("span_universe_digest")
            or candidate_generation.get("canonical_span_universe_digest")
            or ""
        ),
        "candidate_transaction_id": str(
            pack.get("candidate_transaction_id")
            or candidate_generation.get("canonical_pack_candidate_transaction_id")
            or ""
        ),
    }


def _prompt_slots(slots: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = deepcopy(slots)
    for value in values:
        value.setdefault("description", "")
    return values


def _prompt_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values = deepcopy(records)
    for index, value in enumerate(values, start=1):
        value.setdefault("label", f"E{index}")
        value.setdefault("source_id", str(value.get("evidence_id") or ""))
        value.setdefault("page_label", "")
        value.setdefault("section_id", "")
    return values


def _same_local_proposal(value: Any, proposal: Mapping[str, Any]) -> bool:
    observed = _mapping(value)
    fields = (
        "candidate_judgment",
        "canonical_evidence_plan_id",
        "verdict",
        "premises",
        "proof_mode",
        "evidence_relation",
        "unknown_assessment",
    )
    return all(observed.get(field) == proposal.get(field) for field in fields)


def _latest_parsed_value(stage: Mapping[str, Any]) -> dict[str, Any]:
    for attempt in reversed(stage.get("attempts") or []):
        parsed = _mapping(_mapping(attempt).get("parsed_value"))
        if parsed:
            return parsed
    return {}


def _observation(
    reasons: list[str],
    *,
    mode: str,
    transaction: Mapping[str, Any],
) -> dict[str, Any]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return {
        "contract_id": "qasper_frozen_semantic_io_replay.v1",
        "status": "matched" if not unique else "failed",
        "mode": mode,
        "reasons": unique,
        "transaction_digest": canonical_digest(transaction),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
