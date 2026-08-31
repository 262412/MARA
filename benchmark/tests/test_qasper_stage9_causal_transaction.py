from __future__ import annotations

from copy import deepcopy

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import qasper_causal_transaction
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
    prediction, context = _semantic_response_replay_fixture()

    replay = natural_causal_transaction_replay(prediction, context)

    assert replay["status"] == "matched"
    assert replay["through_stage_index"] == 9
    reference = replay["reference_transaction"]["stages"][8]
    local = replay["local_replay_transaction"]["stages"][8]
    assert reference["status"] == "complete"
    assert local["status"] == "complete"
    assert local["comparison_digest"] == reference["comparison_digest"]


def test_stage_nine_rejects_a_self_consistent_but_nonlocal_proposal_input() -> None:
    prediction, context = _semantic_response_replay_fixture()
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    transaction = verifier["debug_trace"]["events"][0]["transaction"]
    forged = deepcopy(transaction["proposal_input"])
    forged["question"] = "A forged verifier question"
    transaction["proposal_input"] = forged
    transaction["proposal_input_digest"] = canonical_digest(forged)

    replay = natural_causal_transaction_replay(prediction, context)

    assert replay["status"] == "failed"
    comparison = replay["comparison"]
    assert comparison["first_divergence"]["stage_index"] == 9
    assert comparison["later_stages_evaluated"] is False
    local = replay["local_replay_transaction"]["stages"][8]
    assert "semantic_proposal_question_mismatch" in local["incompleteness_reasons"]
