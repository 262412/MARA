"""Fixed candidate and orchestration expectations captured before R4-B."""

from copy import deepcopy
from dataclasses import replace

import pytest
from ktem.docqa import query_evidence_binding as binding
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan


def item(name, **values):
    return {"evidence_id": name, "source_id": "paper", "page_label": "1", **values}


def ranked(*rows):
    return [(score, index, record) for index, (score, record) in enumerate(rows)]


def choose(slot, rows, *, constraints=None, operands=None, used=None):
    collections = used if used is not None else (set(), set(), set())
    return binding._candidate_ids_for_slot(
        QueryPlan("extractive", "lookup", constraints=constraints or {}),
        slot,
        rows,
        operands if operands is not None else [],
        *collections,
    )


@pytest.mark.parametrize(
    ("comparison", "execution", "expected"),
    [
        (True, True, "segment"),
        (True, False, "segment"),
        (False, True, "materialize"),
        (False, False, "input"),
    ],
)
def test_preprocessing_if_elif_then_coherent_order_and_references(
    monkeypatch, comparison, execution, expected
):
    original = [item("input")]
    transformed = [item(expected)]
    calls = []

    def transform(stage, records):
        calls.append(stage)
        assert records is original
        return transformed

    def coherent(plan, records):
        calls.append("coherent")
        assert records is (original if expected == "input" else transformed)
        return records

    monkeypatch.setattr(
        binding,
        "segment_comparison_evidence_items",
        lambda records: transform("segment", records),
    )
    monkeypatch.setattr(
        binding,
        "reconcile_materialized_cells",
        lambda records: transform("materialize", records),
    )
    monkeypatch.setattr(binding, "coherent_segment_evidence_items", coherent)
    plan = QueryPlan(
        "extractive",
        "lookup",
        evidence_slots=(
            EvidenceSlot("s", "operand", required_for_execution=execution),
        ),
        constraints={
            "comparison_operator": "proportional_increase" if comparison else ""
        },
    )
    result = binding._binding_evidence_items(plan, original)
    assert result is (original if expected == "input" else transformed)
    assert calls == ([expected] if expected != "input" else []) + ["coherent"]


def test_preprocessing_exception_stops_before_coherent(monkeypatch):
    calls = []
    error = RuntimeError("materialization stopped")

    def fail(records):
        calls.append("materialize")
        raise error

    monkeypatch.setattr(binding, "reconcile_materialized_cells", fail)
    monkeypatch.setattr(
        binding,
        "coherent_segment_evidence_items",
        lambda *args: calls.append("coherent"),
    )
    plan = QueryPlan(
        "numeric",
        "calculation",
        evidence_slots=(EvidenceSlot("s", "operand", required_for_execution=True),),
    )
    with pytest.raises(RuntimeError) as caught:
        binding.bind_evidence_slots(plan, [item("a")])
    assert caught.value is error
    assert calls == ["materialize"]


def test_six_decimal_quality_score_identity_sort_and_equal_key_stability(monkeypatch):
    records = [
        item("b", score=1.0000004, quality=0),
        item("a", score=1.00000049, quality=0),
        item("c", score=0.25, quality=1),
        item("d", score=1.00000051, quality=0),
    ]
    duplicate = {**records[1], "tag": "second a"}
    records.append(duplicate)
    calls = []

    def score(plan, slot, record, *, assessments):
        calls.append(("score", record["evidence_id"]))
        return record["score"]

    def quality(slot, record, all_records):
        assert all_records is records
        calls.append(("quality", record["evidence_id"]))
        return record["quality"]

    monkeypatch.setattr(binding, "_candidate_score", score)
    monkeypatch.setattr(binding, "_slot_binding_quality", quality)
    result = binding._ranked_evidence(
        QueryPlan("extractive", "lookup"),
        EvidenceSlot("s", "support"),
        records,
        assessments=None,
    )
    assert [row[1] for row in result] == [2, 3, 1, 4, 0]
    assert all(row[2] is records[row[1]] for row in result)
    assert calls == [
        (stage, record["evidence_id"])
        for stage in ("score", "quality")
        for record in records
    ]


@pytest.mark.parametrize(
    ("kind", "retrieval", "scores", "expected"),
    [
        ("answer_relation", False, [-1, 0, 1, 2], ["a", "b", "c"]),
        ("boolean_proposition", False, [-1, 0, 1, 2], ["c"]),
        ("boolean_proposition", False, [-1, 0, 0, 2], []),
        ("answer_relation", True, [-1, 0, 1, 2], None),
    ],
)
def test_verification_none_empty_and_first_three_before_filter(
    kind, retrieval, scores, expected
):
    rows = ranked(*[(score, item(name)) for score, name in zip(scores, "abcd")])
    slot = EvidenceSlot(
        "s", "support", statement_kind=kind, required_for_retrieval=retrieval
    )
    actual = binding._verification_candidate_ids(slot, rows)
    assert actual == (
        None if expected is None else [f"evidence:paper:{x}" for x in expected]
    )
    if expected is not None:
        assert (
            choose(slot, rows, constraints={"requires_distinct_evidence": True})
            == actual
        )


def test_ordinary_candidates_slice_before_filter_and_do_not_dedupe():
    slot = EvidenceSlot("s", "support")
    assert choose(
        slot, ranked((-1, item("a")), (0, item("b")), (1, item("c")), (2, item("d")))
    ) == ["evidence:paper:c"]
    record = item("a")
    assert choose(slot, ranked((1, record), (1, record))) == [
        "evidence:paper:a",
        "evidence:paper:a",
    ]


def test_segment_priority_keeps_all_matching_periods_without_positive_filter():
    slot = EvidenceSlot(
        "segment",
        "support",
        statement_kind="segment_table",
        financial_scope="segment",
        period="2022",
    )
    rows = ranked(
        *[(0, item(str(i), column_label="2022")) for i in range(5)],
        (8, item("other", period="2021", column_label="2022")),
    )
    plan = QueryPlan(
        "extractive",
        "comparison",
        constraints={"comparison_operator": "proportional_increase"},
    )
    assert binding._segment_comparison_candidate_ids(plan, slot, rows) == [
        f"evidence:paper:{i}" for i in range(5)
    ]
    assert (
        binding._segment_comparison_candidate_ids(
            plan, replace(slot, period="2020"), rows
        )
        == []
    )
    assert (
        binding._segment_comparison_candidate_ids(plan, replace(slot, period=""), rows)
        is None
    )
    assert choose(
        slot, rows, constraints={**plan.constraints, "requires_distinct_evidence": True}
    ) == [f"evidence:paper:{i}" for i in range(5)]


def test_collection_facility_date_fallback_and_early_return_leave_used_sets():
    slot = EvidenceSlot(
        "collection",
        "operand",
        metric="revolving credit capacity",
        entity="active_at:2023-05-26",
        operator_role="COLLECTION",
        cardinality=3,
    )
    records = [
        item("future", facility_identity="future", effective_date="2024-01-01"),
        item("inactive", agreement_lifecycle_status="inactive"),
        item("a", facility_identity="facility-one", effective_date="2023-05-26"),
        item("duplicate", facility_identity="facility-one"),
        item("b"),
        item("c"),
    ]
    for record in records:
        record.setdefault("agreement_lifecycle_status", "active")
    rows = ranked((0, item("zero")), *[(1, record) for record in records])
    used = ({"evidence:paper:a"}, {"evidence:paper:a"}, {("paper", "1")})
    before = deepcopy(used)
    assert choose(
        slot, rows, constraints={"requires_distinct_evidence": True}, used=used
    ) == ["evidence:paper:a", "evidence:paper:b", "evidence:paper:c"]
    assert used == before


def test_authoritative_narrative_empty_and_override_before_distinct():
    slot = EvidenceSlot("s", "support", metric="primary customers")
    noise = item("noise", text="primary customers")
    authority = item("authority", text="A limited number of commercial airlines")
    assert choose(slot, ranked((4, noise))) == []
    rows = ranked((4, noise), (0, authority))
    assert choose(slot, rows) == ["evidence:paper:authority"]
    assert choose(slot, rows, constraints={"requires_distinct_evidence": True}) == [
        "evidence:paper:noise"
    ]


def test_dimension_reads_bound_operands_and_keeps_source_and_raw_lookup_rules():
    operand = item("value", cell_id="value", table_id="t", value="20")
    correct = item("header", table_id="t", text="Amounts in millions")
    other = item("other", source_id="other", table_id="t", text="Amounts in billions")
    rows = ranked((100, other), (0, correct), (1, operand))
    slot = EvidenceSlot("scale", "dimension", scale="million")
    assert choose(slot, rows) == []
    assert choose(slot, rows, operands=[operand, operand]) == ["evidence:paper:header"]
    assert choose(replace(slot, scale="billion"), rows, operands=[operand]) == []


def test_distinct_locator_mutation_precedes_generic_operand_rejection():
    slot = EvidenceSlot("s", "operand", cardinality=3)
    rows = ranked(
        (3, item("a", page_label="")),
        (2, item("b", page_label="2")),
        (1, item("c", page_label="3")),
    )
    used: tuple[set[str], set[str], set[tuple[str, str]]] = (
        {"evidence:paper:b"},
        set(),
        set(),
    )
    constraints = {
        "requires_distinct_evidence": True,
        "requires_distinct_source_pages": True,
    }
    assert choose(slot, rows, constraints=constraints, used=used) == []
    assert used == ({"evidence:paper:b"}, {"evidence:paper:b"}, {("paper", "2")})
    assert choose(slot, rows, constraints=constraints, used=used) == [
        "evidence:paper:c"
    ]
    assert used[1] == {"evidence:paper:b", "evidence:paper:c"}
    assert used[2] == {("paper", "2"), ("paper", "3")}


def test_explicit_distinct_slots_and_generic_operand_original_cutoff():
    rows = ranked(*[(1, item(x)) for x in "abcd"])
    slot = EvidenceSlot("s", "operand", cardinality=3)
    used: tuple[set[str], set[str], set[tuple[str, str]]] = (
        {"evidence:paper:a", "evidence:paper:b", "evidence:paper:c"},
        set(),
        set(),
    )
    assert choose(slot, rows, used=used) == []
    assert choose(replace(slot, period="2023"), rows, used=used) == [
        "evidence:paper:a",
        "evidence:paper:b",
        "evidence:paper:c",
    ]
    constraints = {
        "requires_distinct_evidence": True,
        "distinct_source_page_slot_ids": ["other"],
    }
    assert choose(
        replace(slot, role="support"), rows, constraints=constraints, used=used
    ) == ["evidence:paper:a", "evidence:paper:b", "evidence:paper:c"]
    assert used[1:] == (set(), set())


def test_old_score_export_is_the_existing_scoring_function():
    from ktem.docqa import query_evidence_binding_support, query_planning

    assert (
        binding.score_evidence_for_slot
        is query_evidence_binding_support.score_evidence_for_slot
    )
    assert "score_evidence_for_slot" in binding.__all__
    slot, record = EvidenceSlot("s", "support", metric="topic"), item("a", text="topic")
    assert query_planning.score_evidence_for_slot(
        slot, record
    ) == binding.score_evidence_for_slot(slot, record)
    assert identity_of(record).key == "evidence:paper:a"


@pytest.mark.parametrize("reverse", (False, True))
def test_ranking_input_permutation_uses_identity_but_equal_keys_stay_stable(
    monkeypatch, reverse
):
    records = [item("b", tag="b"), item("a", tag="first"), item("a", tag="second")]
    if reverse:
        records.reverse()
    monkeypatch.setattr(binding, "_candidate_score", lambda *args, **kwargs: 1.0)
    monkeypatch.setattr(binding, "_slot_binding_quality", lambda *args: 0.0)
    result = binding._ranked_evidence(
        QueryPlan("extractive", "lookup"),
        EvidenceSlot("s", "support"),
        records,
        assessments=None,
    )
    assert [row[2]["tag"] for row in result] == (
        ["second", "first", "b"] if reverse else ["first", "second", "b"]
    )


def test_verification_cardinality_exceeds_three_without_generic_operand_cutoff():
    slot = EvidenceSlot(
        "s",
        "operand",
        statement_kind="answer_relation",
        required_for_retrieval=False,
        cardinality=4,
    )
    rows = ranked(*[(-1, item(name)) for name in "abcde"])
    assert choose(slot, rows) == [f"evidence:paper:{name}" for name in "abcd"]


def test_distinct_same_page_is_skipped_without_mutating_other_sets():
    used_ids: set[str] = set()
    used_pages = {("paper", "1")}
    plan = QueryPlan(
        "extractive", "lookup", constraints={"requires_distinct_source_pages": True}
    )
    rows = ranked((1, item("same-page")), (1, item("next-page", page_label="2")))
    assert binding._distinct_candidate_ids(rows, plan, used_ids, used_pages) == [
        "evidence:paper:next-page"
    ]
    assert used_ids == {"evidence:paper:next-page"}
    assert used_pages == {("paper", "1"), ("paper", "2")}


def test_operand_accounting_retains_references_and_period_scope():
    record = item("a")
    bound: list[dict] = []
    used: set[str] = set()
    slot = EvidenceSlot("s", "operand", period="2023")
    binding._update_bound_operand_state(
        slot, ("a", "unresolved"), {"a": record}, bound, used
    )
    assert len(bound) == 1 and bound[0] is record
    assert used == set()
    binding._update_bound_operand_state(
        replace(slot, period=""), ("a",), {"a": record}, bound, used
    )
    assert bound[1] is record
    assert used == {"a"}
