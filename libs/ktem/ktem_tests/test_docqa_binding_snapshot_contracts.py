"""Snapshot misses remain errors; identity/lookup boundaries stay distinct."""

from copy import deepcopy
from dataclasses import replace

import pytest
from ktem.docqa import query_evidence_binding as binding
from ktem.docqa import query_planning
from ktem.docqa.evidence_identity import (
    EvidenceIdentityConflictError,
    canonicalize_and_dedupe_evidence,
    canonicalize_evidence_item,
    exact_evidence_aliases,
    grouping_evidence_aliases,
    identity_of,
)
from ktem.docqa.query_evidence_binding_support import item_for_raw_id
from ktem.docqa.selection_assessment_snapshot import (
    SelectionAssessmentCacheMiss,
    SelectionAssessmentSnapshot,
)
from ktem_tests.test_docqa_binding_candidate_contracts import choose, item, ranked
from ktem_tests.test_docqa_selection_assessment_snapshot import QUESTION, _items


@pytest.mark.parametrize("change", ("identity", "content", "role", "frame", "question"))
@pytest.mark.parametrize("monotonic", (False, True))
def test_selection_cache_miss_does_not_build_expand_or_classify(
    monkeypatch, change, monotonic
):
    plan = query_planning.build_query_plan(
        QUESTION, answer_type="boolean", verification_domain="qasper"
    )
    record = _items()[0]
    snapshot = SelectionAssessmentSnapshot.build(plan, [record])
    audit_before = snapshot.audit()
    record = deepcopy(record)
    if change == "identity":
        record["evidence_id"] = "different"
    if change == "content":
        record["text"] = "We did not release the source code."
    if change in {"role", "frame"}:
        slot = (
            replace(plan.evidence_slots[0], role="operand")
            if change == "role"
            else replace(plan.evidence_slots[0], metric="new frame")
        )
        plan = replace(plan, evidence_slots=(slot,))
    if change == "question":
        plan = replace(
            plan, constraints={**plan.constraints, "question": "Did they publish data?"}
        )

    def forbidden(*args, **kwargs):
        pytest.fail("Binding must consume the explicit frozen snapshot")

    monkeypatch.setattr(SelectionAssessmentSnapshot, "build", forbidden)
    monkeypatch.setattr(SelectionAssessmentSnapshot, "expanded", forbidden)
    function = (
        binding.bind_evidence_slots_monotonic
        if monotonic
        else binding.bind_evidence_slots
    )
    with pytest.raises(
        SelectionAssessmentCacheMiss, match="Boolean selection assessment missing"
    ):
        function(plan, [record], assessments=snapshot)
    audit_after = snapshot.audit()
    assert audit_after == {**audit_before, "cache_misses": 1}


def test_canonicalization_conflict_stays_at_its_own_boundary():
    record = canonicalize_evidence_item(item("a", text="topic"))
    record["source_id"] = "other"
    with pytest.raises(EvidenceIdentityConflictError):
        canonicalize_evidence_item(record)
    # Binding itself still reads the current raw identity, without extra normalization.
    assert choose(query_planning.EvidenceSlot("s", "support"), ranked((1, record))) == [
        "evidence:other:a"
    ]


def test_fact_conflicts_and_source_collisions_are_not_newly_merged():
    records = [
        item("same", cell_id="same", value="10", text="revenue 10"),
        item("same", cell_id="same", value="20", text="revenue 20"),
        item("same", cell_id="same", source_id="other", value="10", text="revenue 10"),
    ]
    with pytest.raises(EvidenceIdentityConflictError, match="cell:paper:same: value"):
        canonicalize_and_dedupe_evidence(records)
    normalized, trace = canonicalize_and_dedupe_evidence([records[0], records[2]])
    assert [identity_of(record).key for record in normalized] == [
        "cell:paper:same",
        "cell:other:same",
    ]
    assert trace["output_count"] == 2
    assert choose(
        query_planning.EvidenceSlot("s", "support"), ranked(*[(1, r) for r in records])
    ) == ["cell:paper:same", "cell:paper:same", "cell:other:same"]


def test_exact_grouping_and_dimension_raw_lookup_remain_separate():
    record = item("raw", cell_id="cell", table_id="table", parent_element_id="parent")
    assert identity_of(record).key in exact_evidence_aliases(record)
    assert "parent" in grouping_evidence_aliases(record)
    assert item_for_raw_id("raw", [record]) is record
    assert item_for_raw_id("parent", [record]) is None
    assert item_for_raw_id(identity_of(record).key, [record]) is None


def test_public_facade_keeps_actual_binder_patch_and_assessment_forwarding(monkeypatch):
    sentinel = object()
    calls = []
    plan = query_planning.QueryPlan("extractive", "lookup")
    records: list[dict] = []
    assessments = SelectionAssessmentSnapshot.build(plan, records)

    def bound(current, evidence, *, assessments):
        calls.append((current, evidence, assessments))
        return sentinel

    monkeypatch.setattr(query_planning, "_bind_evidence_slots", bound)
    assert (
        query_planning.bind_evidence_slots(plan, records, assessments=assessments)
        is sentinel
    )
    assert calls == [(plan, records, assessments)]


def test_binder_keeps_candidate_entry_patch_and_boolean_reconciliation_order(
    monkeypatch,
):
    slot = query_planning.EvidenceSlot("s", "support", metric="topic")
    plan = query_planning.QueryPlan("extractive", "lookup", evidence_slots=(slot,))
    calls = []
    original = binding.reconcile_boolean_binding_slots

    def choose_none(*args):
        calls.append("choose")
        return []

    def reconcile(current, slots, evidence, *, assessments):
        assert [s.status for s in slots] == ["missing"]
        calls.append("reconcile")
        return original(current, slots, evidence, assessments=assessments)

    monkeypatch.setattr(binding, "_candidate_ids_for_slot", choose_none)
    monkeypatch.setattr(binding, "reconcile_boolean_binding_slots", reconcile)
    assert (
        binding.bind_evidence_slots(plan, [item("a", text="topic")])
        .evidence_slots[0]
        .evidence_ids
        == ()
    )
    assert calls == ["choose", "reconcile"]
