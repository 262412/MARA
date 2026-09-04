from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.frozen_canonical_proposition_projection import (
    frozen_canonical_plan_projection_checked,
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
    qasper_canonical_selector_bindings,
    qasper_source_packing_observation,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
    semantic_proposition_verifier_prompt,
)
from ktem.reasoning.mara_semantic_proposition_transaction import (
    run_semantic_proposition_transaction,
)

QUESTION = "Did the authors compare the two systems?"


class _StaticLLM:
    def __init__(self, response: str, model_name: str) -> None:
        self.response = response
        self.model_name = model_name
        self.calls = 0

    def __call__(self, _messages: Any, **_kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(
            text=self.response,
            completion_tokens=0,
            prompt_tokens=0,
            finish_reason="stop",
        )


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        origin="benchmark",
        verification_domain="qasper",
        dataset_family="qasper",
        answer_type="boolean",
        question=QUESTION,
        query=QUESTION,
        query_plan={
            "answer_type": "boolean",
            "evidence_slots": [
                {
                    "slot_id": "support:boolean_proposition",
                    "required_for_verification": True,
                    "evidence_ids": [],
                    "evidence_refs": [],
                }
            ],
        },
    )


def _frozen_case() -> tuple[EvidenceBundle, Any, list[dict[str, Any]], dict[str, Any]]:
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "chunk-1",
                "source_id": "paper",
                "text": "The authors compared the two systems.",
            }
        ],
    )
    slots = required_semantic_proposition_slots(_request())
    source = pack_semantic_proposition_evidence(
        _request(),
        QUESTION,
        slots,
        bundle,
        candidate_priority=True,
    )
    frozen = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=QUESTION,
        slots=slots,
        source_packing=source,
        records=prepare_qasper_canonical_records(QUESTION, source.records),
        candidate_transaction_id="candidate-transaction-1",
    )
    frozen_slots = deepcopy(bundle.metadata["qasper_canonical_semantic_pack"]["slots"])
    plans = qasper_canonical_evidence_plans(bundle)
    assert plans is not None
    plan_id = next(iter(plans))
    plan = plans[plan_id]
    support_by_ref, reason = frozen_slot_support_by_ref(
        plan["span_refs"],
        frozen_slots,
    )
    assert reason == ""
    proposition = build_question_proposition(QUESTION)
    projection, reason = frozen_canonical_plan_projection_from_bundle(
        bundle,
        plan_id=plan_id,
        proposition=proposition,
        expected_slots=applicable_proposition_evidence_slots(proposition),
        slot_support_by_ref=support_by_ref,
    )
    assert reason == "" and projection is not None
    return bundle, frozen, frozen_slots, {"plans": plans, "projection": projection}


def _multi_selector_frozen_case() -> tuple[
    EvidenceBundle, Any, list[dict[str, Any]], dict[str, Any]
]:
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "chunk-1",
                "source_id": "paper",
                "text": (
                    "This study compares language. "
                    "The authors discussed the two systems."
                ),
            }
        ],
    )
    slots = required_semantic_proposition_slots(_request())
    source = pack_semantic_proposition_evidence(
        _request(),
        QUESTION,
        slots,
        bundle,
        candidate_priority=True,
    )
    frozen = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=QUESTION,
        slots=slots,
        source_packing=source,
        records=prepare_qasper_canonical_records(QUESTION, source.records),
        candidate_transaction_id="candidate-transaction-1",
    )
    frozen_slots = deepcopy(bundle.metadata["qasper_canonical_semantic_pack"]["slots"])
    plans = qasper_canonical_evidence_plans(bundle)
    assert plans is not None
    plan_id = next(iter(plans))
    plan = plans[plan_id]
    support_by_ref, reason = frozen_slot_support_by_ref(
        plan["span_refs"],
        frozen_slots,
    )
    assert reason == ""
    proposition = build_question_proposition(QUESTION)
    projection, reason = frozen_canonical_plan_projection_from_bundle(
        bundle,
        plan_id=plan_id,
        proposition=proposition,
        expected_slots=applicable_proposition_evidence_slots(proposition),
        slot_support_by_ref=support_by_ref,
    )
    assert reason == "" and projection is not None
    return bundle, frozen, frozen_slots, {"plans": plans, "projection": projection}


def _audit_with_fragment_disagreement(
    projection: Any,
    *,
    semantic_fields_valid: bool,
) -> str:
    checks = {}
    for index, premise in enumerate(projection.premises, start=1):
        premise_ref = f"P{index}"
        checks[premise_ref] = {
            "fragment_entailed": False,
            "scope_consistent": semantic_fields_valid,
            "evidence_relation_valid": semantic_fields_valid,
            "proposition_slot_checks": {
                slot: {
                    "binding_valid": semantic_fields_valid,
                    "evidence_ref": f"{premise_ref}:{slot}",
                }
                for slot in premise["binds_proposition_slots"]
            },
        }
    return json.dumps(
        {
            "premise_checks": checks,
            "jointly_entails": semantic_fields_valid,
            "each_premise_required": semantic_fields_valid,
            "contradiction_free": semantic_fields_valid,
            "conclusion_check": {
                "conclusion_entailed": semantic_fields_valid,
                "actor_consistent": semantic_fields_valid,
                "predicate_consistent": semantic_fields_valid,
                "object_consistent": semantic_fields_valid,
                "polarity_consistent": semantic_fields_valid,
                "quantifier_consistent": semantic_fields_valid,
                "scope_consistent": semantic_fields_valid,
            },
        }
    )


def _run_frozen_audit(*, semantic_fields_valid: bool) -> tuple[Any, Any, Any, Any]:
    bundle, frozen, slots, case = _frozen_case()
    plans = case["plans"]
    projection = case["projection"]
    proposal = _StaticLLM(
        json.dumps(
            {
                "candidate_judgment": "supported",
                "canonical_evidence_plan_id": projection.plan_id,
            }
        ),
        "proposal-model",
    )
    auditor = _StaticLLM(
        _audit_with_fragment_disagreement(
            projection,
            semantic_fields_valid=semantic_fields_valid,
        ),
        "auditor-model",
    )
    binding = bundle.metadata["qasper_canonical_semantic_pack"]["proposition_binding"]

    result = run_semantic_proposition_transaction(
        proposal,
        auditor,
        semantic_proposition_verifier_prompt(
            QUESTION,
            slots,
            frozen.records,
            candidate="yes",
        ),
        question=QUESTION,
        packed=deepcopy(frozen.records),
        slots=slots,
        proposal_model="proposal-model",
        audit_model="auditor-model",
        seed=7,
        release_mode=True,
        semantic_pack_digest=frozen.semantic_pack_digest,
        canonical_span_universe_digest=bundle.metadata[
            "qasper_canonical_semantic_pack"
        ]["span_universe_digest"],
        candidate_transaction_id="candidate-transaction-1",
        allowed_proposition_slot_bindings=qasper_canonical_selector_bindings(
            frozen.records
        ),
        allowed_proposition_evidence_plans=plans,
        plan_construction_trace=deepcopy(binding["plan_construction_trace"]),
        source_packing_observation=qasper_source_packing_observation(bundle),
        capture_debug_trace=True,
        transaction_id="candidate-transaction-1",
    )

    return result, proposal, auditor, projection


def test_literal_fragment_disagreement_can_use_the_frozen_plan() -> None:
    result, proposal, auditor, projection = _run_frozen_audit(
        semantic_fields_valid=True
    )

    assert result.status == "parsed"
    assert result.value is not None
    assert result.value["verdict"] == "yes"
    assert result.value["canonical_evidence_plan_id"] == projection.plan_id
    assert result.value["premises"] == list(projection.premises)
    assert result.diagnostics["auditor_internal_inconsistency"] is True
    assert result.diagnostics["local_premise_consistency"]["override_eligible"] is True
    assert result.diagnostics["auditor_override_blocked"] is True
    assert result.diagnostics["audit_authority_source"] == (
        "frozen_canonical_plan_projection"
    )
    assert (
        result.diagnostics["audit_model_observation"]["premise_checks"][0][
            "fragment_entailed"
        ]
        is False
    )
    assert result.debug_trace is not None
    assert (
        result.debug_trace["audit"]["attempts"][0]["parsed_value"]["premise_checks"][0][
            "fragment_entailed"
        ]
        is False
    )
    assert (
        result.value["entailment_audit"]["premise_checks"][0]["fragment_entailed"]
        is True
    )
    assert result.diagnostics["audit_status"] == "verified"
    assert result.diagnostics.get("audit_call_rejection_count", 0) == 0
    assert result.diagnostics.get("rejected_transactions", []) == []
    assert proposal.calls == auditor.calls == 1


def test_frozen_plan_projection_rejects_an_unasserted_selector() -> None:
    _bundle, frozen, frozen_slots, case = _frozen_case()
    plans = case["plans"]
    plan = next(iter(plans.values()))
    records = deepcopy(frozen.records)
    records[0]["selectors"][0]["assertion_scope"] = "conditional"
    support_by_ref, reason = frozen_slot_support_by_ref(
        plan["span_refs"],
        frozen_slots,
    )
    assert reason == ""
    proposition = build_question_proposition(QUESTION)

    projection, reason = frozen_canonical_plan_projection_checked(
        plan,
        records,
        proposition=proposition,
        expected_slots=applicable_proposition_evidence_slots(proposition),
        slot_support_by_ref=support_by_ref,
    )

    assert projection is None
    assert reason == "canonical_plan_projection_selector_invalid"


def test_frozen_plan_projection_uses_plan_level_object_token_union() -> None:
    _bundle, frozen, frozen_slots, case = _multi_selector_frozen_case()
    plan = next(iter(case["plans"].values()))
    assert any(
        not selector["semantic_alignment"]["covered_object_tokens"]
        for record in frozen.records
        for selector in record["selectors"]
    )
    assert set(plan["covered_object_tokens"]) == {
        token
        for record in frozen.records
        for selector in record["selectors"]
        for token in selector["semantic_alignment"]["covered_object_tokens"]
    }

    support_by_ref, reason = frozen_slot_support_by_ref(
        plan["span_refs"],
        frozen_slots,
    )
    assert reason == ""
    projection, reason = frozen_canonical_plan_projection_from_bundle(
        _bundle,
        plan_id=plan["plan_id"],
        proposition=build_question_proposition(QUESTION),
        expected_slots=applicable_proposition_evidence_slots(
            build_question_proposition(QUESTION)
        ),
        slot_support_by_ref=support_by_ref,
    )

    assert reason == ""
    assert projection is not None
    assert projection.covered_object_tokens == tuple(plan["covered_object_tokens"])


def test_semantic_auditor_denial_cannot_be_overridden_by_the_frozen_plan() -> None:
    result, proposal, auditor, _projection = _run_frozen_audit(
        semantic_fields_valid=False
    )

    assert result.status == "audit_rejected"
    assert result.value is not None
    assert result.value["verdict"] == "insufficient_evidence"
    assert result.diagnostics["auditor_internal_inconsistency"] is False
    assert result.diagnostics["local_premise_consistency"]["override_eligible"] is False
    assert result.diagnostics["audit_status"] == "rejected"
    assert result.diagnostics["audit_semantic_rejection"] is True
    assert result.diagnostics["audit_reason"] != ""
    assert result.diagnostics.get("auditor_override_blocked") is not True
    assert result.diagnostics.get("audit_authority_source") is None
    assert result.diagnostics["audit_call_rejection_count"] == 1
    assert len(result.diagnostics["rejected_transactions"]) == 1
    assert proposal.calls == auditor.calls == 1
