from __future__ import annotations

from ktem.reasoning.mara_semantic_transaction_context import prepare_transaction

from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)
from benchmark.tests.test_qasper_stage9_causal_transaction import (
    _current_semantic_io_fixture,
)
from scripts.slurm.qasper_natural_causal_transaction import (
    natural_causal_transaction_replay,
)

QUESTION = "Does the model have attention?"
REPAIR = {
    "from": "question_proposition",
    "to": "proposition_repair",
    "reason": "question_proposition_predicate_unspecified",
    "outcome": "repaired",
}
SEMANTIC_STOP = {
    "from": "semantic_audit",
    "to": "stop_without_reverify",
    "reason": "local_semantic_relation_rejected",
    "outcome": "recovery_no_progress",
    "recovery_action": "stop_without_reverify",
    "evidence_digest_before": "a" * 64,
    "evidence_digest_after": "a" * 64,
    "evidence_digest_changed": False,
}


def _stage_ten(prediction: dict, debug_row: dict) -> dict:
    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    return transaction["stages"][9]


def test_stage_ten_projects_typed_proposition_repair_before_and_after() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    prediction["question"] = QUESTION
    debug_row["semantic_verifier"]["recovery_transitions"] = [dict(REPAIR)]

    stage = _stage_ten(prediction, debug_row)

    assert stage["status"] == "complete"
    transition = next(
        value
        for value in stage["payload"]["transitions"]
        if value["source"] == "semantic_verifier"
    )
    assert transition["source"] == "semantic_verifier"
    assert transition["state_dimensions"] == ["question_proposition"]
    assert transition["before"]["question_proposition"]["predicate"] == "unspecified"
    assert transition["after"]["question_proposition"]["predicate"] == "have"
    assert transition["changed"] is True


def test_semantic_preflight_records_typed_repair_state_snapshots() -> None:
    _relationship, diagnostics, resolution, failure = prepare_transaction(
        object(),
        object(),
        question=QUESTION,
        proposal_model="proposal-model",
        audit_model="audit-model",
        seed=0,
        release_mode=False,
        semantic_pack_digest="a" * 64,
    )

    assert failure is None
    assert resolution is not None and resolution.status == "repaired"
    [transition] = diagnostics["recovery_transitions"]
    assert transition["question_proposition_before"] == resolution.initial.as_dict()
    assert transition["question_proposition_after"] == resolution.proposition.as_dict()


def test_stage_ten_rejects_a_false_changed_marker() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    prediction["controller_trace"] = [
        {
            "stage": "evidence_rebind",
            "recovery_action": "rebind",
            "recovery_outcome": "changed",
            "evidence_ids_before": ["evidence-1"],
            "evidence_ids_after": ["evidence-2"],
            "evidence_ids_changed": False,
        }
    ]

    stage = _stage_ten(prediction, debug_row)

    assert stage["status"] == "incomplete"
    assert stage["incompleteness_reasons"] == [
        "recovery_transition_1_evidence_ids_changed_flag_mismatch"
    ]


def test_stage_ten_replays_semantic_recovery_from_local_question_state() -> None:
    prediction, context = _current_semantic_io_fixture()
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    verifier["recovery_transitions"] = [dict(SEMANTIC_STOP)]

    replay = natural_causal_transaction_replay(prediction, context)

    assert replay["status"] == "matched"
    assert replay["through_stage_index"] == 10
    reference = replay["reference_transaction"]["stages"][9]
    local = replay["local_replay_transaction"]["stages"][9]
    assert reference["status"] == "complete"
    assert local["status"] == "complete"
    assert local["comparison_digest"] == reference["comparison_digest"]
