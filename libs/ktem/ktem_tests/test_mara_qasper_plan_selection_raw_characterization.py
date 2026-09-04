from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import ValidationError, validate
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)
from ktem.reasoning.mara_semantic_proposition_transaction import (
    run_semantic_proposition_transaction,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "qasper_provider_10384454_raw_responses.json"
)
QUESTION = "Did the authors release the code for the evaluated system?"
SLOT_ID = "support:boolean_proposition"
SELECTOR_ID = "E1:S1"
APPLICABLE_SLOTS = ("actor", "predicate", "object")


def _fixtures() -> list[dict[str, str]]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _packed(case: dict[str, str]) -> list[dict[str, Any]]:
    text = case["evidence_text"]
    return [
        {
            "evidence_id": "provider-10384454-evidence",
            "required_slot_ids": [SLOT_ID],
            "selectors": [
                {
                    "selector_id": SELECTOR_ID,
                    "text": text,
                    "span_start": 0,
                    "span_end": len(text),
                    "event_id": "provider-10384454-event",
                    "object_tokens": ["code", "component", "metric"],
                    "event_core_tokens": ["code", "component", "metric"],
                    "predicate_match_kind": "exact",
                    "local_relation_state": case["local_relation_state"],
                    "proposition_slot_spans": {},
                }
            ],
        }
    ]


def _allowed_plan(case: dict[str, str]) -> dict[str, dict[str, Any]]:
    plan_id = case["plan_id"]
    return {
        plan_id: {
            "plan_id": plan_id,
            "polarity_relation": case["polarity_relation"],
            "span_refs": [SELECTOR_ID],
            "slot_refs": {
                "actor": [SELECTOR_ID],
                "predicate": [SELECTOR_ID],
                "object": [SELECTOR_ID],
            },
            "event_binding_id": "provider-10384454-event",
        }
    }


@pytest.mark.parametrize("case", _fixtures(), ids=lambda case: case["case_id"])
def test_live_raw_response_stops_at_plan_selection_boundary(
    case: dict[str, str],
) -> None:
    raw_response = case["raw_response"]
    assert (
        hashlib.sha256(raw_response.encode()).hexdigest() == case["raw_response_sha256"]
    )
    response_format = semantic_proposition_response_format(
        [SELECTOR_ID],
        [SLOT_ID],
        candidate=case["candidate"],
        applicable_proposition_slots=APPLICABLE_SLOTS,
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        allowed_proposition_evidence_plans=_allowed_plan(case),
    )
    with pytest.raises(ValidationError):
        validate(
            instance=json.loads(raw_response),
            schema=response_format["json_schema"]["schema"],
        )

    parsed = parse_semantic_proposition_response(
        raw_response,
        packed=_packed(case),
        slot_ids={SLOT_ID},
        model="provider-10384454-characterization",
        seed=20260829,
        candidate=case["candidate"],
        applicable_proposition_slots=APPLICABLE_SLOTS,
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        allowed_proposition_evidence_plans=_allowed_plan(case),
    )

    assert parsed.value is None
    assert parsed.failure_reason == "plan_selection_schema_invalid"


@pytest.mark.parametrize("case", _fixtures(), ids=lambda case: case["case_id"])
def test_local_plan_selection_projects_the_complete_semantic_proof(
    case: dict[str, str],
) -> None:
    payload = {
        "candidate_judgment": case["candidate_judgment"],
        "canonical_evidence_plan_id": case["plan_id"],
    }
    response_format = semantic_proposition_response_format(
        [SELECTOR_ID],
        [SLOT_ID],
        candidate=case["candidate"],
        applicable_proposition_slots=APPLICABLE_SLOTS,
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        allowed_proposition_evidence_plans=_allowed_plan(case),
    )
    schema = response_format["json_schema"]["schema"]

    assert set(schema["properties"]) == {
        "candidate_judgment",
        "canonical_evidence_plan_id",
    }
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["additionalProperties"] is False
    validate(instance=payload, schema=schema)

    parsed = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=_packed(case),
        slot_ids={SLOT_ID},
        model="provider-10384454-characterization",
        seed=20260829,
        candidate=case["candidate"],
        applicable_proposition_slots=APPLICABLE_SLOTS,
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        slot_evidence_refs={SLOT_ID: [SELECTOR_ID]},
        allowed_proposition_evidence_plans=_allowed_plan(case),
    )

    assert parsed.failure_reason == ""
    assert parsed.value is not None
    assert parsed.value["canonical_evidence_plan_id"] == case["plan_id"]
    assert parsed.value["candidate_judgment"] == case["candidate_judgment"]
    assert parsed.value["verdict"] == case["expected_verdict"]
    assert parsed.value["evidence_relation"] == case["polarity_relation"]
    assert parsed.value["proof_mode"] == "atomic_semantic"
    assert parsed.value["jointly_complete"] is True
    assert parsed.value["each_premise_required"] is True
    assert parsed.value["premises"] == [
        {
            "evidence_id": "provider-10384454-evidence",
            "span_selector": SELECTOR_ID,
            "quote": case["evidence_text"],
            "span_start": 0,
            "span_end": len(case["evidence_text"]),
            "canonical_start": None,
            "canonical_end": None,
            "proposition_fragment": case["evidence_text"],
            "supports_slot_ids": [SLOT_ID],
            "binds_proposition_slots": list(APPLICABLE_SLOTS),
            "event_id": "provider-10384454-event",
            "object_tokens": ["code", "component", "metric"],
            "event_core_tokens": ["code", "component", "metric"],
            "predicate_match_kind": "exact",
            "local_relation_state": case["local_relation_state"],
            "proposition_slot_spans": {},
            "semantic_alignment": {},
        }
    ]


def test_plan_selection_rejects_alias_and_model_projected_fields() -> None:
    case = _fixtures()[0]
    payloads = [
        {
            "candidate_judgment": case["candidate_judgment"],
            "plan_id": case["plan_id"],
        },
        {
            "candidate_judgment": case["candidate_judgment"],
            "canonical_evidence_plan_id": case["plan_id"],
            "premises": [],
        },
        {
            "candidate_judgment": case["candidate_judgment"],
            "canonical_evidence_plan_id": {"plan_id": case["plan_id"]},
        },
    ]

    for payload in payloads:
        parsed = parse_semantic_proposition_response(
            json.dumps(payload),
            packed=_packed(case),
            slot_ids={SLOT_ID},
            model="provider-10384454-characterization",
            seed=20260829,
            candidate=case["candidate"],
            applicable_proposition_slots=APPLICABLE_SLOTS,
            allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
            slot_evidence_refs={SLOT_ID: [SELECTOR_ID]},
            allowed_proposition_evidence_plans=_allowed_plan(case),
        )
        assert parsed.value is None
        assert parsed.failure_reason == "plan_selection_schema_invalid"


def test_bound_frozen_plan_cannot_be_bypassed_with_unknown() -> None:
    case = _fixtures()[0]
    payload = {
        "candidate_judgment": "unknown",
        "canonical_evidence_plan_id": "",
    }
    response_format = semantic_proposition_response_format(
        [SELECTOR_ID],
        [SLOT_ID],
        candidate=case["candidate"],
        applicable_proposition_slots=APPLICABLE_SLOTS,
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        allowed_proposition_evidence_plans=_allowed_plan(case),
    )

    with pytest.raises(ValidationError):
        validate(
            instance=payload,
            schema=response_format["json_schema"]["schema"],
        )
    parsed = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=_packed(case),
        slot_ids={SLOT_ID},
        model="provider-10384454-characterization",
        seed=20260829,
        candidate=case["candidate"],
        applicable_proposition_slots=APPLICABLE_SLOTS,
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        slot_evidence_refs={SLOT_ID: [SELECTOR_ID]},
        allowed_proposition_evidence_plans=_allowed_plan(case),
    )

    assert parsed.value is None
    assert parsed.failure_reason == "candidate_judgment_plan_mismatch"


def test_mismatched_frozen_plan_identity_is_not_a_legal_choice() -> None:
    case = _fixtures()[0]
    allowed_plans = _allowed_plan(case)
    allowed_plans[case["plan_id"]]["plan_id"] = "different-local-plan"
    payload = {
        "candidate_judgment": case["candidate_judgment"],
        "canonical_evidence_plan_id": case["plan_id"],
    }
    response_format = semantic_proposition_response_format(
        [SELECTOR_ID],
        [SLOT_ID],
        candidate=case["candidate"],
        applicable_proposition_slots=APPLICABLE_SLOTS,
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        allowed_proposition_evidence_plans=allowed_plans,
    )

    with pytest.raises(ValidationError):
        validate(
            instance=payload,
            schema=response_format["json_schema"]["schema"],
        )
    parsed = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=_packed(case),
        slot_ids={SLOT_ID},
        model="provider-10384454-characterization",
        seed=20260829,
        candidate=case["candidate"],
        applicable_proposition_slots=APPLICABLE_SLOTS,
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        slot_evidence_refs={SLOT_ID: [SELECTOR_ID]},
        allowed_proposition_evidence_plans=allowed_plans,
    )

    assert parsed.value is None
    assert parsed.failure_reason == "canonical_evidence_plan_id_invalid"


class _RawResponseLLM:
    model_name = "provider-10384454-characterization"

    def __init__(self, response: str) -> None:
        self.response = response

    def __call__(self, _messages: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(text=self.response)


@pytest.mark.parametrize("case", _fixtures(), ids=lambda case: case["case_id"])
def test_failed_transaction_records_first_data_lineage_inconsistency(
    case: dict[str, str],
) -> None:
    llm = _RawResponseLLM(case["raw_response"])

    result = run_semantic_proposition_transaction(
        llm,
        llm,
        f"STRUCTURED CANDIDATE TO VERIFY:\n{case['candidate']}",
        question=QUESTION,
        packed=_packed(case),
        slots=[
            {
                "slot_id": SLOT_ID,
                "description": "Boolean proposition",
                "evidence_refs": [SELECTOR_ID],  # type: ignore[dict-item]
            }
        ],
        proposal_model=llm.model_name,
        audit_model=llm.model_name,
        seed=20260829,
        semantic_pack_digest="provider-10384454-pack",
        canonical_span_universe_digest="provider-10384454-span-universe",
        candidate_transaction_id="provider-10384454-candidate",
        allowed_proposition_slot_bindings={SELECTOR_ID: APPLICABLE_SLOTS},
        allowed_proposition_evidence_plans=_allowed_plan(case),
    )

    assert result.status == "failed"
    lineage = result.diagnostics["semantic_data_lineage"]
    assert lineage["contract_id"] == "semantic_proposition_data_lineage.v1"
    assert lineage["status"] == "failed"
    assert lineage["proposal_contract"]["mode"] == "canonical_plan_selection"
    assert lineage["proposal_contract"]["allowed_plan_ids"] == [case["plan_id"]]
    assert len(lineage["proposal_contract"]["response_schema_digest"]) == 64
    assert lineage["local_projection"]["status"] == "not_run"
    assert lineage["audit"]["status"] == "not_run"
    assert len(lineage["proposal_attempts"]) == 2
    assert {
        attempt["raw_response_digest"] for attempt in lineage["proposal_attempts"]
    } == {case["raw_response_sha256"]}
    assert result.audit_call_count == 0
    assert lineage["first_inconsistency"] == {
        "stage": "proposal_parse",
        "reason": "plan_selection_schema_invalid",
        "attempt": 1,
        "raw_response_digest": case["raw_response_sha256"],
    }
