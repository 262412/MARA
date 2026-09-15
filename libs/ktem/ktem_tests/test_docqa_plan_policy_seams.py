"""Baseline transcripts retain plans, queries, budgets, citations and terminal state."""

import json
from pathlib import Path

import pytest
from ktem_tests.plan_policy_seams import SEAMS, observe_in_fixed_process

FIXTURE = Path(__file__).with_name("fixtures") / "r4a_plan_policy_seams"


@pytest.fixture(scope="module")
def observed():
    return observe_in_fixed_process()


@pytest.mark.parametrize("name", SEAMS)
def test_real_planning_binding_execution_recovery_and_verification(name, observed):
    baseline = json.loads((FIXTURE / f"{name}.json").read_text(encoding="utf-8"))
    assert baseline["source"] == "e40dc0a18ef57d251a2931ce85553e22ee145798"
    assert observed[name] == baseline["observation"]
