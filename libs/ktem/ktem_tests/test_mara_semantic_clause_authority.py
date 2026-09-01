from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_authority_derivation import (
    boolean_derivation_contract_status,
    boolean_derivation_id,
    boolean_derivation_identity_payload,
)
from ktem.docqa.boolean_authority_schema import BooleanEvidenceAuthority
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
    proposition_evidence_bindings,
    typed_conclusion,
)
from ktem.docqa.semantic_evidence_set_derivation import semantic_evidence_set_derivation
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
)
from ktem.docqa.verification import verify_decision
from ktem.reasoning.mara_semantic_proposition_verifier import (
    build_semantic_proposition_verifier,
)
from ktem_tests.test_docqa_semantic_evidence_set_authority import (
    _premises as _valid_semantic_premises,
)
from ktem_tests.test_docqa_semantic_evidence_set_authority import (
    _request as _valid_semantic_request,
)
from ktem_tests.test_docqa_semantic_evidence_set_authority import (
    _semantic_verdict as _valid_semantic_verdict,
)

QUESTION = "Did the authors release the code for the evaluated system?"
FALSE_PASS_QUOTE = (
    "The authors released code for a different baseline, but this sentence "
    "does not establish release for the evaluated system."
)


def _premise(quote: str, *, question: str = QUESTION) -> dict[str, Any]:
    proposition = build_question_proposition(question)
    slots = applicable_proposition_evidence_slots(proposition)
    bindings = proposition_evidence_bindings(proposition)
    return {
        "evidence_id": "evidence-1",
        "quote": quote,
        "span_start": 0,
        "span_end": len(quote),
        "proposition_fragment": quote,
        "binds_proposition_slots": list(slots),
        "proposition_slot_bindings": {slot: bindings[slot] for slot in slots},
        "evidence_relation": "proposition_support",
    }


def test_slot_refs_are_exact_subspans_of_one_relation_clause() -> None:
    question = "Did the authors compare the two systems?"
    proposition = build_question_proposition(question)
    quote = "The authors compared the two systems."

    analysis = semantic_relation_clause_analysis(
        _premise(quote, question=question), proposition
    )

    assert analysis["status"] == "affirmative_assertion"
    assert analysis["evidence_relation"] == "proposition_support"
    assert analysis["joint_relation_clause_bound"] is True
    spans = analysis["slot_evidence"]
    assert set(spans) == {"actor", "predicate", "object", "quantifier"}
    assert {value["clause_ref"] for value in spans.values()} == {"C1"}
    assert spans["actor"]["text"] == "The authors"
    assert spans["predicate"]["text"] == "compared"
    assert spans["object"]["text"] == "the two systems"
    assert spans["quantifier"]["text"] == "two"
    assert all(value["text"] != quote for value in spans.values())
    assert all(
        quote[value["span_start"] : value["span_end"]] == value["text"]
        for value in spans.values()
    )


def test_local_relation_analysis_separates_assertion_contradiction_and_mention() -> (
    None
):
    proposition = build_question_proposition(QUESTION)
    affirmative = semantic_relation_clause_analysis(
        _premise("The authors released the code for the evaluated system."),
        proposition,
    )
    contradiction = semantic_relation_clause_analysis(
        _premise("The authors did not release the code for the evaluated system."),
        proposition,
    )
    mention = semantic_relation_clause_analysis(_premise(FALSE_PASS_QUOTE), proposition)

    assert affirmative["status"] == "affirmative_assertion"
    assert affirmative["evidence_relation"] == "proposition_support"
    assert contradiction["status"] == "explicit_contradiction"
    assert contradiction["evidence_relation"] == "explicit_contradiction"
    assert mention["status"] == "mention_only"
    assert mention["evidence_relation"] == "undetermined"
    assert mention["joint_relation_clause_bound"] is False


def _authority(quote: str) -> BooleanEvidenceAuthority:
    proposition = build_question_proposition(QUESTION)
    bindings = proposition_evidence_bindings(proposition)
    slots = applicable_proposition_evidence_slots(proposition)
    return BooleanEvidenceAuthority(
        evidence_id="evidence-1",
        evidence_ref=f"evidence-1#quote:0:{len(quote)}",
        span_id=f"evidence-1#quote:0:{len(quote)}",
        quote=quote,
        span_start=0,
        span_end=len(quote),
        canonical_start=None,
        canonical_end=None,
        actor="current_paper",
        section_scope="document",
        relation="semantic_premise",
        object=quote,
        quantifier="none",
        polarity="yes",
        reason="semantic_evidence_set_premise",
        proposition_slot_bindings=tuple((slot, bindings[slot]) for slot in slots),
        evidence_relation="proposition_support",
    )


def test_auditor_attestation_cannot_self_certify_argument_token_coverage() -> None:
    proposition = build_question_proposition(QUESTION)
    attestation = {
        "typed_conclusion": typed_conclusion(proposition, "yes").as_dict(),
        "independent_semantic_constraint": {"status": "passed"},
    }
    false_authority = _authority(FALSE_PASS_QUOTE)
    valid_authority = _authority(
        "The authors released the code for the evaluated system."
    )

    false_derivation = semantic_evidence_set_derivation(
        QUESTION,
        "yes",
        (false_authority,),
        attestation,
        slot_support={false_authority.evidence_ref: ("support:boolean_proposition",)},
    )
    valid_derivation = semantic_evidence_set_derivation(
        QUESTION,
        "yes",
        (valid_authority,),
        attestation,
        slot_support={valid_authority.evidence_ref: ("support:boolean_proposition",)},
    )

    assert false_derivation.covered_argument_tokens == ()
    assert (
        valid_derivation.covered_argument_tokens
        == valid_derivation.required_argument_tokens
    )


def test_semantic_derivation_cannot_shrink_required_tokens_to_match_coverage() -> None:
    request = _valid_semantic_request()
    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(route="doc_text", items=_valid_semantic_premises()),
        "yes",
        proposition_verifier=_valid_semantic_verdict,
    )
    [derivation] = deepcopy(decision.typed_authority["authority_derivations"])
    retained = derivation["required_argument_tokens"][:-1]
    assert retained
    derivation["required_argument_tokens"] = retained
    derivation["covered_argument_tokens"] = retained
    for contribution in derivation["premise_contributions"]:
        contribution["argument_tokens"] = [
            token for token in contribution["argument_tokens"] if token in retained
        ]
    derivation["derivation_id"] = boolean_derivation_id(
        boolean_derivation_identity_payload(
            rule_id=derivation["rule_id"],
            premise_refs=derivation["premise_refs"],
            conclusion=derivation["conclusion"],
            required_argument_tokens=retained,
            bindings=derivation["bindings"],
            support_mode=derivation["support_mode"],
            verifier_attestation=derivation["verifier_attestation"],
            premise_contributions=derivation["premise_contributions"],
        )
    )

    assert (
        boolean_derivation_contract_status(
            derivation,
            decision.typed_authority["authority_atoms"],
            question=request.prompt,
            canonical_polarity="yes",
        )
        == "semantic_required_argument_tokens_mismatch"
    )


class _SequenceLLM:
    model_name = "Qwen/Qwen3-8B"

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def __call__(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        return SimpleNamespace(
            text=self.responses.pop(0),
            completion_tokens=64,
            additional_kwargs={"finish_reason": "stop"},
        )


def _proposal(request: DocQARequest) -> str:
    required_slots = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]
    return json.dumps(
        {
            "candidate_judgment": "supported",
            "support_mode": "evidence_set",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "span_selector": "E1:S1",
                    "proposition_fragment": FALSE_PASS_QUOTE,
                    "supports_slot_ids": required_slots,
                    "binds_proposition_slots": ["actor", "predicate", "object"],
                }
            ],
            "not_applicable_proposition_slots": ["quantifier"],
        }
    )


def _all_true_audit() -> str:
    return json.dumps(
        {
            "premise_checks": {
                "P1": {
                    "fragment_entailed": True,
                    "scope_consistent": True,
                    "evidence_relation_valid": True,
                    "proposition_slot_checks": {
                        slot: {
                            "binding_valid": True,
                            "evidence_ref": f"P1:{slot}",
                        }
                        for slot in ("actor", "predicate", "object")
                    },
                }
            },
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


def test_same_model_all_true_audit_cannot_promote_a_meta_mention() -> None:
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    request = DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=plan,
        generation_seed=17,
    )
    proposer = _SequenceLLM([_proposal(request)])
    auditor = _SequenceLLM([_all_true_audit()])
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=proposer)),
        audit_llm=auditor,
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "false-pass",
                "source_id": "paper",
                "section_id": "results",
                "text": FALSE_PASS_QUOTE,
            }
        ],
    )

    assert verifier is not None
    result = verifier(request, QUESTION, "yes", bundle)

    assert result is not None
    assert result["verdict"] == "insufficient_evidence"
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["auditor_relationship"] == "distinct_instance_same_model"
    assert trace["audit_model_call_count"] == 1
    assert trace["audit_parser_accepted"] is True
    assert trace["audit_semantic_rejection"] is True
    assert trace["audit_reason"] == "local_semantic_relation_mention_only"
    constraint = trace["independent_semantic_constraint"]
    assert constraint["independent_from_models"] is True
    assert constraint["correlated_model_guard_applied"] is True

    audit_prompt = auditor.calls[0][0][1].content
    prompt_payload = json.loads(
        audit_prompt.split("AUDIT THIS PROOF PROPOSAL:\n", maxsplit=1)[1]
    )
    slot_refs = prompt_payload["premises"][0]["proposition_slot_evidence_refs"]
    assert set(slot_refs) == {"actor", "predicate", "object"}
    assert all(value["text"] != FALSE_PASS_QUOTE for value in slot_refs.values())
    assert all(
        FALSE_PASS_QUOTE[value["span_start"] : value["span_end"]] == value["text"]
        for value in slot_refs.values()
    )


def test_same_model_false_pass_cannot_reach_boolean_authority() -> None:
    plan = build_query_plan(
        QUESTION,
        answer_type="boolean",
        verification_domain="qasper",
    )
    request = DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=plan,
        generation_seed=17,
    )
    proposer = _SequenceLLM([_proposal(request)])
    auditor = _SequenceLLM([_all_true_audit()])
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=proposer)),
        audit_llm=auditor,
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "false-pass",
                "source_id": "paper",
                "section_id": "results",
                "text": FALSE_PASS_QUOTE,
            }
        ],
    )

    assert verifier is not None
    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "yes",
        proposition_verifier=verifier,
    )

    assert decision.status != "supported"
    assert decision.boolean_authority_status != "verified_support"
    assert decision.typed_authority["state"] == "missing"
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_parser_accepted"] is True
    assert trace["audit_reason"] == "local_semantic_relation_mention_only"
