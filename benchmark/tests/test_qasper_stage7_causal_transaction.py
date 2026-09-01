from __future__ import annotations

from copy import deepcopy

from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)


def _projection_fixture() -> tuple[dict, dict, dict]:
    prediction, debug_row = _prediction_and_debug_row()
    pack = prediction["evidence_metadata"]["qasper_canonical_semantic_pack"]
    selector = pack["records"][0]["selectors"][0]
    selector["allowed_proposition_slots"] = ["actor", "predicate", "object"]
    pack["slots"] = [
        {
            "slot_id": "support:boolean_proposition",
            "evidence_refs": ["E1:S1"],
        }
    ]
    binding = pack["proposition_binding"]
    binding["applicable_slots"] = ["actor", "predicate", "object"]
    plan = binding["canonical_evidence_plan"]["support_plan"]
    plan.update(
        {
            "polarity_relation": "proposition_support",
            "span_refs": ["E1:S1"],
            "slot_refs": {
                "actor": ["E1:S1"],
                "predicate": ["E1:S1"],
                "object": ["E1:S1"],
            },
            "event_binding_id": "event-binding-1",
            "required_object_tokens": [],
            "covered_object_tokens": [],
            "event_subplans": [],
            "comparison_relation": None,
        }
    )
    generator_binding = deepcopy(binding)
    debug_row["main_candidate_generator"][
        "candidate_evidence_set_binding"
    ] = generator_binding
    prediction["evidence_metadata"]["qasper_candidate_generation"] = debug_row[
        "main_candidate_generator"
    ]
    return prediction, debug_row, plan


def _stage_seven(prediction: dict, debug_row: dict) -> dict:
    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    return transaction["stages"][6]


def test_projection_stage_ignores_model_supplied_authority_fields() -> None:
    prediction, debug_row, _plan = _projection_fixture()
    parsed = debug_row["semantic_verifier"]["debug_trace"]["events"][0]["transaction"][
        "proposal"
    ]["attempts"][0]["parsed_value"]
    parsed["premises"] = [{"span_selector": "MODEL:FORGED"}]
    parsed["proof_mode"] = "model_forged"
    parsed["evidence_relation"] = "model_forged"

    stage = _stage_seven(prediction, debug_row)

    assert stage["status"] == "complete"
    assert stage["payload"]["projection_authority_source"] == (
        "frozen_canonical_semantic_pack"
    )
    assert [item["span_selector"] for item in stage["payload"]["premises"]] == ["E1:S1"]
    assert stage["payload"]["proof_mode"] == "atomic_semantic"
    assert stage["payload"]["evidence_relation"] == "proposition_support"


def test_projection_stage_uses_frozen_plan_slot_bindings() -> None:
    prediction, debug_row, plan = _projection_fixture()

    stage = _stage_seven(prediction, debug_row)

    assert stage["status"] == "complete"
    assert stage["payload"]["slot_bindings"] == plan["slot_refs"]


def test_projection_stage_rejects_a_plan_with_a_missing_frozen_span() -> None:
    prediction, debug_row, _plan = _projection_fixture()
    pack = prediction["evidence_metadata"]["qasper_canonical_semantic_pack"]
    pack["records"][0]["selectors"] = []

    stage = _stage_seven(prediction, debug_row)

    assert stage["status"] == "incomplete"
    assert "canonical_evidence_plan_span_invalid" in stage["incompleteness_reasons"]
