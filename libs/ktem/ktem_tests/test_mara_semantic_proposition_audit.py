from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.question_proposition import build_question_proposition, typed_conclusion
from ktem.reasoning.mara_semantic_proposition_verifier import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
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
            "support_mode": "evidence_set",
            "proof_mode": "composite_conjunction",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "span_selector": "E1:S1",
                    "proposition_fragment": "cross-lingual evaluation was performed",
                    "supports_slot_ids": slot_ids[:2],
                },
                {
                    "span_selector": "E2:S1",
                    "proposition_fragment": (
                        "single-language baselines were included for comparison"
                    ),
                    "supports_slot_ids": [slot_ids[-1]],
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
                "the complete comparison proposition is established"
            ),
            "supports_slot_ids": slot_ids,
        }
    ]
    return json.dumps(payload)


def _audit(*, second_fragment_entailed: bool = True) -> str:
    return json.dumps(
        {
            "premise_checks": [
                {
                    "premise_ref": "P1",
                    "fragment_entailed": True,
                    "scope_consistent": True,
                },
                {
                    "premise_ref": "P2",
                    "fragment_entailed": second_fragment_entailed,
                    "scope_consistent": True,
                },
            ],
            "jointly_entails": second_fragment_entailed,
            "each_premise_required": second_fragment_entailed,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": second_fragment_entailed,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        }
    )


def _audit_with_false_premise_but_joint_entailment() -> str:
    payload = json.loads(_audit())
    payload["premise_checks"][1]["fragment_entailed"] = False
    payload["jointly_entails"] = True
    payload["each_premise_required"] = True
    payload["conclusion_check"]["conclusion_entailed"] = True
    return json.dumps(payload)


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
            "support_mode": "evidence_set",
            "proof_mode": "atomic_semantic",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "span_selector": selector,
                    "proposition_fragment": ("cross-lingual transfer was evaluated"),
                    "supports_slot_ids": ["support:boolean_proposition"],
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
    assert result["contract_id"] == "semantic_proposition_verdict.v3"
    assert result["verdict"] == "yes"
    audit = result["entailment_audit"]
    assert audit["contract_id"] == "semantic_entailment_audit.v2"
    assert audit["auditor"]["contract_id"] == "grounded_semantic_auditor.v2"
    assert audit["status"] == "verified"
    assert audit["premise_count"] == 2
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


def test_runtime_downgrades_a_self_attested_but_unaudited_extension() -> None:
    llm = _SequenceLLM(
        [_response(_proposal()), _response(_audit(second_fragment_entailed=False))]
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


def test_false_premise_with_joint_entailment_true_triggers_repair_and_full_review() -> (
    None
):
    llm = _SequenceLLM(
        [
            _response(_repairable_proposal()),
            _response(_audit_with_false_premise_but_joint_entailment()),
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
    assert repair_debug["initial_audit"]["attempts"][0]["raw_response"] == (
        _audit_with_false_premise_but_joint_entailment()
    )
    assert repair_debug["proof_reaudit"]["attempts"][0]["raw_response"] == (
        _atomic_audit()
    )


def test_unprunable_contradictory_audit_rebuilds_proof_then_fully_reaudits() -> None:
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response(_audit_with_false_premise_but_joint_entailment()),
            _response(_rebuilt_atomic_proposal()),
            _response(_atomic_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None
    assert result["verdict"] == "yes"
    assert result["proof_mode"] == "atomic_semantic"
    assert len(llm.calls) == 4
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["proof_repair_count"] == 1
    assert trace["proof_rebuild_count"] == 1
    assert trace["proof_reaudit_count"] == 1
    assert trace["full_reaudit"] is True
    assert trace["recovery_transitions"][-1]["outcome"] == "rebuilt"
    repair_debug = trace["debug_trace"]["events"][0]["transaction"]["proof_repair"]
    assert repair_debug["kind"] == "rebuilt"
    assert repair_debug["initial_audit"]["attempts"][0]["raw_response"] == (
        _audit_with_false_premise_but_joint_entailment()
    )
    assert repair_debug["proof_reaudit"]["attempts"][0]["raw_response"] == (
        _atomic_audit()
    )


def test_runtime_retries_one_malformed_proposal_then_audits_it() -> None:
    llm = _SequenceLLM(
        [
            _response("{", completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS),
            _response(_proposal()),
            _response(_audit()),
        ]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None and result["verdict"] == "yes"
    assert len(llm.calls) == 3
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["proposal_retry_count"] == 1
    assert trace["initial_parse_failure_reason"] == "json_decode_error"


def test_runtime_classifies_exhausted_output_without_recording_response_text() -> None:
    llm = _SequenceLLM(
        [
            _response(
                "{",
                completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                finish_reason="length",
            ),
            _response(
                "{",
                completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                finish_reason="length",
            ),
        ]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None

    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["reason"] == "provider_output_truncated"
    assert trace["parse_failure_reason"] == "json_decode_error"
    assert trace["response_finish_reason"] == "length"
    assert trace["response_completion_tokens"] == (
        SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS
    )
    assert trace["response_chars"] == 1
    assert "response_text" not in trace
    assert "debug_trace" not in trace


def test_debug_trace_records_every_proposal_and_audit_output_without_changing_result() -> (
    None
):
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "yes"
    debug = bundle.metadata["semantic_proposition_verifier"]["debug_trace"]
    assert debug["contract_id"] == "semantic_proposition_debug_trace.v2"
    [event] = debug["events"]
    assert event["event"] == "model_transaction"
    assert event["auditor_relationship"] == "same_instance"
    assert event["transaction"]["proposal"]["attempts"][0]["raw_response"] == (
        _proposal()
    )
    assert (
        event["transaction"]["proposal"]["attempts"][0]["parsed_value"]["verdict"]
        == "yes"
    )
    assert event["transaction"]["audit"]["attempts"][0]["raw_response"] == (_audit())
    assert (
        event["transaction"]["audit"]["attempts"][0]["parsed_value"]["jointly_entails"]
        is True
    )


def test_debug_trace_preserves_cache_reuse_after_a_rejected_audit() -> None:
    llm = _SequenceLLM(
        [_response(_proposal()), _response(_audit(second_fragment_entailed=False))]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    first = verifier(_request(), QUESTION, "yes", bundle)
    second = verifier(_request(), QUESTION, "yes", bundle)

    assert first == second
    debug = bundle.metadata["semantic_proposition_verifier"]["debug_trace"]
    assert [event["event"] for event in debug["events"]] == [
        "model_transaction",
        "cache_reuse",
    ]
    assert debug["events"][0]["outcome"]["audit_status"] == "rejected"
    assert debug["events"][1]["source_event_index"] == 1
    assert debug["events"][1]["cached_outcome"]["audit_status"] == "rejected"


def test_debug_trace_can_be_enabled_by_the_slurm_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE", "1")
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    verifier(_request(), QUESTION, "unanswerable", bundle)

    assert (
        bundle.metadata["semantic_proposition_verifier"]["debug_trace"]["contract_id"]
        == "semantic_proposition_debug_trace.v2"
    )


def test_canonical_sentence_span_selector_preserves_exact_quote_and_offsets() -> None:
    source_text = (
        "Lead-in context. Transfer was evaluated across two languages. "
        "Trailing context."
    )
    target_quote = "Transfer was evaluated across two languages."
    local_start = source_text.index(target_quote)
    canonical_start = 240
    item = {
        "evidence_id": "canonical-span-source",
        "source_id": "paper",
        "section_id": "experiments",
        "canonical_start": canonical_start,
        "text": source_text,
    }
    llm = _SequenceLLM(
        [_response(_atomic_proposal(selector="E1:S2")), _response(_atomic_audit())]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=[item])

    result = verifier(
        _atomic_request(),
        "Did the authors evaluate transfer across languages?",
        "yes",
        bundle,
    )

    assert result is not None
    [premise] = result["premises"]
    assert premise["quote"] == target_quote
    assert premise["span_start"] == local_start
    assert premise["span_end"] == local_start + len(target_quote)
    assert premise["canonical_start"] == canonical_start + local_start
    assert premise["canonical_end"] == canonical_start + local_start + len(target_quote)
