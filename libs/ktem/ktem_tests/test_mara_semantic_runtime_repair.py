from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.semantic_evidence_set_validation import validated_semantic_header
from ktem.reasoning.mara_semantic_proposition_verifier import (
    build_semantic_proposition_verifier,
)


class _SequenceLLM:
    def __init__(self, model_name: str, responses: list[str]) -> None:
        self.model_name = model_name
        self.responses = [SimpleNamespace(text=value) for value in responses]
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def __call__(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        return self.responses.pop(0)


def _request(question: str) -> DocQARequest:
    return DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        generation_seed=17,
        origin="benchmark",
    )


def _proposal(
    request: DocQARequest,
    selector: str,
    fragment: str,
    *,
    verdict: str = "yes",
) -> str:
    slot_ids = [
        slot.slot_id
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]
    return json.dumps(
        {
            "verdict": verdict,
            "support_mode": "evidence_set",
            "proof_mode": "atomic_semantic",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "span_selector": selector,
                    "proposition_fragment": fragment,
                    "supports_slot_ids": slot_ids,
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
                }
            ],
            "jointly_entails": True,
            "each_premise_required": True,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": True,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        }
    )


def _release_verifier(
    proposals: list[str],
    audits: list[str],
) -> tuple[Any, _SequenceLLM, _SequenceLLM]:
    proposal_llm = _SequenceLLM("semantic-proposer", proposals)
    audit_llm = _SequenceLLM("semantic-auditor", audits)
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=proposal_llm),
            semantic_proposition_release_mode=True,
            semantic_proposition_debug_trace=True,
        ),
        audit_llm=audit_llm,
    )
    assert verifier is not None
    return verifier, proposal_llm, audit_llm


def _item(evidence_id: str, section_id: str, text: str) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": section_id,
        "text": text,
    }


def test_proposition_repair_completes_question_before_conclusion_audit() -> None:
    question = "Does the model have attention?"
    request = _request(question)
    verifier, proposal_llm, audit_llm = _release_verifier(
        [_proposal(request, "E1:S1", "our model uses an attention mechanism")],
        [_atomic_audit()],
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[_item("attention", "methods", "Our model uses an attention mechanism.")],
    )

    result = verifier(request, question, "yes", bundle)

    assert result is not None and result["verdict"] == "yes"
    assert result["question_proposition"]["predicate"] == "have"
    assert result["question_proposition"]["object_surface"] == "attention"
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["question_proposition_status"] == "repaired"
    assert trace["proposition_repair_count"] == 1
    assert trace["recovery_transitions"][0]["to"] == "proposition_repair"
    assert len(proposal_llm.calls) == len(audit_llm.calls) == 1


def test_unrepairable_proposition_stops_before_models_with_bound_insufficient() -> None:
    question = "Is it?"
    request = _request(question)
    verifier, proposal_llm, audit_llm = _release_verifier([], [])
    bundle = EvidenceBundle(
        route="doc_text",
        items=[_item("ambiguous", "methods", "It is described in the paper.")],
    )

    result = verifier(request, question, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "insufficient_evidence"
    header, reason = validated_semantic_header(result, question, release_mode=True)
    assert reason == ""
    assert header is not None and header[0] == "insufficient_evidence"
    assert result["question_proposition_resolution"]["status"] == "incomplete"
    assert result["verifier"]["auditor_relationship"] == "distinct_model"
    assert proposal_llm.calls == audit_llm.calls == []


def test_independent_polarity_check_triggers_real_proof_repair() -> None:
    question = "Does the experiment focus on a specific domain?"
    request = _request(question)
    fragment = "the experiment does not focus on a specific domain"
    verifier, proposal_llm, audit_llm = _release_verifier(
        [
            _proposal(request, "E1:S1", fragment),
            _proposal(request, "E1:S1", fragment, verdict="no"),
        ],
        [_atomic_audit(), _atomic_audit()],
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            _item(
                "domain-scope",
                "experiments",
                "The experiment does not focus on a specific domain.",
            )
        ],
    )

    result = verifier(request, question, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "no"
    assert len(proposal_llm.calls) == len(audit_llm.calls) == 2
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_verified_but_runtime_rejected_count"] == 1
    assert trace["runtime_contract_rejection_count"] == 1
    assert trace["proof_repair_count"] == trace["proof_reaudit_count"] == 1
    assert trace["full_reaudit"] is True
    assert trace["recovery_transitions"][-1]["to"] == "proof_repair"
    rejected = trace["rejected_transactions"][0]
    assert rejected["typed_conclusion"]["polarity"] == "yes"
    assert rejected["polarity_contradiction_check"]["status"] == (
        "contradiction_detected"
    )
    assert (
        result["entailment_audit"]["polarity_contradiction_check"][
            "independent_from_models"
        ]
        is True
    )


def test_runtime_scope_rejection_rebuilds_proof_instead_of_retrieving() -> None:
    question = "Does the model have attention?"
    request = _request(question)
    verifier, proposal_llm, audit_llm = _release_verifier(
        [
            _proposal(request, "E1:S1", "the baseline model uses attention"),
            _proposal(request, "E2:S1", "our model uses attention"),
        ],
        [_atomic_audit(), _atomic_audit()],
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            _item(
                "prior-attention", "related_work", "The baseline model uses attention."
            ),
            _item("current-attention", "methods", "Our model uses attention."),
        ],
    )

    result = verifier(request, question, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "yes"
    assert result["premises"][0]["span_selector"] == "E2:S1"
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["runtime_contract_rejection_count"] == 1
    assert trace["audit_verified_but_runtime_rejected_count"] == 1
    assert trace["runtime_authority_rejection_reason"] == (
        "semantic_premise_scope_rejected"
    )
    transition = next(
        value
        for value in trace["recovery_transitions"]
        if value["from"] == "runtime_authority_contract"
    )
    assert transition["to"] == "proof_repair"
    assert transition["outcome"] == "verified"
    assert trace["semantic_proof_digest_changed"] is True
    assert trace["rejected_transactions"][0]["typed_conclusion"]["polarity"] == ("yes")
    assert len(proposal_llm.calls) == len(audit_llm.calls) == 2


def test_terminal_runtime_rejection_remains_a_bound_insufficient_response() -> None:
    question = "Does the model have attention?"
    request = _request(question)
    rejected = _proposal(request, "E1:S1", "the baseline model uses attention")
    verifier, proposal_llm, audit_llm = _release_verifier(
        [rejected, rejected],
        [_atomic_audit(), _atomic_audit()],
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            _item(
                "prior-attention", "related_work", "The baseline model uses attention."
            )
        ],
    )

    result = verifier(request, question, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "insufficient_evidence"
    header, reason = validated_semantic_header(result, question, release_mode=True)
    assert reason == ""
    assert header is not None and header[0] == "insufficient_evidence"
    assert result["verifier"]["auditor_relationship"] == "distinct_model"
    assert result["verifier"]["semantic_pack_digest"]
    assert result["rejected_transaction"]["typed_conclusion"]["polarity"] == "yes"
    assert len(proposal_llm.calls) == len(audit_llm.calls) == 2
