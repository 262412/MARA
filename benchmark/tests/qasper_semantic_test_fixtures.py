from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.evidence_identity import identity_of
from ktem_tests.semantic_entailment_test_helpers import audited_verdict


def semantic_verdict(
    request: Any,
    question: str,
    answer: str,
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
        "verifier_input_candidate": str(answer or "").strip().casefold(),
        "candidate_verification_status": "supported",
        "replacement_candidate_allowed": False,
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": "test-double",
            "seed": 7,
        },
    }
    response = audited_verdict(response, question)
    response["verifier"]["release_mode"] = True
    bundle.metadata["semantic_proposition_verifier"][
        "audit_proposal_digest"
    ] = response["entailment_audit"]["proposal_digest"]
    return response


def semantic_repair_diagnostics() -> dict[str, Any]:
    """Return trace fields produced by a repaired semantic transaction."""

    local_consistency = {
        "contract_id": "deterministic_local_premise_consistency.v1",
        "status": "auditor_internal_inconsistency",
        "inconsistent_premise_refs": ["P1"],
    }
    return {
        "question_proposition_resolution": {
            "contract_id": "question_proposition_resolution.v1",
            "status": "repaired",
        },
        "audit_call_rejection_count": 2,
        "auditor_internal_inconsistency": True,
        "auditor_internal_inconsistency_count": 1,
        "local_premise_consistency": local_consistency,
        "local_premise_consistency_history": [local_consistency],
        "audit_verified_but_runtime_rejected_count": 1,
        "runtime_contract_rejection_count": 1,
        "rejected_transactions": [
            {
                "runtime_rejection_reason": "semantic_premise_scope_rejected",
                "typed_conclusion": {"conclusion_id": "rejected"},
                "semantic_proof_digest": "before",
            }
        ],
        "semantic_proof_digest_before": "before",
        "semantic_proof_digest_after": "after",
        "semantic_proof_digest_changed": True,
        "polarity_contradiction_check": {
            "contract_id": "polarity_contradiction_check.v1",
            "status": "aligned",
        },
    }


def _runtime_trace() -> dict[str, Any]:
    return {
        "contract_id": "semantic_proposition_verifier_runtime.v3",
        "status": "parsed",
        "reason": "strict_schema_and_entailment_audit",
        "release_mode": True,
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
        "audit_contract_id": SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
        "audit_model": "independent-test-auditor",
        "audit_retry_count": 0,
        "audit_initial_parse_failure_reason": "",
        "audit_parse_failure_reason": "",
        "audit_response_finish_reason": "stop",
        "audit_response_completion_tokens": 94,
        "audit_response_chars": 346,
        "candidate_label": "yes",
        "candidate_verification_status": "supported",
        "replacement_candidate_allowed": False,
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
