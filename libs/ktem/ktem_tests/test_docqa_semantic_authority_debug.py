from __future__ import annotations

from typing import Any

from ktem.docqa.boolean_authority_schema import SEMANTIC_PROPOSITION_VERDICT_CONTRACT
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.verification import verify_decision
from ktem_tests.semantic_entailment_test_helpers import audited_verdict
from ktem_tests.test_docqa_semantic_evidence_set_authority import _item, _request


def test_debug_trace_preserves_audit_verified_then_authority_rejected_stages() -> None:
    question = "Does Atlas contain private datasets for its 50 tasks?"
    items = [
        _item("atlas-public", "Atlas contains public datasets."),
        _item("atlas-tasks", "Atlas focuses on 50 tasks."),
    ]
    request = _request(question)
    [slot_id] = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]

    def verifier(*_args: Any) -> dict[str, Any]:
        bundle = _args[-1]
        bundle.metadata["semantic_proposition_verifier"] = {
            "contract_id": "semantic_proposition_verifier_runtime.v1",
            "status": "parsed",
            "audit_status": "verified",
            "debug_trace": {
                "contract_id": "semantic_proposition_debug_trace.v1",
                "events": [{"event_index": 1, "event": "model_transaction"}],
            },
        }
        return audited_verdict(
            {
                "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
                "verdict": "no",
                "support_mode": "evidence_set",
                "jointly_complete": True,
                "each_premise_required": True,
                "premises": [
                    {
                        "evidence_id": identity_of(item).key,
                        "quote": item["text"],
                        "proposition_fragment": f"positive premise {index}",
                        "supports_slot_ids": [slot_id],
                    }
                    for index, item in enumerate(items, start=1)
                ],
                "verifier": {
                    "contract_id": "grounded_semantic_verifier.v1",
                    "model": "test-double",
                    "seed": 7,
                },
            },
            question,
        )

    bundle = EvidenceBundle(route="doc_text", items=items)
    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "no",
        proposition_verifier=verifier,
    )

    assert decision.status != "supported"
    authority = bundle.metadata["semantic_proposition_authority"]
    assert authority["status"] == "rejected"
    assert authority["reason"] == "semantic_negative_authority_not_explicit"
    assert authority["debug_trace"]["attempts"][0]["stages"] == [
        {"stage": "verifier", "status": "parsed", "reason": ""},
        {"stage": "header", "status": "accepted", "reason": ""},
        {
            "stage": "premises",
            "status": "rejected",
            "reason": "semantic_negative_authority_not_explicit",
        },
    ]
