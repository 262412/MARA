from __future__ import annotations

from ktem.reasoning.mara_qasper_candidate import _candidate_prompt
from ktem.reasoning.mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding,
    exact_candidate_slot_binding,
)
from ktem.reasoning.mara_qasper_candidate_relation import candidate_slot_hints

QUESTION = "Did the authors compare the two systems?"


def _selector(selector_id: str, text: str, start: int) -> dict[str, object]:
    return {
        "selector_id": selector_id,
        "text": text,
        "span_start": start,
        "span_end": start + len(text),
    }


def _split_positive_record() -> dict[str, object]:
    return {
        "evidence_id": "e1",
        "text": "The authors compared the two systems",
        "selectors": [
            _selector("E1:S1", "The authors", 0),
            _selector("E1:S2", "compared", 12),
            _selector("E1:S3", "the two systems", 21),
        ],
    }


def _split_negative_record() -> dict[str, object]:
    return {
        "evidence_id": "e1",
        "text": "The authors did not compare the two systems",
        "selectors": [
            _selector("E1:S1", "The authors", 0),
            _selector("E1:S2", "did not compare", 12),
            _selector("E1:S3", "the two systems", 28),
        ],
    }


def test_one_evidence_set_can_union_three_exact_spans_for_support() -> None:
    binding = candidate_evidence_set_binding([_split_positive_record()], QUESTION)

    assert binding["binding_status"] == "bound"
    assert binding["binding_reason"] == "exact_span_set"
    assert binding["covered_slots"] == ["actor", "predicate", "object", "quantifier"]
    assert binding["evidence_refs"] == ["E1:S1", "E1:S2", "E1:S3"]
    assert binding["support"] is True
    assert binding["explicit_contradiction"] is False
    assert [
        {key: span[key] for key in ("evidence_id", "evidence_ref")}
        for span in binding["evidence_set_spans"]
    ] == [
        {"evidence_id": "e1", "evidence_ref": "E1:S1"},
        {"evidence_id": "e1", "evidence_ref": "E1:S2"},
        {"evidence_id": "e1", "evidence_ref": "E1:S3"},
    ]


def test_cross_record_exact_spans_with_local_offsets_form_one_set() -> None:
    records = [
        {
            "evidence_id": "e1",
            "text": "The authors",
            "selectors": [_selector("E1:S1", "The authors", 0)],
        },
        {
            "evidence_id": "e2",
            "text": "compared",
            "selectors": [_selector("E2:S1", "compared", 0)],
        },
        {
            "evidence_id": "e3",
            "text": "the two systems",
            "selectors": [_selector("E3:S1", "the two systems", 0)],
        },
    ]

    binding = candidate_evidence_set_binding(records, QUESTION)

    assert binding["binding_status"] == "bound"
    # Cross-record slot coverage is structurally auditable, but the isolated
    # predicate is not enough to project a polarity across unrelated records.
    assert binding["support"] is False
    assert binding["polarity_signal"] == "undetermined"
    assert binding["evidence_ids"] == ["e1", "e2", "e3"]
    assert binding["evidence_refs"] == ["E1:S1", "E2:S1", "E3:S1"]


def test_windowed_record_normalizes_source_relative_exact_offsets() -> None:
    record = _split_positive_record()
    record["text_start"] = 100
    record["selectors"] = [
        _selector("E1:S1", "The authors", 100),
        _selector("E1:S2", "compared", 112),
        _selector("E1:S3", "the two systems", 121),
    ]

    binding = candidate_evidence_set_binding([record], QUESTION)

    assert binding["binding_status"] == "bound"
    assert binding["support"] is True
    assert binding["evidence_refs"] == ["E1:S1", "E1:S2", "E1:S3"]


def test_support_and_contradiction_are_separate_set_level_observations() -> None:
    record = {
        "evidence_id": "e1",
        "text": "The authors compared the two systems. did not compare the two systems",
        "selectors": [
            _selector("E1:S1", "The authors", 0),
            _selector("E1:S2", "compared", 12),
            _selector("E1:S3", "the two systems", 21),
            _selector("E1:S4", "did not compare", 38),
            _selector("E1:S5", "the two systems", 54),
        ],
    }

    binding = candidate_evidence_set_binding([record], QUESTION)

    assert binding["support"] is True
    assert binding["explicit_contradiction"] is True
    assert binding["polarity_signal"] == "undetermined"
    assert binding["support_evidence_refs"] == ["E1:S1", "E1:S2", "E1:S3"]
    assert binding["explicit_contradiction_evidence_refs"] == [
        "E1:S1",
        "E1:S3",
        "E1:S4",
    ]


def test_record_identity_and_first_selector_cannot_bind_an_incomplete_set() -> None:
    record = {
        "evidence_id": "e1",
        "text": "The authors",
        "selectors": [_selector("E1:S1", "The authors", 0)],
    }

    binding = candidate_evidence_set_binding([record], QUESTION)

    assert binding["binding_status"] == "missing"
    assert binding["binding_reason"] == "record_identity_only"
    assert binding["evidence_refs"] == []
    assert binding["support"] is False
    assert binding["explicit_contradiction"] is False


def test_quantifier_none_is_not_added_as_evidence_by_default() -> None:
    question = "Did the authors compare the systems?"

    assert "quantifier" not in candidate_slot_hints(
        question,
        "The authors compared the systems.",
    )


def test_candidate_binding_allows_extra_unselected_record_spans() -> None:
    too_many = {
        "evidence_id": "e1",
        "text": "The authors compared the two systems unrelated",
        "selectors": [
            _selector("E1:S1", "The authors", 0),
            _selector("E1:S2", "compared", 12),
            _selector("E1:S3", "the two", 21),
            _selector("E1:S4", "systems", 29),
            _selector("E1:S5", "unrelated", 37),
        ],
    }
    cross_record = [
        {
            "evidence_id": "e1",
            "text": "The authors",
            "selectors": [_selector("E1:S1", "The authors", 0)],
        },
        {
            "evidence_id": "e2",
            "text": "compared the two systems",
            "selectors": [
                _selector("E2:S1", "compared", 0),
                _selector("E2:S2", "the two systems", 9),
            ],
        },
    ]
    slot = {
        "evidence_refs": ["E1:S1", "E2:S1", "E2:S2"],
        "proposition_slot_bindings": {
            "actor": "current_paper",
            "predicate": "compare",
            "object": "the two systems",
            "quantifier": "two",
        },
        "proposition_slot_evidence_refs": {
            "actor": ["E1:S1"],
            "predicate": ["E2:S1"],
            "object": ["E2:S2"],
            "quantifier": ["E2:S2"],
        },
        "typed_proposition": {
            "actor": "current_paper",
            "predicate": "compare",
            "object_surface": "the two systems",
            "quantifier": "two",
        },
        "binding_status": "verified",
        "evidence_relation": "proposition_support",
    }

    assert candidate_evidence_set_binding([too_many], QUESTION)["binding_status"] == (
        "bound"
    )
    assert exact_candidate_slot_binding(
        slot,
        [{**record, "selectors": list(record["selectors"])} for record in cross_record],
    ) == (["e1", "e2"], ["E1:S1", "E2:S1", "E2:S2"])


def test_unquantified_set_keeps_quantifier_trace_without_binding_it() -> None:
    record = {
        "evidence_id": "e1",
        "text": "The authors compared the systems",
        "selectors": [
            _selector("E1:S1", "The authors", 0),
            _selector("E1:S2", "compared", 12),
            _selector("E1:S3", "the systems", 21),
        ],
    }

    binding = candidate_evidence_set_binding(
        [record], "Did the authors compare the systems?"
    )

    assert binding["binding_status"] == "bound"
    assert binding["required_slots"] == ["actor", "predicate", "object"]
    assert binding["applicable_slots"] == ["actor", "predicate", "object"]
    assert binding["covered_slots"] == ["actor", "predicate", "object"]
    assert binding["slot_states"]["quantifier"] == "not_applicable"
    assert binding["quantifier_evidence_state"] == "not_applicable"
    assert "quantifier" not in binding["slot_evidence_refs"]


def test_exact_unquantified_binding_omits_quantifier_authority_slot() -> None:
    record = {
        "evidence_id": "e1",
        "text": "The authors compared the systems",
        "selectors": [
            _selector("E1:S1", "The authors", 0),
            _selector("E1:S2", "compared", 12),
            _selector("E1:S3", "the systems", 21),
        ],
    }
    slot = {
        "evidence_refs": ["E1:S1", "E1:S2", "E1:S3"],
        "proposition_slot_bindings": {
            "actor": "current_paper",
            "predicate": "compare",
            "object": "the systems",
        },
        "proposition_slot_evidence_refs": {
            "actor": ["E1:S1"],
            "predicate": ["E1:S2"],
            "object": ["E1:S3"],
        },
        "typed_proposition": {
            "actor": "current_paper",
            "predicate": "compare",
            "object_surface": "the systems",
            "quantifier": "none",
        },
        "binding_status": "verified",
        "evidence_relation": "proposition_support",
    }

    assert exact_candidate_slot_binding(slot, [record]) == (
        ["e1"],
        ["E1:S1", "E1:S2", "E1:S3"],
    )


def test_candidate_prompt_exposes_non_authoritative_set_binding() -> None:
    prompt = _candidate_prompt(
        QUESTION,
        [{"label": "E1", **_split_positive_record()}],
        required_slots=[],
    )

    assert "CANDIDATE EVIDENCE-SET OBSERVATION:" in prompt
    assert '"binding_status":"bound"' in prompt
    assert "one to four exact selectors" in prompt
    assert "immutable span universe" in prompt
    assert "permission to invent evidence" in prompt
    assert "Quantifier none is not evidence" in prompt


def test_selector_offsets_must_resolve_to_exact_record_text() -> None:
    record = _split_positive_record()
    record["selectors"] = [
        _selector("E1:S1", "The authors", 1),
        _selector("E1:S2", "compared", 12),
        _selector("E1:S3", "the two systems", 21),
    ]

    binding = candidate_evidence_set_binding([record], QUESTION)

    assert binding["binding_status"] == "missing"
    assert "E1:S1" not in binding["evidence_refs"]
