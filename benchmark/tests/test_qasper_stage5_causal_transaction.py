from __future__ import annotations

from copy import deepcopy

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)


def _freeze_candidate_plan_trace(
    prediction: dict,
    debug_row: dict,
) -> dict:
    construction = deepcopy(
        debug_row["semantic_verifier"]["semantic_data_lineage"]["plan_construction"]
    )
    binding = {
        "binding_digest": "7" * 64,
        "canonical_evidence_plan_digest": "8" * 64,
        "plan_construction_trace": construction,
    }
    pack = prediction["evidence_metadata"]["qasper_canonical_semantic_pack"]
    pack["proposition_binding"] = deepcopy(binding)
    generator = debug_row["main_candidate_generator"]
    generator["candidate_evidence_set_binding"] = deepcopy(binding)
    prediction["evidence_metadata"]["qasper_candidate_generation"] = generator
    return construction


def _not_run_plan_lineage() -> dict:
    return {
        "status": "not_run",
        "transport_status": "not_run",
        "semantic_plan_status": "not_run",
        "candidate_count": 0,
        "legal_plan_count": 0,
        "valid_candidate_counts": {},
    }


def test_candidate_plan_stage_uses_the_frozen_candidate_plan_trace() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    construction = _freeze_candidate_plan_trace(prediction, debug_row)
    debug_row["semantic_verifier"]["semantic_data_lineage"][
        "plan_construction"
    ] = _not_run_plan_lineage()

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][4]

    assert stage["status"] == "complete"
    assert stage["payload"]["plan_construction_source"] == (
        "frozen_canonical_semantic_pack"
    )
    assert stage["payload"]["candidate_plans"] == construction["candidate_decisions"]
    assert (
        stage["payload"]["candidate_plans_digest"]
        == construction["candidate_decisions_digest"]
    )


def test_candidate_plan_stage_rejects_generator_binding_drift() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    _freeze_candidate_plan_trace(prediction, debug_row)
    generator_binding = debug_row["main_candidate_generator"][
        "candidate_evidence_set_binding"
    ]
    generator_trace = generator_binding["plan_construction_trace"]
    generator_trace["candidate_decisions"][0]["candidate_id"] = "drifted"
    generator_trace["candidate_decisions_digest"] = canonical_digest(
        generator_trace["candidate_decisions"]
    )

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][4]

    assert stage["status"] == "incomplete"
    assert "candidate_generator_plan_construction_mismatch" in (
        stage["incompleteness_reasons"]
    )


def test_candidate_plan_stage_rejects_a_tampered_frozen_decision_digest() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    construction = _freeze_candidate_plan_trace(prediction, debug_row)
    construction["candidate_decisions_digest"] = "0" * 64
    pack_binding = prediction["evidence_metadata"]["qasper_canonical_semantic_pack"][
        "proposition_binding"
    ]
    pack_binding["plan_construction_trace"] = construction
    debug_row["main_candidate_generator"]["candidate_evidence_set_binding"] = deepcopy(
        pack_binding
    )

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][4]

    assert stage["status"] == "incomplete"
    assert "candidate_plans_digest_mismatch" in stage["incompleteness_reasons"]
