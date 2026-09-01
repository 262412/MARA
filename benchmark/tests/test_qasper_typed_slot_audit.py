from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_identity import identity_of

from benchmark.execution_slot_contract_metrics import required_slot_reference_metrics

TypedProjection = tuple[dict[str, Any], dict[str, Any], dict[str, Any]]


def test_complete_typed_authority_is_not_a_generic_semantic_false_fill() -> None:
    prediction, metadata, evidence = _typed_boolean_projection()

    metrics = required_slot_reference_metrics(prediction, metadata, [evidence])

    assert metrics["slot_semantic_false_fill_count"] == 0.0


def test_invalid_typed_authority_remains_a_semantic_false_fill() -> None:
    prediction, metadata, evidence = _typed_boolean_projection()
    prediction = deepcopy(prediction)
    decision = prediction["engine_verify_decision"]
    decision["typed_authority"]["authority_atoms"][0]["span_end"] -= 1

    metrics = required_slot_reference_metrics(prediction, metadata, [evidence])

    assert metrics["slot_semantic_false_fill_count"] == 1.0


def _typed_boolean_projection() -> TypedProjection:
    slot_id = "support:boolean_proposition"
    text = (
        "Table TABREF5 shows that the GluonCV/GluonNLP implementation matches "
        "or outperforms the compared open source implementation."
    )
    evidence = {
        "source_id": "runtime-paper",
        "evidence_id": "toolkit-results",
        "text": text,
    }
    evidence_id = identity_of(evidence).key
    evidence_ref = f"{evidence_id}#quote:0:{len(text)}"
    atom = {
        "evidence_id": evidence_id,
        "evidence_ref": evidence_ref,
        "span_id": evidence_ref,
        "quote": text,
        "span_start": 0,
        "span_end": len(text),
        "actor": "current_paper",
        "relation": "evaluate",
        "predicate": "evaluate",
        "object": "toolkit",
        "arguments": ["toolkit"],
        "polarity": "yes",
        "qualifier": "none",
        "quantifier": "none",
        "scope": "results",
        "section_scope": "results",
    }
    claim_result = {
        "status": "supported",
        "authority_status": "exact",
        "verified_slot_state": "verified_support",
        "verified_support_slot_ids": [slot_id],
    }
    authority = {
        "contract_id": "typed_proposition_authority.v1",
        "state": "verified_support",
        "required_slot_ids": [slot_id],
        "verified_slot_ids": [slot_id],
        "slot_bindings": {slot_id: [evidence_id]},
        "authority_atoms": [atom],
    }
    decision = {
        "status": "supported",
        "action": "generate",
        "verified_citations": [evidence_id],
        "claim_results": [claim_result],
        "typed_authority": authority,
    }
    metadata = {
        "query_plan": {
            "answer_type": "boolean",
            "question_type": "simple_fact",
            "constraints": {"verification_domain": "qasper"},
            "evidence_slots": [
                {
                    "slot_id": slot_id,
                    "role": "support",
                    "metric": "they experiment with toolkits",
                    "statement_kind": "boolean_proposition",
                    "required": True,
                    "required_for_verification": True,
                    "status": "verified_support",
                    "evidence_ids": [evidence_id],
                }
            ],
        }
    }
    prediction = {
        "question": "Do they experiment with the toolkits?",
        "answer_type": "boolean",
        "gold_answers": ["yes"],
        "engine_verify_decision": decision,
        "engine_terminal_evidence_bundle": {"items": [evidence]},
    }
    return prediction, metadata, evidence
