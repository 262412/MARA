from __future__ import annotations

from copy import deepcopy

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import (
    qasper_causal_transaction,
    qasper_causal_transaction_first_failure,
)
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)


def test_candidate_input_stage_marks_final_attempt_identity_divergence_first() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    projection = debug_row["main_candidate_generator"][
        "candidate_request_projection_trace"
    ]
    projection["decisions"].append(deepcopy(projection["decisions"][0]))
    projection["input_record_count"] = 2
    projection["decision_count"] = 2
    projection["selected_record_count"] = 2
    projection["decisions_digest"] = canonical_digest(projection["decisions"])

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
        origin="online",
    )
    stage = transaction["stages"][2]
    failure = qasper_causal_transaction_first_failure(transaction)

    assert stage["status"] == "incomplete"
    assert (
        "candidate_request_final_accepted_attempt_ids_mismatch"
        in stage["incompleteness_reasons"]
    )
    assert failure["stage_index"] == 3
    assert failure["stage"] == "candidate_input"
    assert failure["reason"] == "transaction_stage_incomplete"
    assert failure["producer_digest"] == canonical_digest(["evidence-1"])
    assert failure["validator_digest"] == canonical_digest(["evidence-1", "evidence-1"])
    assert failure["serializer_identity"] == "canonical_json_utf8_v1"
