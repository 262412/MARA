from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.question_proposition import build_question_proposition, typed_conclusion
from ktem.reasoning.mara_semantic_proposition_verifier import (
    build_semantic_proposition_verifier,
)

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


class _SequenceLLM:
    model_name = "semantic-test-model"

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def __call__(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        return self.responses.pop(0)


def _response(
    text: str,
    *,
    completion_tokens: int = 100,
    finish_reason: str = "stop",
) -> Any:
    return SimpleNamespace(
        text=text,
        completion_tokens=completion_tokens,
        additional_kwargs={"finish_reason": finish_reason},
    )


def _request() -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="general",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=build_query_plan(
            QUESTION,
            answer_type="boolean",
            verification_domain="general",
        ),
        generation_seed=17,
    )


def _items() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": "cross-lingual",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "We evaluated transfer in the cross-lingual setting.",
        },
        {
            "evidence_id": "single-language",
            "source_id": "paper",
            "section_id": "experiments",
            "text": (
                "The same experiment included single-language baselines for comparison."
            ),
        },
    ]


def _proposal() -> str:
    slot_ids = [
        slot.slot_id
        for slot in _request().query_plan.evidence_slots
        if slot.required_for_verification
    ]
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
                    "proposition_fragment": "cross-lingual evaluation was performed",
                    "supports_slot_ids": slot_ids[:2],
                    "binds_proposition_slots": ["actor", "predicate"],
                },
                {
                    "span_selector": "E2:S1",
                    "proposition_fragment": (
                        "single-language baselines were included for comparison"
                    ),
                    "supports_slot_ids": [slot_ids[-1]],
                    "binds_proposition_slots": ["object"],
                },
            ],
        }
    )


def _repairable_proposal() -> str:
    payload = json.loads(_proposal())
    slot_ids = [
        slot.slot_id
        for slot in _request().query_plan.evidence_slots
        if slot.required_for_verification
    ]
    payload["premises"][0]["supports_slot_ids"] = slot_ids
    payload["premises"][0]["binds_proposition_slots"] = [
        "actor",
        "predicate",
        "object",
    ]
    return json.dumps(payload)


def _rebuilt_atomic_proposal() -> str:
    payload = json.loads(_proposal())
    slot_ids = [
        slot.slot_id
        for slot in _request().query_plan.evidence_slots
        if slot.required_for_verification
    ]
    payload["proof_mode"] = "atomic_semantic"
    payload["premises"] = [
        {
            "span_selector": "E1:S1",
            "proposition_fragment": (
                "We evaluated transfer in the cross-lingual setting."
            ),
            "supports_slot_ids": slot_ids,
            "binds_proposition_slots": [
                "actor",
                "predicate",
                "object",
            ],
        }
    ]
    return json.dumps(payload)


def _audit(
    *,
    second_fragment_entailed: bool = True,
    premise_specs: list[tuple[list[str], dict[str, str]]] | None = None,
) -> str:
    premise_specs = premise_specs or [
        (["actor", "predicate"], {"actor": "We", "predicate": "evaluated"}),
        (["object"], {"object": "single-language baselines"}),
    ]
    validity = [True, second_fragment_entailed]
    return json.dumps(
        {
            "premise_checks": [
                {
                    "premise_ref": f"P{index}",
                    "fragment_entailed": validity[index - 1],
                    "scope_consistent": True,
                    "proposition_bindings_valid": validity[index - 1],
                    "evidence_relation_valid": validity[index - 1],
                    "declared_proposition_slots": slots,
                    "proposition_slot_checks": [
                        {
                            "slot": slot,
                            "binding_valid": validity[index - 1],
                            "evidence_text": evidence[slot],
                        }
                        for slot in slots
                    ],
                }
                for index, (slots, evidence) in enumerate(premise_specs, start=1)
            ],
            "jointly_entails": second_fragment_entailed,
            "each_premise_required": second_fragment_entailed,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": second_fragment_entailed,
                "actor_consistent": second_fragment_entailed,
                "predicate_consistent": second_fragment_entailed,
                "object_consistent": second_fragment_entailed,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        }
    )


def _audit_with_false_premise_but_joint_entailment(
    *,
    repairable: bool = False,
) -> str:
    premise_specs = None
    if repairable:
        premise_specs = [
            (
                ["actor", "predicate", "object"],
                {
                    "actor": "We",
                    "predicate": "evaluated",
                    "object": "cross-lingual setting",
                },
            ),
            (["object"], {"object": "single-language baselines"}),
        ]
    payload = json.loads(_audit(premise_specs=premise_specs))
    payload["premise_checks"][1]["fragment_entailed"] = False
    payload["jointly_entails"] = True
    payload["each_premise_required"] = True
    payload["conclusion_check"]["conclusion_entailed"] = True
    return json.dumps(payload)


def _insufficient_proposal() -> str:
    return json.dumps(
        {
            "verdict": "insufficient_evidence",
            "evidence_relation": "undetermined",
            "support_mode": "evidence_set",
            "proof_mode": "none",
            "jointly_complete": False,
            "each_premise_required": False,
            "premises": [],
            "unknown_assessment": {
                "reviewed_span_selectors": ["E1:S1", "E2:S1"],
                "unresolved_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                ],
                "support_gap": "No reviewed evidence set establishes every proposition slot.",
                "contradiction_gap": "No reviewed evidence explicitly contradicts the proposition.",
            },
        }
    )


def _atomic_request() -> DocQARequest:
    question = "Did the authors evaluate transfer across languages?"
    return DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="general",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="general",
        ),
        generation_seed=17,
    )


def _atomic_proposal(*, selector: str = "E1:S1") -> str:
    return json.dumps(
        {
            "verdict": "yes",
            "evidence_relation": "proposition_support",
            "support_mode": "evidence_set",
            "proof_mode": "atomic_semantic",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "span_selector": selector,
                    "proposition_fragment": (
                        "We evaluated transfer in the cross-lingual setting."
                    ),
                    "supports_slot_ids": ["support:boolean_proposition"],
                    "binds_proposition_slots": [
                        "actor",
                        "predicate",
                        "object",
                    ],
                }
            ],
        }
    )


def _atomic_audit() -> str:
    return json.dumps(
        {
            "premise_checks": [
                {
                    "premise_ref": "P1",
                    "fragment_entailed": True,
                    "scope_consistent": True,
                    "proposition_bindings_valid": True,
                    "evidence_relation_valid": True,
                    "declared_proposition_slots": [
                        "actor",
                        "predicate",
                        "object",
                    ],
                    "proposition_slot_checks": [
                        {
                            "slot": "actor",
                            "binding_valid": True,
                            "evidence_text": "We",
                        },
                        {
                            "slot": "predicate",
                            "binding_valid": True,
                            "evidence_text": "evaluated",
                        },
                        {
                            "slot": "object",
                            "binding_valid": True,
                            "evidence_text": "transfer",
                        },
                    ],
                }
            ],
            "jointly_entails": True,
            "each_premise_required": True,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": True,
                "actor_consistent": True,
                "predicate_consistent": True,
                "object_consistent": True,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        }
    )


def _unknown_audit(*, support_gap_valid: bool = True) -> str:
    return json.dumps(
        {
            "audit_scope": "original_candidate_and_verifier_unknown_only",
            "audited_candidate": "yes",
            "audited_verdict": "insufficient_evidence",
            "audited_judgment": "unknown",
            "typed_conclusion_present": True,
            "reviewed_evidence_present": True,
            "support_gap_valid": support_gap_valid,
            "contradiction_gap_valid": True,
            "relationship_consistent": True,
            "replacement_candidate_allowed": False,
            "replacement_candidate": "",
        }
    )


def _verifier(llm: _SequenceLLM, *, debug: bool = False) -> Any:
    return build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=llm),
            semantic_proposition_debug_trace=debug,
        )
    )


def test_runtime_requires_an_independent_entailment_audit_before_commit() -> None:
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None
    assert result["contract_id"] == "semantic_proposition_verdict.v4"
    assert result["verdict"] == "yes"
    audit = result["entailment_audit"]
    assert audit["contract_id"] == "semantic_entailment_audit.v3"
    assert audit["auditor"]["contract_id"] == "grounded_semantic_auditor.v3"
    assert audit["status"] == "verified"
    assert audit["premise_count"] == 2
    assert {
        slot
        for premise in result["premises"]
        for slot in premise["proposition_slot_bindings"]
    } == {"actor", "predicate", "object"}
    assert result["not_applicable_proposition_slots"] == ["quantifier"]
    assert {premise["evidence_relation"] for premise in result["premises"]} == {
        "proposition_support"
    }
    assert all(
        check["proposition_bindings_valid"] and check["evidence_relation_valid"]
        for check in audit["premise_checks"]
    )
    assert len(llm.calls) == 2
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_status"] == "verified"
    assert trace["audit_model_call_count"] == 1


def test_runtime_publishes_typed_question_proposition_and_conclusion_audit() -> None:
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None
    proposition = build_question_proposition(QUESTION)
    conclusion = typed_conclusion(proposition, "yes")
    assert result["question_proposition"]["proposition_id"] == (
        proposition.proposition_id
    )
    assert result["question_proposition"]["surface"] == proposition.surface
    assert result["typed_conclusion"]["conclusion_id"] == conclusion.conclusion_id
    assert result["typed_conclusion"]["proposition_id"] == (proposition.proposition_id)
    conclusion_audit = result["entailment_audit"]["conclusion_audit"]
    assert conclusion_audit["conclusion_id"] == conclusion.conclusion_id
    assert conclusion_audit["auditor_relationship"] == "same_instance"


def test_unknown_verdict_requires_candidate_typed_conclusion_and_gap_audit() -> None:
    llm = _SequenceLLM(
        [_response(_insufficient_proposal()), _response(_unknown_audit())]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None
    assert result["verdict"] == "insufficient_evidence"
    assert result["audited_typed_conclusion"]["polarity"] == "yes"
    assert result["unknown_assessment"]["reviewed_evidence"]
    audit = result["candidate_verification_audit"]
    assert audit["status"] == "passed"
    assert audit["mode"] == "candidate_bound_unknown_audit"
    assert audit["replacement_candidate_allowed"] is False
    assert len(llm.calls) == 2


def test_unknown_verdict_rejects_empty_generic_entailment_audit() -> None:
    empty_generic_audit = json.dumps(
        {
            "premise_checks": [],
            "jointly_entails": True,
            "each_premise_required": True,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": True,
                "actor_consistent": True,
                "predicate_consistent": True,
                "object_consistent": True,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        }
    )
    llm = _SequenceLLM(
        [
            _response(_insufficient_proposal()),
            _response(empty_generic_audit),
            _response(empty_generic_audit),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None

    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["candidate_verification_audit"]["status"] == "failed"
    assert trace["audit_reason"] == "invalid_candidate_bound_unknown_audit_json"


def test_release_mode_same_instance_auditor_fails_closed_before_model_call() -> None:
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    bundle = EvidenceBundle(route="doc_text", items=_items())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=llm),
            semantic_proposition_release_mode=True,
        )
    )

    assert verifier is not None
    assert verifier(_request(), QUESTION, "unanswerable", bundle) is None
    assert llm.calls == []
    assert bundle.metadata["semantic_proposition_verifier"]["reason"] == (
        "release_conclusion_auditor_not_independent"
    )


def test_runtime_can_route_the_audit_to_a_dedicated_model() -> None:
    proposal_llm = _SequenceLLM([_response(_proposal())])
    audit_llm = _SequenceLLM([_response(_audit())])
    audit_llm.model_name = "dedicated-audit-model"
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=proposal_llm)),
        audit_llm=audit_llm,
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None
    assert len(proposal_llm.calls) == 1
    assert len(audit_llm.calls) == 1
    assert result["entailment_audit"]["auditor"]["model"] == ("dedicated-audit-model")
    assert bundle.metadata["semantic_proposition_verifier"]["audit_model"] == (
        "dedicated-audit-model"
    )


def test_runtime_rejects_a_self_attested_extension_without_reanswering() -> None:
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response(_audit(second_fragment_entailed=False)),
            _response(_insufficient_proposal()),
            _response(_unknown_audit()),
        ]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None
    assert result["verdict"] == "insufficient_evidence"
    assert result["premises"] == []
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["status"] == "audit_rejected"
    assert trace["audit_status"] == "rejected"
    assert trace["audit_reason"] == "premise_fragment_not_entailed"
    assert trace.get("proof_repair_count", 0) == 0
    transition = trace["recovery_transitions"][-1]
    assert transition["to"] == "stop_without_reverify"
    assert transition["outcome"] == "recovery_no_progress"
    assert transition["proposition_binding_digest_changed"] is False
    assert len(llm.calls) == 2


def test_false_premise_with_joint_entailment_true_triggers_repair_and_full_review() -> (
    None
):
    llm = _SequenceLLM(
        [
            _response(_repairable_proposal()),
            _response(_audit_with_false_premise_but_joint_entailment(repairable=True)),
            _response(_atomic_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None
    assert result["verdict"] == "yes"
    assert len(llm.calls) == 3
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["proof_repair_count"] == 1
    assert trace["audit_reason"] == "premise_false_jointly_entails_true"
    assert trace["full_reaudit"] is True
    repair_debug = trace["debug_trace"]["events"][0]["transaction"]["proof_repair"]
    assert repair_debug["kind"] == "pruned"
    transition = repair_debug["transition"]
    assert transition["evidence_digest_changed"] is False
    assert transition["slot_state_digest_changed"] is False
    assert transition["proposition_binding_digest_changed"] is True
    assert (
        transition["proposition_binding_digest_before"]
        != transition["proposition_binding_digest_after"]
    )
    assert repair_debug["initial_audit"]["attempts"][0]["raw_response"] == (
        _audit_with_false_premise_but_joint_entailment(repairable=True)
    )
    assert repair_debug["proof_reaudit"]["attempts"][0]["raw_response"] == (
        _atomic_audit()
    )
