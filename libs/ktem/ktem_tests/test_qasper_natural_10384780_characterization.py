from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "qasper_natural_10384780_canonical_evidence_plans.json"
)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10384780_natural_plan_failures_are_frozen_by_route() -> None:
    payload = _fixture()
    instances = payload["instances"]

    assert payload["contract"] == ("qasper_natural_canonical_evidence_plan_fixture.v1")
    assert payload["source"]["job_id"] == "10384780"
    assert payload["source"]["code_sha"] == ("21552f8742161ce9ebda7ab40980b36e6fff24ae")
    assert len(instances) == payload["instance_count"] == 18
    assert len({row["sample_id"] for row in instances}) == 6
    assert {row["route"] for row in instances} == {
        "text_rag",
        "controller_auto",
        "crag_guarded",
    }
    assert Counter(row["sample_id"] for row in instances) == Counter(
        {f"natural_{index:02d}": 3 for index in range(1, 7)}
    )
    assert Counter(row["expected_defect_class"] for row in instances) == {
        "empty_plan": 15,
        "cross_event_invalid": 3,
    }


def test_job_10384780_empty_plans_expose_the_lineage_blind_spot() -> None:
    rows = [
        row
        for row in _fixture()["instances"]
        if row["expected_defect_class"] == "empty_plan"
    ]

    assert len(rows) == 15
    for row in rows:
        assert row["binding_state"] == "unresolved"
        assert row["binding_status"] == "missing"
        assert row["allowed_plan_ids"] == []
        assert row["selected_plan_id"] == ""
        assert row["canonical_plan_span_refs"] == []
        assert row["covered_slots"] == []
        assert row["covered_object_tokens"] == []
        assert row["lineage_status"] == "passed"
        assert row["first_inconsistency"] == {}
        assert row["selector_refs"]


def test_job_10384780_cross_event_plans_reached_the_auditor_incorrectly() -> None:
    rows = [
        row
        for row in _fixture()["instances"]
        if row["expected_defect_class"] == "cross_event_invalid"
    ]

    assert len(rows) == 3
    for row in rows:
        event_ids = {selector["event_id"] for selector in row["selector_refs"]}
        assert len(event_ids) == 2
        assert row["binding_state"] == "relation_bound_contradiction"
        assert len(row["allowed_plan_ids"]) == 1
        assert row["selected_plan_id"] == row["allowed_plan_ids"][0]
        assert row["required_object_tokens"] == ["control", "quality"]
        assert row["covered_object_tokens"] == ["control", "quality"]
        assert row["lineage_status"] == "failed"
        assert row["first_inconsistency"]["stage"] == "auditor_semantics"
        assert row["first_inconsistency"]["reason"] == (
            "auditor_internal_inconsistency"
        )
