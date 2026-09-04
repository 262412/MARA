from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_trace_canary_10388470_stage4.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10388470_freezes_the_single_stage_four_digest_divergence() -> None:
    payload = _fixture()
    divergence = payload["first_divergence"]

    assert payload["contract_id"] == "qasper_stage4_divergence_characterization.v1"
    assert payload["source"]["job_id"] == "10388470"
    assert divergence == {
        "differing_field_count": 1,
        "field": "$.selector_universe_digest",
        "local_value": "",
        "online_value": (
            "606d514611d748ed71ecd9ce046f7fc87476028c1fc8bdf98543cc480e9690ab"
        ),
        "stage": "proposition_spans_and_selector_universe",
        "stage_index": 4,
    }


def test_job_10388470_proves_the_pack_was_equal_but_the_replay_trace_was_not() -> None:
    payload = _fixture()
    online = payload["online_candidate_identity"]
    local = payload["local_candidate_identity_before_repair"]
    frozen = payload["frozen_pack_identity"]
    selectors = payload["selector_observation"]

    assert online["canonical_semantic_pack_digest"] == frozen["semantic_pack_digest"]
    assert online["canonical_span_universe_digest"] == frozen["span_universe_digest"]
    assert online["canonical_pack_candidate_transaction_id"] == (
        frozen["candidate_transaction_id"]
    )
    assert local["canonical_semantic_pack_digest"] == ""
    assert local["canonical_span_universe_digest"] == ""
    assert local["evidence_pack_digest"] != frozen["semantic_pack_digest"]
    assert selectors["frozen_selector_count"] == 12
    assert selectors["recorded_proposition_bearing_span_count"] == 0
    assert "selectors" not in selectors["source_canonical_record_keys"]
