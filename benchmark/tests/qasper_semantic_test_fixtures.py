from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.frozen_canonical_proposition_projection import (
    frozen_canonical_plan_projection_from_bundle,
    frozen_slot_support_by_ref,
)
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.reasoning.mara_qasper_semantic_pack import (
    freeze_qasper_canonical_semantic_pack,
    prepare_qasper_canonical_records,
    qasper_canonical_evidence_plans,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)
from ktem_tests.semantic_entailment_test_helpers import audited_verdict


def semantic_verdict(
    request: Any,
    question: str,
    answer: str,
    bundle: Any,
) -> dict[str, Any]:
    """Build one fully audited semantic-authority benchmark fixture."""

    projection, identity = _freeze_semantic_plan(request, question, bundle)
    pack = bundle.metadata["qasper_canonical_semantic_pack"]
    bundle.metadata["qasper_candidate_generation"] = {
        "canonical_semantic_pack_digest": identity["semantic_pack_digest"],
        "canonical_span_universe_digest": identity["span_universe_digest"],
        "transaction_id": identity["candidate_transaction_id"],
        "candidate_evidence_set_binding": deepcopy(pack["proposition_binding"]),
        "required_slots": deepcopy(pack["slots"]),
    }
    bundle.metadata["semantic_proposition_verifier"] = _runtime_trace(identity)
    response: dict[str, Any] = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "verdict": "yes",
        "support_mode": "evidence_set",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": deepcopy(list(projection.premises)),
        "canonical_evidence_plan_id": projection.plan_id,
        "canonical_plan_digest": projection.plan_digest,
        "verifier_input_candidate": str(answer or "").strip().casefold(),
        "candidate_verification_status": "supported",
        "replacement_candidate_allowed": False,
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": "test-double",
            "seed": 7,
            "semantic_pack_digest": identity["semantic_pack_digest"],
            "canonical_span_universe_digest": identity["span_universe_digest"],
            "candidate_transaction_id": identity["candidate_transaction_id"],
            "canonical_plan_digest": projection.plan_digest,
            "canonical_pack_continuity_status": "preserved",
        },
    }
    response = audited_verdict(
        response,
        question,
        canonical_plan_projection=projection,
    )
    response["verifier"]["release_mode"] = True
    response["entailment_audit"]["semantic_pack_identity"] = identity
    bundle.metadata["semantic_proposition_verifier"][
        "audit_proposal_digest"
    ] = response["entailment_audit"]["proposal_digest"]
    return response


def _freeze_semantic_plan(
    request: Any,
    question: str,
    bundle: Any,
) -> tuple[Any, dict[str, str]]:
    slots = required_semantic_proposition_slots(request)
    source = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )
    transaction_id = "semantic-authority-fixture"
    frozen = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        slots=slots,
        source_packing=source,
        records=prepare_qasper_canonical_records(question, source.records),
        candidate_transaction_id=transaction_id,
    )
    plans = qasper_canonical_evidence_plans(bundle)
    assert plans is not None and len(plans) == 1
    plan_id, plan = next(iter(plans.items()))
    pack = bundle.metadata["qasper_canonical_semantic_pack"]
    support_by_ref, reason = frozen_slot_support_by_ref(
        plan["span_refs"], pack["slots"]
    )
    assert reason == "", reason
    proposition = build_question_proposition(question)
    projection, reason = frozen_canonical_plan_projection_from_bundle(
        bundle,
        plan_id=plan_id,
        proposition=proposition,
        expected_slots=applicable_proposition_evidence_slots(proposition),
        slot_support_by_ref=support_by_ref,
    )
    assert projection is not None and reason == "", reason
    return projection, {
        "semantic_pack_digest": frozen.semantic_pack_digest,
        "span_universe_digest": str(pack["span_universe_digest"]),
        "candidate_transaction_id": transaction_id,
    }


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


def _runtime_trace(identity: dict[str, str]) -> dict[str, Any]:
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
        "semantic_pack_digest": identity["semantic_pack_digest"],
        "canonical_span_universe_digest": identity["span_universe_digest"],
        "candidate_transaction_id": identity["candidate_transaction_id"],
        "canonical_pack_continuity_status": "preserved",
    }
