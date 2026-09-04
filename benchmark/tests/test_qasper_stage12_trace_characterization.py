from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_trace_canary_10388470_stage12.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10388470_freezes_the_stage_twelve_provenance_loss() -> None:
    payload = _fixture()
    replay = payload["replay_without_frozen_run_context"]

    assert payload["source"]["job_id"] == "10388470"
    assert replay["status"] == "failed"
    assert replay["stage_index"] == 12
    assert replay["first_divergence_reason"] == "reference_stage_incomplete"
    assert replay["incompleteness_reasons"] == [
        "code_sha_missing",
        "worktree_path_missing",
        "worktree_not_clean",
        "manifest_digest_missing",
        "run_config_missing",
    ]


def test_job_10388470_freezes_the_two_true_stage_twelve_differences() -> None:
    payload = _fixture()
    online = payload["online_stage12"]
    replay = payload["replay_with_frozen_run_context"]

    assert online["status"] == "complete"
    assert online["worktree_clean"] is True
    assert online["source_prediction_digest"] == (
        "489bd8d5a918397d0e47a623cd187085a547e70141bb73b6da8f56d3576b7c4b"
    )
    assert [difference["field"] for difference in replay["differing_fields"]] == [
        "$.provider_model_identity.candidate_model",
        "$.source_prediction_digest",
    ]
    assert payload["root_cause"] == (
        "replay_discarded_the_frozen_run_context_then_rehashed_the_mutated_"
        "replay_prediction_and_reconstructed_an_empty_candidate_model"
    )
