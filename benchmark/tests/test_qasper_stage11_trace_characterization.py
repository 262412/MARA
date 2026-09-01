from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_trace_canary_10388470_stage11.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10388470_freezes_the_hidden_terminal_projection_divergence() -> None:
    payload = _fixture()
    terminal = payload["terminal_projection"]

    assert payload["source"]["job_id"] == "10388470"
    assert terminal["online_runtime_projection_present"] is True
    assert terminal["local_runtime_projection_present"] is False
    assert terminal["online_terminal_bundle_metadata_digest"] == (
        terminal["state_bundle_metadata_digest"]
    )
    assert terminal["local_terminal_bundle_metadata_digest"] != (
        terminal["state_bundle_metadata_digest"]
    )


def test_stage_eleven_previously_missed_the_terminal_projection_divergence() -> None:
    payload = _fixture()
    stage = payload["observed_stage11"]

    assert stage["status"] == "complete"
    assert stage["incompleteness_reasons"] == []
    assert payload["real_quality_rows"] == {
        "row_count": 18,
        "runtime_projection_valid": 18,
        "scoring_answer_matches_commit": 18,
        "terminal_aliases_valid": 18,
    }
    assert payload["root_cause"] == (
        "local_replay_mutated_the_terminal_evidence_envelope_while_stage_eleven_"
        "checked_only_field_presence"
    )
