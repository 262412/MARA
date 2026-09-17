"""Full baseline result/terminal/plan comparisons, including trace and IDs."""

import json
from pathlib import Path

import pytest
from ktem_tests.route_closeout_seams import SEAMS, observe_in_fixed_process

FIXTURE = Path(__file__).with_name("fixtures") / "r4c_route_closeout"


@pytest.fixture(scope="module")
def observed():
    return observe_in_fixed_process()


@pytest.mark.parametrize("name", SEAMS)
def test_route_recovery_and_terminal_full_baseline(name, observed):
    expected = json.loads((FIXTURE / f"{name}.json").read_text(encoding="utf-8"))
    assert expected["source"] == "273e6173cb736a2f154f51daa69190393372c9b7"
    assert observed[name] == expected["observation"]
