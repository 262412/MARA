from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_trace_canary_10388470_stage6.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10388470_freezes_the_single_stage_six_field_divergence() -> None:
    payload = _fixture()
    divergence = payload["first_divergence"]

    assert payload["contract_id"] == "qasper_stage6_divergence_characterization.v1"
    assert payload["source"]["job_id"] == "10388470"
    assert divergence == {
        "differing_field_count": 1,
        "field": "$.selected_candidate_ids",
        "local_value": {
            "explicit_contradiction": "",
            "proposition_support": "",
        },
        "online_value": {},
        "stage": "selected_local_plan",
        "stage_index": 6,
    }


def test_job_10388470_proves_selection_outcome_itself_was_identical() -> None:
    payload = _fixture()
    frozen = payload["frozen_candidate_stage_selection"]
    verifier = payload["post_verifier_selection"]

    assert payload["shared_selection_outcome"] == {
        "legal_plan_count": 0,
        "selected_plan_id": "",
        "selection_reason": "no_legal_plan",
        "selection_status": "not_selected",
    }
    assert frozen["selected_candidate_ids"] == {
        "explicit_contradiction": "",
        "proposition_support": "",
    }
    assert verifier["selected_candidate_ids"] == {}
    assert verifier["status"] == "not_run"
    assert payload["root_cause"] == (
        "stage6_mixed_frozen_binding_with_post_verifier_plan_construction"
    )
