from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.reasoning.mara_semantic_proof_repair import requires_proof_repair
from ktem.reasoning.mara_semantic_proposition_stages import ParsedSemanticStage
from ktem.reasoning.mara_semantic_proposition_verifier import (
    build_semantic_proposition_verifier,
)

from .test_mara_semantic_proposition_audit import (
    QUESTION,
    _atomic_audit,
    _audit,
    _items,
    _proposal,
    _rebuilt_atomic_proposal,
    _request,
    _response,
    _SequenceLLM,
    _verifier,
)

INSPECTION_QUESTION = (
    "Do they inspect their model to see whether visual contexts affect "
    "entity predictions?"
)


def _literal_composite_proposal(*, repaired: bool = False) -> str:
    payload = json.loads(_proposal())
    payload["premises"][0][
        "proposition_fragment"
    ] = "We compared cross-lingual and single-language evaluation"
    payload["premises"][1]["proposition_fragment"] = (
        "The comparison covered cross-lingual and single-language evaluation"
        if repaired
        else "cross-lingual and single-language evaluation"
    )
    return json.dumps(payload)


def _audit_with_all_literal_premises_rejected() -> str:
    payload = json.loads(_audit())
    for check in payload["premise_checks"].values():
        check["fragment_entailed"] = False
    payload["jointly_entails"] = False
    payload["each_premise_required"] = False
    payload["conclusion_check"]["conclusion_entailed"] = False
    return json.dumps(payload)


def _audit_with_joint_entailment_rejected() -> str:
    payload = json.loads(_audit())
    payload["jointly_entails"] = False
    payload["each_premise_required"] = False
    payload["conclusion_check"]["conclusion_entailed"] = False
    return json.dumps(payload)


def _inspection_request() -> DocQARequest:
    return DocQARequest(
        prompt=INSPECTION_QUESTION,
        retrieval_query=INSPECTION_QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=build_query_plan(
            INSPECTION_QUESTION,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        generation_seed=17,
    )


def _inspection_proposal() -> str:
    return json.dumps(
        {
            "verdict": "yes",
            "evidence_relation": "proposition_support",
            "support_mode": "evidence_set",
            "proof_mode": "composite_conjunction",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "span_selector": "E1:S1",
                    "proposition_fragment": (
                        "We visualize the modality attention module at each "
                        "decoding step to analyze the model"
                    ),
                    "supports_slot_ids": ["support:boolean_proposition"],
                    "binds_proposition_slots": ["actor", "predicate", "object"],
                },
                {
                    "span_selector": "E2:S1",
                    "proposition_fragment": (
                        "We confirm that attention amplifies relevant visual "
                        "contexts when predicting named entities"
                    ),
                    "supports_slot_ids": ["support:boolean_proposition"],
                    "binds_proposition_slots": ["object"],
                },
            ],
        }
    )


def _inspection_items() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "inspection-procedure",
            "source_id": "paper",
            "section_id": "analysis",
            "text": (
                "We visualize the modality attention module at each decoding "
                "step to analyze the model."
            ),
        },
        {
            "evidence_id": "inspection-observation",
            "source_id": "paper",
            "section_id": "analysis",
            "text": (
                "We confirm that attention amplifies relevant visual contexts "
                "when predicting named entities."
            ),
        },
    ]


def test_text_semantic_conjunction_can_prove_an_inspection_question() -> None:
    request = _inspection_request()
    proposal_llm = _SequenceLLM([_response(_inspection_proposal())])
    audit_llm = _SequenceLLM(
        [
            _response(
                _audit(
                    premise_specs=[
                        (
                            ["actor", "predicate", "object"],
                            {"actor": "We", "predicate": "visualize"},
                        ),
                        (["object"], {"object": "visual contexts"}),
                    ]
                )
            )
        ]
    )
    audit_llm.model_name = "dedicated-audit-model"
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=proposal_llm),
            semantic_proposition_release_mode=True,
        ),
        audit_llm=audit_llm,
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_inspection_items())

    result = verifier(request, INSPECTION_QUESTION, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "yes"
    assert result["proof_mode"] == "composite_conjunction"
    assert result["entailment_audit"]["auditor"]["relationship"] == ("distinct_model")
    assert [slot.slot_id for slot in request.query_plan.evidence_slots] == [
        "support:boolean_proposition"
    ]


def test_semantic_denial_with_literal_false_stops_without_a_second_answer() -> None:
    llm = _SequenceLLM(
        [
            _response(_literal_composite_proposal()),
            _response(_audit_with_all_literal_premises_rejected()),
            _response(_literal_composite_proposal(repaired=True)),
            _response(_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "insufficient_evidence"
    assert result["evidence_relation"] == "undetermined"
    assert result["proof_mode"] == "none"
    assert result["premises"] == []
    assert result["candidate_verification_audit"]["status"] == "failed"
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["auditor_internal_inconsistency_count"] == 0
    consistency = trace["local_premise_consistency"]
    assert consistency["status"] == "auditor_semantic_rejection"
    assert consistency["literal_disagreement_premise_refs"] == ["P1", "P2"]
    assert consistency["inconsistent_premise_refs"] == []
    assert consistency["override_eligible"] is False
    assert consistency["semantic_denial_fields"] == [
        "jointly_entails",
        "each_premise_required",
        "conclusion_check.conclusion_entailed",
    ]
    assert trace.get("proof_repair_count", 0) == 0
    assert trace.get("proof_reaudit_count", 0) == 0
    transition = trace["recovery_transitions"][-1]
    assert transition["from"] == "semantic_audit"
    assert transition["to"] == "stop_without_reverify"
    assert transition["reason"] == "premise_fragment_not_entailed"
    assert transition["outcome"] == "recovery_no_progress"
    assert transition["proposition_binding_digest_changed"] is False
    assert len(llm.calls) == 2
    [rejected] = trace["rejected_transactions"]
    assert rejected["local_premise_consistency"]["status"] == (
        "auditor_semantic_rejection"
    )


def test_joint_entailment_rejection_stops_without_binding_change() -> None:
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response(_audit_with_joint_entailment_rejected()),
            _response(_rebuilt_atomic_proposal()),
            _response(_atomic_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "insufficient_evidence"
    assert result["candidate_verification_audit"]["status"] == "failed"
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace.get("proof_repair_count", 0) == 0
    assert trace.get("proof_reaudit_count", 0) == 0
    transition = trace["recovery_transitions"][-1]
    assert transition["to"] == "stop_without_reverify"
    assert transition["reason"] == "joint_entailment_rejected"
    assert transition["outcome"] == "recovery_no_progress"
    assert transition["proposition_binding_digest_changed"] is False
    assert len(llm.calls) == 2


def test_all_semantic_audit_rejection_classes_are_proof_repairable() -> None:
    stage = ParsedSemanticStage(
        response=None,
        value={"premise_checks": []},
        failure_reason="",
        initial_failure_reason="",
        retry_count=0,
        provider_failure_reason="",
        call_count=0,
        attempts=(),
    )
    for reason in (
        "premise_fragment_not_entailed",
        "joint_entailment_rejected",
        "typed_conclusion_not_entailed",
        "typed_conclusion_scope_rejected",
        "typed_conclusion_quantifier_rejected",
        "typed_conclusion_polarity_rejected",
    ):
        assert requires_proof_repair(stage, reason=reason) is True
    assert requires_proof_repair(stage, reason="provider_call_failed") is False
