from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_trace_10385302_stage7_projection.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10385302_freezes_the_low_entropy_model_response() -> None:
    payload = _fixture()
    response = payload["model_response_payload"]

    assert payload["contract_id"] == "qasper_stage7_projection_characterization.v1"
    assert payload["source"]["job_id"] == "10385302"
    assert set(response) == {
        "candidate_judgment",
        "canonical_evidence_plan_id",
    }
    assert response["candidate_judgment"] == "supported"
    assert (
        response["canonical_evidence_plan_id"]
        == payload["frozen_local_plan"]["plan_id"]
    )


def test_job_10385302_freezes_the_local_authority_projection() -> None:
    payload = _fixture()
    plan = payload["frozen_local_plan"]
    projection = payload["local_projection"]

    assert plan["span_refs"] == ["E2:S27", "E2:S28"]
    assert projection["premise_selectors"] == plan["span_refs"]
    assert projection["premise_count"] == 2
    assert projection["proof_mode"] == "composite_conjunction"
    assert plan["evidence_relation"] == "proposition_support"
    assert set(plan["slot_bindings"]) == {
        "actor",
        "predicate",
        "object",
        "quantifier",
    }
    assert payload["invariant"] == (
        "model_selects_only_judgment_and_local_plan_id_"
        "all_authority_fields_are_local_projections"
    )
