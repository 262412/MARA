from __future__ import annotations

import json

import pytest
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_result,
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)
from ktem_tests.test_mara_semantic_proposition_verifier import _model_response


def _packed_premises(count: int) -> list[dict]:
    return [
        {
            "label": f"E{index}",
            "evidence_id": f"synthetic-evidence-{index}",
            "selectors": [
                {
                    "selector_id": f"E{index}:S1",
                    "text": f"Synthetic premise {index} is stated in the source.",
                    "span_start": 0,
                    "span_end": len(
                        f"Synthetic premise {index} is stated in the source."
                    ),
                }
            ],
        }
        for index in range(1, count + 1)
    ]


def test_response_schema_uses_portable_subset_and_parser_rejects_duplicate_slots() -> (
    None
):
    response_format = semantic_proposition_response_format(
        ["E1:S1", "E2:S1"],
        ["support:proposition", "support:left_subject"],
    )
    schema_text = json.dumps(response_format)
    assert "uniqueItems" not in schema_text
    assert "E1:S1" not in schema_text
    assert response_format == semantic_proposition_response_format(
        [f"E{index}:S{index}" for index in range(1, 101)],
        ["support:proposition", "support:left_subject"],
    )

    response = json.loads(_model_response())
    response["premises"][0]["supports_slot_ids"] = [
        "support:proposition",
        "support:proposition",
    ]
    packed = _packed_premises(2)

    assert (
        parse_semantic_proposition_result(
            json.dumps(response),
            packed=packed,
            slot_ids={
                "support:proposition",
                "support:left_subject",
                "support:right_subject",
            },
            model="semantic-test-model",
            seed=17,
        )
        is None
    )


@pytest.mark.parametrize(
    ("premise_count", "each_premise_required", "accepted"),
    (
        (1, True, False),
        (2, True, True),
        (4, True, True),
        (5, True, False),
        (2, False, False),
    ),
)
def test_composite_conjunction_has_a_bounded_all_required_premise_contract(
    premise_count: int,
    each_premise_required: bool,
    accepted: bool,
) -> None:
    response = {
        "verdict": "yes",
        "support_mode": "evidence_set",
        "proof_mode": "composite_conjunction",
        "jointly_complete": True,
        "each_premise_required": each_premise_required,
        "premises": [
            {
                "span_selector": f"E{index}:S1",
                "proposition_fragment": f"premise {index} is stated",
                "supports_slot_ids": ["support:proposition"],
            }
            for index in range(1, premise_count + 1)
        ],
    }
    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(premise_count),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
    )

    if accepted:
        assert parsed.value is not None
        assert parsed.value["proof_mode"] == "composite_conjunction"
        assert len(parsed.value["premises"]) == premise_count
    else:
        assert parsed.value is None
        assert parsed.failure_reason in {
            "composite_conjunction_contract_invalid",
            "verdict_payload_inconsistent",
            "premise_collection_invalid",
        }


def test_atomic_semantic_accepts_one_complete_premise_without_conjunction() -> None:
    response = {
        "verdict": "yes",
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": "E1:S1",
                "proposition_fragment": "the complete proposition is established",
                "supports_slot_ids": ["support:proposition"],
            }
        ],
    }
    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
    )

    assert parsed.value is not None
    assert parsed.value["proof_mode"] == "atomic_semantic"
    assert len(parsed.value["premises"]) == 1


def test_premise_selector_must_bind_to_a_canonical_span() -> None:
    response = {
        "verdict": "yes",
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": "E1:S9",
                "proposition_fragment": "the complete proposition is established",
                "supports_slot_ids": ["support:proposition"],
            }
        ],
    }
    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
    )

    assert parsed.value is None
    assert parsed.failure_reason == "premise_value_invalid"
