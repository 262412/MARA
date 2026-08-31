from __future__ import annotations

from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)


def _stage_six(prediction: dict, debug_row: dict) -> dict:
    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    return transaction["stages"][5]


def test_selected_plan_stage_uses_frozen_candidate_selection_ids() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    frozen_binding = prediction["evidence_metadata"]["qasper_canonical_semantic_pack"][
        "proposition_binding"
    ]
    frozen_ids = frozen_binding["plan_construction_trace"]["selected_candidate_ids"]
    verifier_construction = debug_row["semantic_verifier"]["semantic_data_lineage"][
        "plan_construction"
    ]
    verifier_construction["selected_candidate_ids"] = {}

    stage = _stage_six(prediction, debug_row)

    assert stage["status"] == "complete"
    assert stage["payload"]["selection_authority_source"] == (
        "frozen_canonical_semantic_pack"
    )
    assert stage["payload"]["selected_candidate_ids"] == frozen_ids
    assert stage["payload"]["selected_plan_id"] == "6" * 64


def test_selected_plan_stage_rejects_a_nonlocal_model_plan_id() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    proposal_attempt = debug_row["semantic_verifier"]["debug_trace"]["events"][0][
        "transaction"
    ]["proposal"]["attempts"][0]
    proposal_attempt["parsed_value"]["canonical_evidence_plan_id"] = "9" * 64

    stage = _stage_six(prediction, debug_row)

    assert stage["status"] == "incomplete"
    assert "selected_plan_id_not_in_frozen_local_plans" in (
        stage["incompleteness_reasons"]
    )


def test_selected_plan_stage_rejects_generator_binding_drift() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    generator_binding = debug_row["main_candidate_generator"][
        "candidate_evidence_set_binding"
    ]
    support_plan = generator_binding["canonical_evidence_plan"]["support_plan"]
    support_plan["plan_id"] = "9" * 64

    stage = _stage_six(prediction, debug_row)

    assert stage["status"] == "incomplete"
    assert "candidate_generator_selection_binding_mismatch" in (
        stage["incompleteness_reasons"]
    )
