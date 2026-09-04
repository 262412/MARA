from __future__ import annotations

import json
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "qasper_quality_10385302_stage10.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10385302_freezes_stage_ten_coverage() -> None:
    payload = _fixture()
    observed = payload["observed_run"]

    assert payload["source"]["job_id"] == "10385302"
    assert observed == {
        "complete_stage10_rows": 3,
        "row_count": 18,
        "semantic_recovery_rows": 15,
    }


def test_job_10385302_freezes_the_unscoped_semantic_repair_transition() -> None:
    payload = _fixture()
    stage = payload["sample_stage10"]

    assert payload["semantic_repair_transition"] == {
        "from": "question_proposition",
        "outcome": "repaired",
        "reason": "question_proposition_predicate_unspecified",
        "to": "proposition_repair",
    }
    assert stage["status"] == "incomplete"
    assert stage["incompleteness_reasons"] == [
        "recovery_transition_2_state_diff_missing"
    ]
    assert payload["root_cause"] == (
        "typed_question_proposition_repair_recorded_no_before_or_after_state_and_"
        "local_replay_dropped_semantic_recovery_transitions"
    )
