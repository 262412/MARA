from __future__ import annotations

import json
from typing import Any

import pytest
from jsonschema import ValidationError, validate
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)

CONTROLLED_BRANCHES = (
    ("yes", "supported"),
    ("yes", "contradicted"),
    ("yes", "unknown"),
    ("no", "supported"),
    ("no", "contradicted"),
    ("no", "unknown"),
    ("unanswerable", "contradicted"),
    ("unanswerable", "unknown"),
)
APPLICABLE_PROPOSITION_SLOTS = ("actor", "predicate", "object")
SLOT_IDS = ("support:proposition",)
ALLOWED_BINDINGS = {"E1:S1": APPLICABLE_PROPOSITION_SLOTS}


def _packed() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "evidence-1",
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": "The source establishes the complete proposition.",
                    "span_start": 0,
                    "span_end": 48,
                }
            ],
        }
    ]


def _response(candidate: str, judgment: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "candidate_judgment": judgment,
        "support_mode": "evidence_set",
        "jointly_complete": judgment != "unknown",
        "each_premise_required": judgment != "unknown",
        "not_applicable_proposition_slots": ["quantifier"],
        "premises": [],
    }
    if judgment != "unknown":
        payload["premises"] = [
            {
                "span_selector": "E1:S1",
                "proposition_fragment": "the complete proposition is established",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": list(APPLICABLE_PROPOSITION_SLOTS),
            }
        ]
    else:
        payload["unknown_assessment"] = {
            "reviewed_span_selectors": ["E1:S1"],
            "unresolved_proposition_slots": "predicate",
            "support_gap": "The predicate is not established.",
            "contradiction_gap": "The predicate is not explicitly contradicted.",
        }
    if candidate == "unanswerable" and judgment == "contradicted":
        payload["evidence_relation"] = "proposition_support"
    return payload


def _schema(candidate: str) -> dict[str, Any]:
    return semantic_proposition_response_format(
        ["E1:S1"],
        list(SLOT_IDS),
        candidate=candidate,
        applicable_proposition_slots=APPLICABLE_PROPOSITION_SLOTS,
        allowed_proposition_slot_bindings=ALLOWED_BINDINGS,
    )["json_schema"]["schema"]


@pytest.mark.parametrize(("candidate", "judgment"), CONTROLLED_BRANCHES)
def test_candidate_specific_schema_payload_is_parser_accepted(
    candidate: str,
    judgment: str,
) -> None:
    payload = _response(candidate, judgment)

    validate(instance=payload, schema=_schema(candidate))
    parsed = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=_packed(),
        slot_ids=set(SLOT_IDS),
        model="semantic-test-model",
        seed=17,
        candidate=candidate,
        applicable_proposition_slots=APPLICABLE_PROPOSITION_SLOTS,
        allowed_proposition_slot_bindings=ALLOWED_BINDINGS,
    )

    assert parsed.failure_reason == ""
    assert parsed.value is not None
    assert parsed.value["candidate_judgment"] == judgment
    if judgment == "unknown":
        assert parsed.value["unknown_assessment"]["unresolved_proposition_slots"] == [
            "predicate"
        ]


_DUPLICATE_BRANCHES = tuple(
    (candidate, judgment)
    for candidate, judgment in CONTROLLED_BRANCHES
    if judgment == "unknown"
)


@pytest.mark.parametrize(("candidate", "judgment"), _DUPLICATE_BRANCHES)
def test_unknown_schema_rejects_duplicate_canonical_slot_set(
    candidate: str,
    judgment: str,
) -> None:
    payload = _response(candidate, judgment)
    payload["unknown_assessment"][
        "unresolved_proposition_slots"
    ] = "predicate|predicate"

    with pytest.raises(ValidationError):
        validate(instance=payload, schema=_schema(candidate))
