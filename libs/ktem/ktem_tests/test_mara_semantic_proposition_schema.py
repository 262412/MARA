from __future__ import annotations

import json

import pytest
from jsonschema import validate
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    parse_semantic_proposition_result,
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


def test_response_schema_omits_runtime_selector_ids_and_parser_rejects_duplicate_slots() -> (
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
        "evidence_relation": "proposition_support",
        "support_mode": "evidence_set",
        "proof_mode": "composite_conjunction",
        "jointly_complete": True,
        "each_premise_required": each_premise_required,
        "premises": [
            {
                "span_selector": f"E{index}:S1",
                "proposition_fragment": f"premise {index} is stated",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                    "quantifier",
                ],
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
            "proof_mode_premise_count_mismatch",
            "verdict_payload_inconsistent",
            "premise_collection_invalid",
        }


def test_atomic_semantic_accepts_one_complete_premise_without_conjunction() -> None:
    response = {
        "verdict": "yes",
        "evidence_relation": "proposition_support",
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": "E1:S1",
                "proposition_fragment": "the complete proposition is established",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                    "quantifier",
                ],
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
        "evidence_relation": "proposition_support",
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": "E1:S9",
                "proposition_fragment": "the complete proposition is established",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                    "quantifier",
                ],
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


@pytest.mark.parametrize(
    ("candidate_judgment", "evidence_relation"),
    (
        ("supported", "proposition_support"),
        ("contradicted", "explicit_contradiction"),
    ),
)
def test_supported_or_contradicted_contract_rejects_unknown_assessment(
    candidate_judgment: str,
    evidence_relation: str,
) -> None:
    response = {
        "candidate_judgment": candidate_judgment,
        "evidence_relation": evidence_relation,
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": "E1:S1",
                "proposition_fragment": "the complete proposition is established",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                    "quantifier",
                ],
            }
        ],
        "unknown_assessment": {
            "reviewed_span_selectors": ["E1:S1"],
            "unresolved_proposition_slots": ["predicate"],
            "support_gap": "A support gap is not valid for this judgment.",
            "contradiction_gap": "A contradiction gap is not valid for this judgment.",
        },
    }

    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
        candidate="yes",
    )

    assert parsed.value is None
    assert parsed.failure_reason == "unexpected_unknown_assessment"


def test_unknown_contract_requires_non_empty_assessment_and_no_premises() -> None:
    response = {
        "candidate_judgment": "unknown",
        "evidence_relation": "undetermined",
        "support_mode": "evidence_set",
        "proof_mode": "none",
        "jointly_complete": False,
        "each_premise_required": False,
        "premises": [],
    }

    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
        candidate="yes",
    )

    assert parsed.value is None
    assert parsed.failure_reason == "unknown_assessment_schema_invalid"

    response["unknown_assessment"] = {
        "reviewed_span_selectors": ["E1:S1"],
        "unresolved_proposition_slots": ["predicate"],
        "support_gap": "The reviewed span does not establish the predicate.",
        "contradiction_gap": "The reviewed span does not explicitly contradict it.",
    }
    response["premises"] = [
        {
            "span_selector": "E1:S1",
            "proposition_fragment": "a conflicting proof must not be retained",
            "supports_slot_ids": ["support:proposition"],
            "binds_proposition_slots": ["predicate"],
        }
    ]

    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
        candidate="yes",
    )

    assert parsed.value is None
    assert parsed.failure_reason == "verdict_payload_inconsistent"


def test_response_schema_has_physically_disjoint_judgment_contracts() -> None:
    schema = semantic_proposition_response_format([], ["support:proposition"])[
        "json_schema"
    ]["schema"]

    branches = schema.get("oneOf")
    assert isinstance(branches, list)
    assert len(branches) == 3

    by_judgment = {
        tuple(branch["properties"]["candidate_judgment"].get("enum", [])): branch
        for branch in branches
    }
    assert set(by_judgment) == {
        ("supported",),
        ("contradicted",),
        ("unknown",),
    }
    for judgment in ("supported", "contradicted"):
        branch = by_judgment[(judgment,)]
        assert "unknown_assessment" not in branch["properties"]
        assert "unknown_assessment" not in branch["required"]
        assert "proof_mode" not in branch["properties"]
        assert "proof_mode" not in branch["required"]
        assert branch["properties"]["premises"]["minItems"] == 1
    unknown = by_judgment[("unknown",)]
    assert "unknown_assessment" in unknown["properties"]
    assert "unknown_assessment" in unknown["required"]
    assert "proof_mode" not in unknown["properties"]
    assert "proof_mode" not in unknown["required"]
    assert unknown["properties"]["premises"]["maxItems"] == 0


def test_unspecified_candidate_unknown_branch_requires_undetermined_relation() -> None:
    schema = semantic_proposition_response_format([], ["support:proposition"])[
        "json_schema"
    ]["schema"]
    unknown = next(
        branch
        for branch in schema["oneOf"]
        if branch["properties"]["candidate_judgment"]["enum"] == ["unknown"]
    )
    assert unknown["properties"]["evidence_relation"]["enum"] == ["undetermined"]
    assert "evidence_relation" in unknown["required"]

    response = {
        "candidate_judgment": "unknown",
        "support_mode": "evidence_set",
        "proof_mode": "none",
        "jointly_complete": False,
        "each_premise_required": False,
        "premises": [],
        "unknown_assessment": {
            "reviewed_span_selectors": ["E1:S1"],
            "unresolved_proposition_slots": ["predicate"],
            "support_gap": "No support.",
            "contradiction_gap": "No contradiction.",
        },
    }
    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
    )
    assert parsed.value is None
    assert parsed.failure_reason == "evidence_relation_invalid"


def test_candidate_bound_schema_projects_yes_no_relation_locally() -> None:
    yes_schema = semantic_proposition_response_format(
        [], ["support:proposition"], candidate="yes"
    )["json_schema"]["schema"]
    no_schema = semantic_proposition_response_format(
        [], ["support:proposition"], candidate="no"
    )["json_schema"]["schema"]
    assert "evidence_relation" not in yes_schema["properties"]
    assert "evidence_relation" not in yes_schema["required"]
    assert "evidence_relation" not in no_schema["properties"]
    assert "evidence_relation" not in no_schema["required"]
    assert "proof_mode" not in yes_schema["properties"]
    assert "proof_mode" not in yes_schema["required"]
    assert "proof_mode" not in no_schema["properties"]
    assert "proof_mode" not in no_schema["required"]

    cases = (
        ("yes", "supported", "proposition_support", "yes"),
        ("yes", "contradicted", "explicit_contradiction", "no"),
        ("no", "supported", "explicit_contradiction", "no"),
        ("no", "contradicted", "proposition_support", "yes"),
    )
    for candidate, judgment, relation, verdict in cases:
        response = {
            "candidate_judgment": judgment,
            "support_mode": "evidence_set",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "span_selector": "E1:S1",
                    "proposition_fragment": "the complete proposition is established",
                    "supports_slot_ids": ["support:proposition"],
                    "binds_proposition_slots": [
                        "actor",
                        "predicate",
                        "object",
                        "quantifier",
                    ],
                }
            ],
        }
        parsed = parse_semantic_proposition_response(
            json.dumps(response),
            packed=_packed_premises(1),
            slot_ids={"support:proposition"},
            model="semantic-test-model",
            seed=17,
            candidate=candidate,
        )
        assert parsed.value is not None
        assert parsed.value["evidence_relation"] == relation
        assert parsed.value["verdict"] == verdict
        assert parsed.value["proof_mode"] == "atomic_semantic"


@pytest.mark.parametrize(
    ("candidate_judgment", "premise_count", "expected_proof_mode"),
    (
        ("supported", 1, "atomic_semantic"),
        ("contradicted", 2, "composite_conjunction"),
        ("unknown", 0, "none"),
    ),
)
def test_candidate_schema_payload_is_parser_identical_with_local_proof_mode(
    candidate_judgment: str,
    premise_count: int,
    expected_proof_mode: str,
) -> None:
    payload: dict[str, object] = {
        "candidate_judgment": candidate_judgment,
        "support_mode": "evidence_set",
        "jointly_complete": candidate_judgment != "unknown",
        "each_premise_required": candidate_judgment != "unknown",
        "premises": [
            {
                "span_selector": f"E{index}:S1",
                "proposition_fragment": f"premise {index} is stated",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                    "quantifier",
                ],
            }
            for index in range(1, premise_count + 1)
        ],
    }
    if candidate_judgment == "unknown":
        payload["unknown_assessment"] = {
            "reviewed_span_selectors": ["E1:S1"],
            "unresolved_proposition_slots": "predicate",
            "support_gap": "The predicate is not established.",
            "contradiction_gap": "The predicate is not explicitly contradicted.",
        }
    schema = semantic_proposition_response_format(
        [],
        ["support:proposition"],
        candidate="yes",
    )["json_schema"]["schema"]

    validate(instance=payload, schema=schema)
    parsed = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=_packed_premises(max(1, premise_count)),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
        candidate="yes",
    )

    assert parsed.failure_reason == ""
    assert parsed.value is not None
    assert parsed.value["proof_mode"] == expected_proof_mode


def test_unanswerable_candidate_rejects_supported_without_direction() -> None:
    response = {
        "candidate_judgment": "supported",
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": "E1:S1",
                "proposition_fragment": "the complete proposition is established",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                    "quantifier",
                ],
            }
        ],
    }
    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
        candidate="unanswerable",
    )
    assert parsed.value is None
    assert parsed.failure_reason == "candidate_judgment_relation_mismatch"


def test_modern_contract_records_quantifier_none_as_explicit_na() -> None:
    response = {
        "candidate_judgment": "supported",
        "evidence_relation": "proposition_support",
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "not_applicable_proposition_slots": ["quantifier"],
        "premises": [
            {
                "span_selector": "E1:S1",
                "proposition_fragment": "the proposition is established",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": ["actor", "predicate", "object"],
            }
        ],
    }
    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
        candidate="yes",
        applicable_proposition_slots={"actor", "predicate", "object"},
    )

    assert parsed.value is not None
    assert parsed.value["not_applicable_proposition_slots"] == ["quantifier"]
    assert {
        slot
        for premise in parsed.value["premises"]
        for slot in premise["binds_proposition_slots"]
    } == {"actor", "predicate", "object"}


def test_modern_contract_rejects_quantifier_evidence_when_quantifier_is_none() -> None:
    response = {
        "candidate_judgment": "supported",
        "evidence_relation": "proposition_support",
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "not_applicable_proposition_slots": ["quantifier"],
        "premises": [
            {
                "span_selector": "E1:S1",
                "proposition_fragment": "the proposition is established",
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                    "quantifier",
                ],
            }
        ],
    }
    parsed = parse_semantic_proposition_response(
        json.dumps(response),
        packed=_packed_premises(1),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
        candidate="yes",
        applicable_proposition_slots={"actor", "predicate", "object"},
    )

    assert parsed.value is None
    assert parsed.failure_reason == "premise_proposition_binding_invalid"
