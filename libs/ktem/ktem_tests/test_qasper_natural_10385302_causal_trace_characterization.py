from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "qasper_natural_10385302_causal_trace_gaps.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10385302_freezes_all_eighteen_causal_trace_gaps() -> None:
    payload = _fixture()
    rows = payload["instances"]

    assert payload["contract"] == "qasper_causal_trace_gap_fixture.v1"
    assert payload["source"]["job_id"] == "10385302"
    assert payload["source"]["code_sha"] == ("d8b3fbc8f9bd5bb1447b96fa004f02376521d658")
    assert len(rows) == payload["instance_count"] == 18
    assert len({row["example_id"] for row in rows}) == 6
    assert Counter(row["route"] for row in rows) == {
        "text_rag": 6,
        "controller_auto": 6,
        "crag_guarded": 6,
    }
    assert Counter(row["first_inconsistency_stage"] for row in rows) == {
        "plan_construction": 9,
        "auditor_semantics": 3,
        "": 6,
    }


def test_job_10385302_proves_why_the_old_trace_cannot_close_the_chain() -> None:
    payload = _fixture()
    rows = payload["instances"]

    assert payload["trace_gaps"] == [
        "source_to_canonical_selector_crosswalk_missing",
        "pre_limit_selector_decisions_missing",
        "all_plan_candidate_decisions_missing",
        "first_decisive_transition_missing",
    ]
    assert all(
        row["source_selector_count"] > row["canonical_selector_count"] for row in rows
    )
    assert all(row["relation_analysis_count"] > 0 for row in rows)
    assert sum(row["relation_analysis_count"] for row in rows) == 853
    assert sum(row["legal_plan_count"] for row in rows) == 3

    missing = [row for row in rows if not row["first_inconsistency_stage"]]
    assert len(missing) == 6
    assert Counter(row["example_id"] for row in missing) == {
        "f2155dc4aeab86bf31a838c8ff388c85440fce6e": 3,
        "7cd22ca9e107d2b13a7cc94252aaa9007976b338": 3,
    }
    assert {
        row["annotation_ambiguous"]
        for row in missing
        if row["example_id"].startswith("7cd22")
    } == {False}


def test_job_10385302_freezes_candidate_elimination_and_auditor_boundaries() -> None:
    payload = _fixture()

    assert payload["observed_rejection_reason_union"] == [
        "event_subplan_incomplete",
        "explicit_contradiction_missing",
        "object_coverage_incomplete",
        "predicate_argument_binding_incomplete",
        "quantifier_attachment_invalid",
        "slot_coverage_incomplete",
        "support_conflicts_with_explicit_contradiction",
        "support_role_binding_incomplete",
    ]
    rejection = payload["auditor_rejection_observation"]
    assert rejection == {
        "example_id": "6568a31241167f618ef5ede939053feaa2fb0d7e",
        "route_count": 3,
        "local_projection_status": "passed",
        "selected_plan_id": (
            "dfb3d3bf990951ac0e9e16a5bbb569ad53846042a9256e03db69cf8a6f8fe03d"
        ),
        "audit_status": "rejected",
        "audit_reason": "premise_proposition_binding_rejected",
        "provider_or_parser_failure_count": 0,
    }
    summary = payload["summary_observation"]
    assert summary["semantic_verifier_failure_count"] == 0
    assert summary["entailment_audit_failure_count"] == 0
    assert summary["entailment_audit_rejection_count"] == 3
    assert summary["verifier_audit_rejection_count"] == 3
    assert summary["recovery_stopped_without_state_change"] == 12
