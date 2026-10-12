"""The financial policy runs on ordinary values without a planner or Runtime."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from ktem.docqa import finance_plan_policy as policy
from ktem.docqa.query_plan_schema import EvidenceSlot
from ktem_tests.plan_policy_characterization import COLLECTION, UNSUPPORTED, lossless


def test_independent_policy_matches_the_fixed_scale_plan():
    question = "What was free cash flow in millions for 2018?"
    slots, domain, comparison = policy.finance_evidence_slots(
        question,
        normalized_type="numeric",
        periods=["2018"],
        period_kind="",
        capabilities={},
        verification_domain="finance",
        causal_intent=False,
    )
    expected = json.loads(
        (
            Path(__file__).with_name("fixtures") / "r4a_plan_policy_baseline.json"
        ).read_text()
    )
    assert slots is not None and domain and not comparison
    assert (
        lossless([slot.as_dict() for slot in slots])
        == expected["cases"]["scale_fcf"]["plan"]["evidence_slots"]
    )


@pytest.mark.parametrize(
    "question, kind, domain, expected",
    [
        (UNSUPPORTED, "numeric", "finance", ((), True, False)),
        ("Describe the study.", "free_text", "", (None, False, False)),
        ("Describe the study.", "free_text", "finance", (None, True, False)),
    ],
)
def test_authoritative_empty_slots_are_distinct_from_generic_fallback(
    question, kind, domain, expected
):
    assert (
        policy.finance_evidence_slots(
            question,
            normalized_type=kind,
            periods=[],
            period_kind="",
            capabilities={},
            verification_domain=domain,
            causal_intent=False,
        )
        == expected
    )


def test_finalization_keeps_identity_unless_a_real_contribution_applies():
    original = (EvidenceSlot("slot", "support", period="2023"),)
    assert (
        policy.finalize_finance_slots("study", original, finance_domain=False)
        is original
    )
    assert (
        policy.finalize_finance_slots("study", original, finance_domain=True)
        is original
    )
    revolving = (
        EvidenceSlot("capacity", "operand", metric="revolving credit capacity"),
    )
    changed = policy.finalize_finance_slots(COLLECTION, revolving, finance_domain=True)
    assert revolving[0].cardinality == 1
    assert changed[0].cardinality == 2
    assert changed[0].entity == "active_at:2023-05-26"
    assert changed[0].operator_role == "collection"


def test_policy_cold_import_has_real_parent_and_no_reverse_runtime_or_io():
    code = r"""
import json, os, sys
import ktem
before = set(sys.modules)
events = []
auditing = True
def audit(event, args):
    if not auditing:
        return
    if event in {"socket.connect", "socket.getaddrinfo", "sqlite3.connect"}:
        events.append(event)
        raise AssertionError(event)
    if event == "open":
        mode, flags = args[1:3]
        if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)
        ):
            events.append(event)
            raise AssertionError("file write during policy import")
sys.addaudithook(audit)
from ktem.docqa import finance_plan_policy
auditing = False
loaded = sorted(set(sys.modules) - before)
for name in loaded:
    assert not name.startswith(("ktem.docqa.query_planning", "ktem.docqa.runtime", "ktem.docqa._runtime", "ktem.db", "sqlmodel", "sqlalchemy", "gradio", "ktem.llms")), name
assert events == []
print(json.dumps({"parent": ktem.__file__, "policy": finance_plan_policy.__file__, "new_modules": loaded, "side_effects": events}))
"""
    env = {
        **os.environ,
        "PYTHONPATH": os.pathsep.join(sys.path),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    result = subprocess.run(
        [sys.executable, "-c", code],
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Traceback" not in result.stderr, result.stderr
    observed = json.loads(result.stdout)
    assert (
        Path(observed["parent"]).resolve()
        == Path(__file__).parents[1] / "ktem" / "__init__.py"
    )
    assert Path(observed["policy"]).resolve() == Path(policy.__file__).resolve()
    print(json.dumps(observed))
