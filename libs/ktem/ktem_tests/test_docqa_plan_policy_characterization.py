"""Expectations captured from the accepted implementation before R4-A extraction."""

import copy
import json
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa import query_planning as planning
from ktem.docqa.query_plan_schema import EvidenceLocator, EvidenceSlot, QueryPlan
from ktem_tests.plan_policy_characterization import CASES, PAYLOAD, observe

FIXTURE = Path(__file__).with_name("fixtures") / "r4a_plan_policy_baseline.json"


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_full_baseline_plans_ids_order_errors_and_call_traces(case):
    expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert expected["baseline"] == "835b2af7f54c51d500a964bc476174ae8e2d17f1"
    assert observe(case) == expected["cases"][case["name"]]


def test_original_types_aliases_and_payload_references():
    assert planning.QueryPlan is QueryPlan
    assert planning.EvidenceSlot is EvidenceSlot
    assert planning.EvidenceLocator is EvidenceLocator
    assert (
        QueryPlan.__module__
        == EvidenceSlot.__module__
        == EvidenceLocator.__module__
        == "ktem.docqa.query_plan_schema"
    )
    nested: dict[str, list[int]] = {"values": []}
    constraints = {"nested": nested}
    slot = EvidenceSlot("original", "support")
    plan = QueryPlan(
        "free_text", "planned", evidence_slots=(slot,), constraints=constraints
    )
    assert planning.build_query_plan("study", planner_payload=plan) is plan
    assert plan.evidence_slots[0] is slot
    assert plan.constraints is constraints
    projected = plan.as_dict()
    assert projected["constraints"] is not constraints
    assert projected["constraints"]["nested"] is nested
    with pytest.raises(FrozenInstanceError):
        setattr(plan, "plan_id", "replacement")


def test_accepted_mapping_keeps_nested_constraints_and_locator_order():
    payload = copy.deepcopy(PAYLOAD)
    plan = planning.build_query_plan("study", planner_payload=payload)
    assert plan.constraints is not payload["constraints"]
    assert plan.constraints["nested"] is payload["constraints"]["nested"]
    assert plan.evidence_slots[0].locator is not None
    assert plan.evidence_slots[0].locator.page_labels == ("8", "8", "12")
    assert plan.evidence_slots[0].evidence_ids == ("x", "x")
    assert plan.subqueries == ("first", "first", "second")
    assert plan.plan_id == "plan:caller-supplied"


@pytest.mark.parametrize(
    "planned", [None, "untyped", QueryPlan("free_text", "retained")]
)
@pytest.mark.parametrize("plan_id", [None, "", "keep-id"])
def test_existing_request_plan_backfill_preserves_version_and_existing_values(
    planned, plan_id
):
    existing = QueryPlan("numeric", "planned", plan_id="plan:existing")
    request = SimpleNamespace(
        query_plan=existing,
        planned_query_plan=planned,
        query_plan_id=plan_id,
        query_plan_state_version=19,
    )
    assert (
        planning.ensure_request_query_plan(request, planner_payload=PAYLOAD) is existing
    )
    assert request.planned_query_plan is (
        planned if isinstance(planned, QueryPlan) else existing
    )
    assert request.query_plan_id == (plan_id or "plan:existing")
    assert request.query_plan_state_version == 19


@pytest.mark.parametrize("existing", [None, {}, PAYLOAD])
def test_new_request_plan_overwrites_planned_plan_id_and_version(existing):
    request = SimpleNamespace(
        query_plan=copy.deepcopy(existing),
        planned_query_plan=QueryPlan("free_text", "old"),
        query_plan_id="old-id",
        query_plan_state_version=19,
        controller_question=" controller ",
        retrieval_query="retrieval",
        prompt="prompt",
        answer_type="",
        task_type="numeric",
        verification_domain="unknown",
    )
    result = planning.ensure_request_query_plan(request, planner_payload=PAYLOAD)
    assert request.query_plan is request.planned_query_plan is result
    assert request.query_plan_id == result.plan_id
    assert request.query_plan_state_version == 0
    assert (result.plan_id == "plan:caller-supplied") is (existing != {})


@pytest.mark.parametrize(
    "values, expected",
    [
        ((" controller ", "retrieval", "prompt"), "controller"),
        (("  ", " retrieval ", "prompt"), "retrieval"),
        ((None, "", " prompt "), "prompt"),
        ((0, None, ""), ""),
    ],
)
def test_request_question_precedence(values, expected):
    request = SimpleNamespace(
        **dict(zip(("controller_question", "retrieval_query", "prompt"), values))
    )
    assert planning.request_planning_question(request) == expected


def test_finance_slot_legacy_query_patch_is_used_in_both_rounds(monkeypatch):
    calls = []

    def query(metric, period, *, statement_kind, query_context=""):
        calls.append((metric, period, statement_kind, query_context))
        return f"patched {period}"

    monkeypatch.setattr(planning, "_finance_retrieval_query", query)
    plan = planning.build_query_plan(
        "What was revenue in 2023?",
        answer_type="numeric",
        verification_domain="finance",
    )
    assert plan.subqueries == ("patched 2023",)
    assert planning.missing_slot_requests(plan) == [
        {
            "query_id": "round2:operand:revenue:2023",
            "slot_id": "operand:revenue:2023",
            "query": "operand revenue 2023 patched 2023 consolidated",
            "modality": "auto",
        }
    ]
    assert calls == [
        ("revenue", "2023", "income_statement", "What was revenue in 2023?"),
        ("revenue", "2023", "income_statement", "patched 2023"),
    ]


def test_private_locators_keep_duplicates_empty_and_nonstring_values():
    assert planning._explicit_page_labels(
        {"explicit_page_labels": [" 8 ", "", "8", None, 0]}
    ) == ("8", "8", "None", "0")
    assert planning._explicit_page_labels({"explicit_page_labels": "8"}) == ()
    assert planning._finance_slot_locator(
        1, slot_count=2, page_labels=("8", "12")
    ) == EvidenceLocator(page_label="12")
    assert planning._finance_slot_locator(
        1, slot_count=2, page_labels=("8",)
    ) == EvidenceLocator(page_labels=("8",))
    with pytest.raises(IndexError, match="tuple index out of range"):
        planning._finance_slot_locator(2, slot_count=2, page_labels=("8", "12"))


def test_slot_construction_error_short_circuits_later_queries(monkeypatch):
    calls = []
    original = planning._finance_retrieval_query

    def query(*args, **kwargs):
        calls.append(args)
        return original(*args, **kwargs)

    monkeypatch.setattr(planning, "_finance_retrieval_query", query)
    invalid: Any = (("first", "revenue", "2023"), ("invalid",))
    with pytest.raises(ValueError, match="not enough values to unpack"):
        planning._finance_slots(invalid, require_scale=True)
    assert calls == [("revenue", "2023")]
