from __future__ import annotations

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
from ktem.reasoning.mara_semantic_entailment_audit import (
    semantic_entailment_audit_prompt,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    semantic_proposition_verifier_prompt,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.qasper_terminal_projection_fixture import (
    attach_valid_terminal_projection,
)
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)
from benchmark.tests.test_qasper_stage8_causal_transaction import (
    _semantic_response_replay_fixture,
)
from scripts.slurm.qasper_natural_causal_transaction import (
    natural_causal_transaction_replay,
)


def _typed_pre_audit_stop() -> tuple[dict, dict]:
    prediction, debug_row = _prediction_and_debug_row()
    verifier = debug_row["semantic_verifier"]
    event = verifier["debug_trace"]["events"][0]
    event["auditor_relationship"] = "distinct_instance_same_model"
    event["transaction"] = {}
    event["outcome"] = {
        "status": "failed",
        "reason": "release_conclusion_auditor_not_independent",
        "audit_status": "not_started",
        "audit_reason": "release_conclusion_auditor_not_independent",
    }
    verifier.update(
        status="failed",
        reason="release_conclusion_auditor_not_independent",
        audit_reason="release_conclusion_auditor_not_independent",
        auditor_relationship="distinct_instance_same_model",
        candidate_verification_status="pre_audit_failed",
        proposal_status="not_started",
        audit_status="not_started",
        proposal_model_call_count=0,
        audit_model_call_count=0,
        actual_model_call_count=0,
    )
    return prediction, debug_row


def _current_semantic_io_fixture() -> tuple[dict, object]:
    prediction, context = _semantic_response_replay_fixture()
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    event = verifier["debug_trace"]["events"][0]
    transaction = event["transaction"]
    pack = context.bundle.metadata["qasper_canonical_semantic_pack"]
    records = pack["records"]
    slots = context.slots
    for slot in slots:
        slot.setdefault("description", "complete proposition support")
    question = prediction["question"]
    proposition = build_question_proposition(question)
    resolution = resolve_question_proposition(question)
    identity = {
        "semantic_pack_digest": pack["semantic_pack_digest"],
        "span_universe_digest": pack["span_universe_digest"],
        "candidate_transaction_id": pack["candidate_transaction_id"],
    }
    proposal = transaction["proposal"]["attempts"][0]["parsed_value"]
    _attach_proposal_io(
        transaction,
        question=question,
        records=records,
        slots=slots,
        proposition=proposition,
        resolution=resolution,
        identity=identity,
    )
    _attach_audit_io(
        transaction,
        proposal=proposal,
        question=question,
        proposition=proposition,
        identity=identity,
    )
    event.update(
        question=question,
        question_proposition=proposition.as_dict(),
        packed_evidence=deepcopy(records),
        required_slots=deepcopy(slots),
    )
    attach_valid_terminal_projection(prediction)
    return prediction, context


def _attach_proposal_io(
    transaction: dict,
    *,
    question: str,
    records: list[dict],
    slots: list[dict],
    proposition: Any,
    resolution: Any,
    identity: dict[str, str],
) -> None:
    proposal_prompt = semantic_proposition_verifier_prompt(
        question,
        slots,
        [
            {
                **record,
                "label": record.get("label") or f"E{index}",
                "source_id": record.get("source_id") or record["evidence_id"],
                "page_label": record.get("page_label") or "",
                "section_id": record.get("section_id") or "",
            }
            for index, record in enumerate(records, start=1)
        ],
        candidate="yes",
    )
    proposal_request = {
        "messages": [
            {"role": "system", "content": "frozen verifier system prompt"},
            {"role": "user", "content": proposal_prompt},
        ],
        "parameters": {"seed": 0},
    }
    transaction["proposal"]["attempts"][0].update(
        request_snapshot=proposal_request,
        request_snapshot_digest=canonical_digest(proposal_request),
    )
    proposal_input = {
        "prompt": proposal_prompt,
        "question": question,
        "packed_evidence": records,
        "required_slots": slots,
        "question_proposition": proposition.as_dict(),
        "question_proposition_resolution": resolution.as_dict(),
        "semantic_pack_identity": identity,
        "model_requests": [proposal_request],
    }
    transaction["proposal_input"] = proposal_input
    transaction["proposal_input_digest"] = canonical_digest(proposal_input)


def _attach_audit_io(
    transaction: dict,
    *,
    proposal: dict,
    question: str,
    proposition: Any,
    identity: dict[str, str],
) -> None:
    premises = proposal["premises"]
    conclusion = typed_conclusion(proposition, proposal["verdict"])
    constraint = semantic_relation_evidence_set_constraint(
        premises,
        proposition,
        proposal["verdict"],
        auditor_relationship="distinct_model",
    )
    evidence = premise_slot_evidence_for_audit(constraint)
    audit_prompt = semantic_entailment_audit_prompt(
        proposition,
        conclusion,
        proposal["proof_mode"],
        premises,
        original_candidate="yes",
        candidate_judgment=proposal["candidate_judgment"],
        premise_slot_evidence=evidence,
        semantic_pack_identity=identity,
    )
    audit_request = {
        "messages": [
            {"role": "system", "content": "frozen auditor system prompt"},
            {"role": "user", "content": audit_prompt},
        ],
        "parameters": {"seed": 1},
    }
    transaction["audit"]["attempts"][0].update(
        request_snapshot=audit_request,
        request_snapshot_digest=canonical_digest(audit_request),
    )
    audit_input = {
        "prompt": audit_prompt,
        "question": question,
        "candidate_proposal": deepcopy(proposal),
        "typed_conclusion": conclusion.as_dict(),
        "premise_slot_evidence": evidence,
        "independent_semantic_constraint": constraint,
        "model_requests": [audit_request],
    }
    transaction["audit_input"] = audit_input
    transaction["audit_input_digest"] = canonical_digest(audit_input)


def test_stage_nine_accepts_an_explicit_zero_call_typed_pre_audit_stop() -> None:
    prediction, debug_row = _typed_pre_audit_stop()

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][8]

    assert stage["status"] == "complete"
    assert stage["incompleteness_reasons"] == []
    assert stage["payload"]["execution_state"] == {
        "disposition": "typed_pre_audit_stop",
        "stop_reason": "release_conclusion_auditor_not_independent",
        "auditor_relationship": "distinct_instance_same_model",
        "proposal_status": "not_started",
        "audit_status": "not_started",
        "proposal_model_call_count": 0,
        "audit_model_call_count": 0,
        "actual_model_call_count": 0,
    }
    assert stage["payload"]["proposal_input"] == {}
    assert stage["payload"]["audit_input"] == {}


def test_stage_nine_replays_the_frozen_verifier_and_auditor_io() -> None:
    prediction, context = _current_semantic_io_fixture()

    replay = natural_causal_transaction_replay(prediction, context, through_stage=9)

    assert replay["status"] == "matched"
    assert replay["through_stage_index"] == 9
    reference = replay["reference_transaction"]["stages"][8]
    local = replay["local_replay_transaction"]["stages"][8]
    assert reference["status"] == "complete"
    assert local["status"] == "complete"
    assert local["comparison_digest"] == reference["comparison_digest"]


def test_stage_nine_rejects_a_self_consistent_but_nonlocal_proposal_input() -> None:
    prediction, context = _current_semantic_io_fixture()
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    transaction = verifier["debug_trace"]["events"][0]["transaction"]
    forged = deepcopy(transaction["proposal_input"])
    forged["question"] = "A forged verifier question"
    transaction["proposal_input"] = forged
    transaction["proposal_input_digest"] = canonical_digest(forged)
    attach_valid_terminal_projection(prediction)

    replay = natural_causal_transaction_replay(prediction, context)

    assert replay["status"] == "failed"
    comparison = replay["comparison"]
    assert comparison["first_divergence"]["stage_index"] == 9
    assert comparison["later_stages_evaluated"] is False
    local = replay["local_replay_transaction"]["stages"][8]
    assert "semantic_proposal_question_mismatch" in local["incompleteness_reasons"]
