from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_authority_schema import SEMANTIC_PROPOSITION_VERDICT_CONTRACT
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.semantic_entailment_audit import semantic_entailment_audit_attestation


def semantic_verdict(
    request: Any,
    question: str,
    _answer: str,
    bundle: Any,
) -> dict[str, Any]:
    """Build one fully audited semantic-authority benchmark fixture."""

    bundle.metadata["semantic_proposition_verifier"] = _runtime_trace()
    slot_ids = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]
    premises = _premises(bundle.items, slot_ids)
    response: dict[str, Any] = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "verdict": "yes",
        "support_mode": "evidence_set",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": premises,
        "verifier": {
            "contract_id": "grounded_semantic_verifier.v1",
            "model": "test-double",
            "seed": 7,
        },
    }
    response["entailment_audit"] = semantic_entailment_audit_attestation(
        question,
        "yes",
        premises,
        model="independent-test-auditor",
        seed=8,
    )
    bundle.metadata["semantic_proposition_verifier"]["audit_proposal_digest"] = (
        response["entailment_audit"]["proposal_digest"]
    )
    return response


def _runtime_trace() -> dict[str, Any]:
    return {
        "contract_id": "semantic_proposition_verifier_runtime.v1",
        "status": "parsed",
        "reason": "strict_schema_and_entailment_audit",
        "actual_model_call_count": 2,
        "proposal_model_call_count": 1,
        "audit_model_call_count": 1,
        "available_evidence_count": 2,
        "packed_evidence_count": 2,
        "evidence_item_char_limit": 2000,
        "estimated_input_token_budget": 3072,
        "estimated_input_tokens": 220,
        "minimum_model_context_tokens": 4096,
        "packed_evidence_chars": 107,
        "dropped_evidence_count": 0,
        "truncated_evidence_count": 0,
        "required_slot_count": 3,
        "prompt_chars": 731,
        "max_prompt_chars": 16000,
        "max_output_tokens": 768,
        "verdict": "yes",
        "proposal_retry_count": 0,
        "initial_parse_failure_reason": "",
        "parse_failure_reason": "",
        "response_finish_reason": "stop",
        "response_completion_tokens": 244,
        "response_chars": 910,
        "audit_status": "verified",
        "audit_reason": "",
        "audit_contract_id": "semantic_entailment_audit.v1",
        "audit_model": "independent-test-auditor",
        "audit_retry_count": 0,
        "audit_initial_parse_failure_reason": "",
        "audit_parse_failure_reason": "",
        "audit_response_finish_reason": "stop",
        "audit_response_completion_tokens": 94,
        "audit_response_chars": 346,
    }


def _premises(
    items: list[dict[str, Any]],
    slot_ids: list[str],
) -> list[dict[str, Any]]:
    premises = []
    for index, item in enumerate(items):
        side = "left_subject" if index == 0 else "right_subject"
        premises.append(
            {
                "evidence_id": identity_of(item).key,
                "quote": item["text"],
                "proposition_fragment": (
                    "cross-language evaluation was performed"
                    if index == 0
                    else "single-language baselines were compared"
                ),
                "supports_slot_ids": [
                    slot_id
                    for slot_id in slot_ids
                    if slot_id == "support:proposition" or slot_id.endswith(side)
                ],
            }
        )
    return premises
