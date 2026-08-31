from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
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


def _all_false_audit(projection: Any) -> str:
    checks = {}
    for index, premise in enumerate(projection.premises, start=1):
        premise_ref = f"P{index}"
        checks[premise_ref] = {
            "fragment_entailed": False,
            "scope_consistent": False,
            "evidence_relation_valid": False,
            "proposition_slot_checks": {
                slot: {
                    "binding_valid": False,
                    "evidence_ref": f"{premise_ref}:{slot}",
                }
                for slot in premise["binds_proposition_slots"]
            },
        }
    return json.dumps(
        {
            "premise_checks": checks,
            "jointly_entails": False,
            "each_premise_required": False,
            "contradiction_free": False,
            "conclusion_check": {
                "conclusion_entailed": False,
                "actor_consistent": False,
                "predicate_consistent": False,
                "object_consistent": False,
                "polarity_consistent": False,
                "quantifier_consistent": False,
                "scope_consistent": False,
            },
        }
    )


def test_internally_inconsistent_auditor_cannot_override_the_frozen_plan() -> None:
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
    auditor = _StaticLLM(_all_false_audit(projection), "auditor-model")
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

    assert result.status == "parsed"
    assert result.value is not None
    assert result.value["verdict"] == "yes"
    assert result.value["canonical_evidence_plan_id"] == projection.plan_id
    assert result.value["premises"] == list(projection.premises)
    assert result.diagnostics["auditor_internal_inconsistency"] is True
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
