"""Full fixed ordinary/monotonic binding results, traces and snapshot counts."""

import json
from pathlib import Path

import pytest
from ktem_tests.binding_contract_inputs import CASES
from ktem_tests.binding_contract_observations import observe_binding

FIXTURE = Path(__file__).with_name("fixtures") / "r4b_binding_baseline"


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("mode", ("ordinary", "monotonic"))
@pytest.mark.parametrize("snapshot", (False, True), ids=("none", "snapshot"))
def test_full_binding_and_assessment_trace(name, mode, snapshot):
    baseline = json.loads((FIXTURE / f"{name}.json").read_text(encoding="utf-8"))
    assert baseline["source"] == "7ed1b371cd942012b24e9654c191fcb843e7a9e4"
    key = f"{name}/{mode}/{snapshot}"
    assert observe_binding(name, mode, snapshot) == baseline["observations"][key]
