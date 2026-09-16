"""Retain complete plans, recovery, verification and citation order."""

import json
from pathlib import Path

import pytest
from ktem_tests.binding_execution_seams import SEAMS, observe_in_fixed_process

FIXTURE = Path(__file__).with_name("fixtures") / "r4b_binding_seams"


@pytest.fixture(scope="module")
def observed():
    return observe_in_fixed_process()


@pytest.mark.parametrize("name", SEAMS)
def test_binding_recovery_execution_verification_seam(name, observed):
    expected = json.loads((FIXTURE / f"{name}.json").read_text(encoding="utf-8"))
    assert expected["source"] == "7ed1b371cd942012b24e9654c191fcb843e7a9e4"
    assert observed[name] == expected["observation"]
