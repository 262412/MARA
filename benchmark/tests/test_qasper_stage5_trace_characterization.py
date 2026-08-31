from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_trace_canary_10388470_stage5.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10388470_freezes_the_stage_five_reference_failure() -> None:
    payload = _fixture()

    assert payload["contract_id"] == "qasper_stage5_divergence_characterization.v1"
    assert payload["source"]["job_id"] == "10388470"
    assert payload["first_failure"] == {
        "reason": "reference_stage_incomplete",
        "stage": "candidate_plans",
        "stage_index": 5,
    }
    assert payload["observed_stage_payloads"]["online_reference"] == {
        "candidate_plan_count": 0,
        "candidate_plans_digest": "",
        "incompleteness_reasons": ["candidate_plan_enumeration_incomplete"],
        "status": "incomplete",
    }


def test_job_10388470_proves_the_frozen_plan_trace_was_not_missing() -> None:
    payload = _fixture()
    frozen = payload["frozen_candidate_stage_plan_trace"]
    generator = payload["candidate_generator_plan_trace"]
    verifier = payload["post_verifier_lineage"]

    assert frozen["contract_id"] == "canonical_plan_construction_trace.v1"
    assert frozen["candidate_count"] == 14
    assert frozen["candidate_decision_count"] == 28
    assert frozen["relation_analysis_count"] == 28
    assert frozen["candidate_decisions_complete"] is True
    assert frozen["all_decisions_have_typed_rejection_reasons"] is True
    assert generator["identical_to_frozen_plan_trace"] is True
    assert verifier["status"] == "not_run"
    assert verifier["candidate_count"] == 0
    assert payload["root_cause"] == (
        "stage5_read_post_verifier_lineage_instead_of_frozen_candidate_plan_trace"
    )
