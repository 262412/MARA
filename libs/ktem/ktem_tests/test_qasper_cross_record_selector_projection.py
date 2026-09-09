from copy import deepcopy

import pytest
from ktem.reasoning.mara_qasper_candidate_selector_projection import (
    _canonical_selectors_for_options,
    prioritized_candidate_prompt_evidence,
)
from ktem.reasoning.mara_qasper_semantic_pack import prepare_qasper_canonical_records

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


def _records():
    return [
        {
            "label": "E1",
            "evidence_id": "cross-lingual",
            "source_id": "paper",
            "text": "We evaluated transfer in the cross-lingual setting.",
        },
        {
            "label": "E2",
            "evidence_id": "single-language",
            "source_id": "paper",
            "text": "The experiment included single-language baselines for comparison.",
        },
    ]


def test_cross_record_contributions_use_the_joint_canonical_selector_universe():
    records = _records()
    original = deepcopy(records)

    projected = prioritized_candidate_prompt_evidence(records, QUESTION)

    assert records == original
    assert [
        [selector["selector_id"] for selector in record["selectors"]]
        for record in projected
    ] == [["E1:S1"], ["E2:S1"]]
    assert projected == prepare_qasper_canonical_records(QUESTION, projected)
    for record in projected:
        selector = record["selectors"][0]
        assert selector["text"] == record["text"]
        assert selector["span_start"] == 0
        assert selector["span_end"] == len(record["text"])
        assert selector["allowed_proposition_slots"]


def test_orphan_object_contribution_does_not_enter_the_canonical_universe():
    projected = prioritized_candidate_prompt_evidence(_records()[:1], QUESTION)

    assert len(projected) == 1
    assert projected[0]["selectors"] == []
    assert (
        projected[0]["candidate_selector_projection_trace"]["selected_selector_refs"]
        == []
    )


def test_missing_canonical_selector_still_fails_closed():
    with pytest.raises(ValueError, match="^candidate_canonical_selector_missing$"):
        _canonical_selectors_for_options([{"evidence_ref": "invented:S1"}], {})
