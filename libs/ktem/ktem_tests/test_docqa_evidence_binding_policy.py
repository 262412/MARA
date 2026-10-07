"""Candidate policy is callable without binding state or runtime construction."""

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from ktem.docqa import evidence_binding_policy as policy
from ktem.docqa import query_evidence_binding as binding
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan


def test_independent_policy_uses_caller_owned_collections_at_original_stage():
    plan = QueryPlan(
        "extractive", "lookup", constraints={"requires_distinct_evidence": True}
    )
    slot = EvidenceSlot("operand", "operand")
    record = {"evidence_id": "a", "source_id": "paper", "page_label": "1"}
    generic = {"evidence:paper:a"}
    used: set[str] = set()
    pages: set[tuple[str, str]] = set()
    assert (
        policy.candidate_ids_for_slot(
            plan, slot, [(1.0, 0, record)], [], generic, used, pages
        )
        == []
    )
    assert generic == used == {"evidence:paper:a"}
    assert pages == set()
    assert record == {"evidence_id": "a", "source_id": "paper", "page_label": "1"}


@pytest.mark.parametrize(
    "kind, expected", [("support", None), ("boolean_proposition", [])]
)
def test_independent_verification_preserves_not_applicable_and_empty(kind, expected):
    slot = EvidenceSlot(
        "s",
        "support",
        statement_kind=kind,
        required_for_verification=True,
        required_for_retrieval=False,
    )
    assert policy.verification_candidate_ids(slot, []) == expected


@pytest.mark.parametrize(
    "name",
    [
        "candidate_ids_for_slot",
        "verification_candidate_ids",
        "segment_comparison_candidate_ids",
        "collection_candidate_ids",
        "dimension_candidate_ids",
        "distinct_candidate_ids",
    ],
)
def test_legacy_diagnostic_entries_share_the_single_policy_implementation(name):
    original = getattr(binding, "_" + name)
    extracted = getattr(policy, name)
    assert original is extracted
    assert inspect.signature(original) == inspect.signature(extracted)


def test_policy_cold_import_uses_real_parent_without_binder_or_io():
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
from ktem.docqa import evidence_binding_policy
auditing = False
loaded = sorted(set(sys.modules) - before)
blocked = ("ktem.docqa.query_evidence_binding", "ktem.docqa.query_planning",
           "ktem.docqa.runtime", "ktem.docqa.controller", "ktem.db",
           "sqlmodel", "sqlalchemy", "gradio", "ktem.llms")
for name in loaded:
    assert not any(name == prefix or name.startswith(prefix + ".") for prefix in blocked), name
    assert not name.startswith("ktem.docqa._runtime"), name
assert events == []
print(json.dumps({"parent": ktem.__file__, "policy": evidence_binding_policy.__file__, "new_modules": loaded, "side_effects": events}))
"""
    result = subprocess.run(
        [sys.executable, "-B", "-c", code],
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(sys.path),
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Traceback" not in result.stderr, result.stderr
    observed = json.loads(result.stdout)
    assert Path(observed["parent"]).resolve() == (
        Path(__file__).parents[1] / "ktem" / "__init__.py"
    )
    assert Path(observed["policy"]).resolve() == Path(policy.__file__).resolve()
    print(json.dumps(observed))
