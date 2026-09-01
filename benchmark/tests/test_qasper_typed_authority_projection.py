from __future__ import annotations

from copy import deepcopy

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_authority_schema import SEMANTIC_PROPOSITION_VERDICT_CONTRACT
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_planning import build_query_plan

from benchmark.answer_finalizer import (
    attach_structured_citations_from_evidence,
    finalize_prediction_answer,
)
from benchmark.citation_claim_selection import minimum_verified_claim_support_items
from benchmark.qasper_contract_invariants import qasper_contract_metric_values
from benchmark.qasper_runtime_authority import (
    runtime_boolean_authority,
    runtime_typed_proposition_authority,
)
from benchmark.task_answer_contracts import apply_task_answer_contract
from benchmark.tests.qasper_semantic_test_fixtures import semantic_repair_diagnostics
from benchmark.tests.qasper_semantic_test_fixtures import (
    semantic_verdict as _semantic_verdict,
)


def _prediction(*, exact: bool) -> dict:
    question = "How many participants did the authors recruit for the study?"
    answer = "The authors recruited 42 participants."
    evidence = {
        "evidence_id": "participants",
        "source_id": "paper",
        "section_id": "results",
        "text": (
            "We recruited 42 participants for the study."
            if exact
            else "The study discusses participant demographics and methods."
        ),
    }
    execution = execute_controller_turn(
        DocQARequest(
            prompt=question,
            retrieval_query=question,
            task_type="free_text",
            verification_domain="qasper",
            verification_mode="strict",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["paper"],
            origin="benchmark",
        ),
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: answer,
    )
    prediction = {
        **execution.as_dict(),
        "example_id": "typed-authority",
        "question": question,
        "answer_type": "evidence_qa" if exact else "unanswerable",
        "predicted_answer": execution.answer,
        "answer_for_user": execution.answer,
        "route": "text_rag",
        "gold_answers": [answer if exact else "unanswerable"],
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    return prediction


def _composite_prediction(
    *,
    question: str = "Did the authors evaluate both clinical and legal datasets?",
    evidence: list[dict] | None = None,
) -> dict:
    evidence = evidence or [
        {
            "evidence_id": "clinical",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "We evaluate the model on a clinical dataset.",
        },
        {
            "evidence_id": "legal",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "We evaluate the model on a legal dataset.",
        },
    ]
    execution = execute_controller_turn(
        DocQARequest(
            prompt=question,
            retrieval_query=question,
            task_type="boolean",
            verification_domain="qasper",
            verification_mode="strict",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["paper"],
            origin="benchmark",
        ),
        retrieve=lambda *_args: {"evidence": evidence},
        generate=lambda *_args: "yes",
    )
    prediction = {
        **execution.as_dict(),
        "example_id": "composite-authority",
        "question": question,
        "answer_type": "boolean",
        "predicted_answer": execution.answer,
        "answer_for_user": execution.answer,
        "route": "text_rag",
        "gold_answers": ["yes"],
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    return prediction


def _semantic_evidence() -> list[dict[str, str]]:
    return [
        {
            "evidence_id": "comparison",
            "source_id": "paper",
            "section_id": "experiments",
            "text": (
                "We compared cross-lingual and single-language evaluation "
                "in the same experiment."
            ),
        },
        {
            "evidence_id": "context",
            "source_id": "paper",
            "section_id": "experiments",
            "text": (
                "The same experiment included single-language evaluation "
                "for comparison."
            ),
        },
    ]


def _semantic_request(question: str) -> DocQARequest:
    return DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="boolean",
        verification_domain="qasper",
        verification_mode="strict",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        origin="benchmark",
        query_plan=build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="qasper",
        ),
    )


def _semantic_prediction() -> dict:
    question = "Did the authors compare cross-lingual and single-language evaluation?"
    evidence = _semantic_evidence()
    request = _semantic_request(question)

    execution = execute_controller_turn(
        request,
        retrieve=lambda *_args: {"evidence": evidence},
        generate=lambda *_args: "yes",
        proposition_verifier=_semantic_verdict,
    )
    prediction = {
        **execution.as_dict(),
        "example_id": "semantic-evidence-set-authority",
        "question": question,
        "answer_type": "boolean",
        "predicted_answer": execution.answer,
        "answer_for_user": execution.answer,
        "route": "text_rag",
        "gold_answers": ["yes"],
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    return prediction


def test_benchmark_only_audits_complete_runtime_typed_authority() -> None:
    prediction = _prediction(exact=True)
    before = (
        prediction["engine_terminal_answer"],
        prediction["predicted_answer"],
        prediction["answer_for_scoring"],
    )

    assert runtime_typed_proposition_authority(prediction)["complete"] is True
    assert not apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )

    assert (
        prediction["engine_terminal_answer"],
        prediction["predicted_answer"],
        prediction["answer_for_scoring"],
    ) == before
    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert trace["runtime_typed_authority_applicable"] is True
    assert trace["runtime_typed_authority_complete"] is True
    assert trace["runtime_typed_authority_state"] == "verified_support"
    assert trace["verifier_required_evidence_coverage"] == "1.000000"
    assert trace["verifier_missing_required_slot_ids"] == ""
    assert prediction["contract_action"] == "pass_through"


def test_tampered_authority_atom_is_reported_without_benchmark_repair() -> None:
    prediction = _prediction(exact=True)
    original_answer = prediction["engine_terminal_answer"]
    atom = prediction["engine_verify_decision"]["typed_authority"]["authority_atoms"][0]
    atom["evidence_ref"] = "tampered"

    audit = runtime_typed_proposition_authority(prediction)

    assert audit["complete"] is False
    assert audit["atom_status"] == "canonical_ref_identity_mismatch"
    assert audit["identity_status"] == "canonical_ref_identity_mismatch"
    assert audit["quote_grounding_status"] == "not_evaluated"
    assert prediction["engine_terminal_answer"] == original_answer


def test_quote_grounding_failure_is_distinct_from_identity_mismatch() -> None:
    prediction = _prediction(exact=True)
    atom = prediction["engine_verify_decision"]["typed_authority"]["authority_atoms"][0]
    atom["quote"] = "The evidence does not contain this quote."

    audit = runtime_typed_proposition_authority(prediction)

    assert audit["complete"] is False
    assert audit["atom_status"] == "quote_semantic_grounding_failure"
    assert audit["identity_status"] == "bound"
    assert audit["quote_grounding_status"] == "quote_semantic_grounding_failure"


def test_safe_missing_projection_contains_no_exact_claim_or_citation() -> None:
    prediction = _prediction(exact=False)
    audit = runtime_typed_proposition_authority(prediction)

    assert prediction["engine_terminal_answer"] == "unanswerable"
    assert audit["complete"] is True
    assert audit["state"] == "missing"
    decision = prediction["engine_verify_decision"]
    assert decision["verified_citations"] == []
    assert decision["authoritative_evidence_id"] == ""
    assert not any(
        result.get("authority_status") == "exact"
        for result in decision["claim_results"]
    )


def test_composite_runtime_authority_binds_every_premise() -> None:
    prediction = _composite_prediction()

    typed = runtime_typed_proposition_authority(prediction)
    boolean = runtime_boolean_authority(prediction, "yes")

    assert typed["complete"] is True
    assert typed["authority_kind"] == "composite"
    assert typed["derivation_status"] == "bound"
    assert typed["derivation_count"] == 1
    assert boolean["complete"] is True
    assert boolean["authority_kind"] == "composite_polarity"
    assert len(boolean["required_evidence_ids"]) == 2

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert prediction["contract_action"] == "pass_through"
    assert trace["runtime_typed_authority_kind"] == "composite"
    assert trace["runtime_typed_authority_derivation_status"] == "bound"
    assert trace["evidence_quote"] == ""
    assert trace["evidence_ref"] == ""
    assert trace["authoritative_quote_evidence_id"] == ""
    assert len(trace["runtime_typed_authority_premise_refs"]) == 2
    assert set(trace["runtime_typed_authority_premise_evidence_ids"]) == {
        "evidence:paper:clinical",
        "evidence:paper:legal",
    }


def test_composite_runtime_rejects_a_missing_premise_atom() -> None:
    prediction = _composite_prediction()
    authority = prediction["engine_verify_decision"]["typed_authority"]
    authority["authority_atoms"] = authority["authority_atoms"][:1]

    audit = runtime_typed_proposition_authority(prediction)

    assert audit["complete"] is False
    assert audit["derivation_status"] == "premise_atom_mismatch"


def test_composite_runtime_rejects_query_plan_operator_drift() -> None:
    prediction = _composite_prediction()
    plan = prediction["engine_terminal_evidence_bundle"]["metadata"]["query_plan"]
    plan["constraints"]["boolean_support_group"]["operator"] = "any"

    audit = runtime_typed_proposition_authority(prediction)

    assert audit["complete"] is False
    assert audit["derivation_status"] == "query_plan_derivation_mismatch"


def test_composite_required_citations_are_not_counted_as_nonminimal() -> None:
    prediction = _composite_prediction()
    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    contract_items = list(prediction["engine_terminal_evidence_bundle"]["items"])
    cited = minimum_verified_claim_support_items(
        prediction,
        contract_items,
        span="yes",
    )
    emitted = attach_structured_citations_from_evidence(prediction, span="yes")

    metrics = qasper_contract_metric_values(
        prediction,
        prediction["evidence_metadata"],
        cited=cited,
        contract_items=contract_items,
    )

    assert len(cited) == 2
    assert len(emitted) == 2
    assert metrics["citation_nonminimal_count"] == 0.0
    assert metrics["qasper_composite_authority_count"] == 1.0
    assert metrics["qasper_composite_authority_invalid_count"] == 0.0


def test_semantic_evidence_set_authority_round_trips_through_benchmark_audit() -> None:
    prediction = _semantic_prediction()

    typed = runtime_typed_proposition_authority(prediction)
    boolean = runtime_boolean_authority(prediction, "yes")

    _assert_semantic_typed_authority(typed, boolean)

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    trace = prediction["evidence_metadata"]["qasper_answerability"]
    contract_items = list(prediction["engine_terminal_evidence_bundle"]["items"])
    cited = minimum_verified_claim_support_items(
        prediction,
        contract_items,
        span="yes",
    )
    metrics = qasper_contract_metric_values(
        prediction,
        prediction["evidence_metadata"],
        cited=cited,
        contract_items=contract_items,
    )

    assert prediction["contract_action"] == "pass_through"
    _assert_semantic_trace(trace, typed)
    _assert_semantic_metrics(metrics, cited)


def test_semantic_repair_diagnostics_round_trip_through_benchmark_trace() -> None:
    prediction = _semantic_prediction()
    metadata = prediction["engine_terminal_evidence_bundle"]["metadata"]
    verifier = metadata["semantic_proposition_verifier"]
    verifier.update(semantic_repair_diagnostics())

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    trace = prediction["evidence_metadata"]["qasper_answerability"]

    assert trace["runtime_semantic_question_proposition_resolution"]["status"] == (
        "repaired"
    )
    assert trace["runtime_semantic_entailment_audit_rejection_count"] == 2
    assert trace["runtime_semantic_auditor_internal_inconsistency"] is True
    assert trace["runtime_semantic_auditor_internal_inconsistency_count"] == 1
    assert trace["runtime_semantic_local_premise_consistency"]["status"] == (
        "auditor_internal_inconsistency"
    )
    assert len(trace["runtime_semantic_local_premise_consistency_history"]) == 1
    assert trace["runtime_semantic_audit_verified_but_runtime_rejected_count"] == 1
    assert trace["runtime_semantic_runtime_contract_rejection_count"] == 1
    assert (
        trace["runtime_semantic_rejected_transactions"][0]["semantic_proof_digest"]
        == "before"
    )
    assert trace["runtime_semantic_proof_digest_changed"] is True


def _assert_semantic_typed_authority(typed: dict, boolean: dict) -> None:
    assert typed["complete"] is True
    assert typed["authority_kind"] == "semantic_evidence_set"
    assert set(typed["slot_ref_bindings"]) == {
        "support:proposition",
        "support:left_subject",
        "support:right_subject",
    }
    assert typed["derivation_status"] == "bound"
    assert boolean["complete"] is True
    assert boolean["authority_kind"] == "semantic_evidence_set_polarity"


def _assert_semantic_trace(trace: dict, typed: dict) -> None:
    assert trace["runtime_typed_authority_kind"] == "semantic_evidence_set"
    assert (
        trace["runtime_typed_authority_slot_ref_bindings"] == typed["slot_ref_bindings"]
    )
    assert trace["runtime_semantic_proposition_authority_status"] == "verified"
    assert trace["runtime_semantic_proposition_authority_premise_count"] == 1
    assert trace["runtime_semantic_proposition_verifier_model_call_count"] == 2
    assert trace["runtime_semantic_proposition_verifier_proposal_call_count"] == 1
    assert trace["runtime_semantic_entailment_audit_call_count"] == 1
    assert trace["runtime_semantic_proposition_verifier_available_evidence_count"] == 2
    assert trace["runtime_semantic_proposition_verifier_packed_evidence_count"] == 2
    assert (
        trace["runtime_semantic_proposition_verifier_evidence_item_char_limit"] == 2000
    )
    assert (
        trace["runtime_semantic_proposition_verifier_estimated_input_token_budget"]
        == 3072
    )
    assert trace["runtime_semantic_proposition_verifier_estimated_input_tokens"] == 220
    assert (
        trace["runtime_semantic_proposition_verifier_minimum_model_context_tokens"]
        == 4096
    )
    assert trace["runtime_semantic_proposition_verifier_packed_evidence_chars"] == 107
    assert trace["runtime_semantic_proposition_verifier_dropped_evidence_count"] == 0
    assert trace["runtime_semantic_proposition_verifier_truncated_evidence_count"] == 0
    assert trace["runtime_semantic_proposition_verifier_required_slot_count"] == 3
    assert trace["runtime_semantic_proposition_verifier_prompt_chars"] == 731
    assert trace["runtime_semantic_proposition_verifier_max_prompt_chars"] == 16000
    assert trace["runtime_semantic_proposition_verifier_max_output_tokens"] == 768
    assert trace["runtime_semantic_proposition_verifier_proposal_retry_count"] == 0
    assert trace["runtime_semantic_proposition_verifier_parse_failure_reason"] == ""
    assert trace["runtime_semantic_proposition_verifier_finish_reason"] == "stop"
    assert trace["runtime_semantic_proposition_verifier_completion_tokens"] == 244
    assert trace["runtime_semantic_entailment_audit_status"] == "verified"
    assert trace["runtime_semantic_entailment_audit_reason"] == ""
    assert trace["runtime_semantic_entailment_audit_model"] == (
        "independent-test-auditor"
    )


def _assert_semantic_metrics(metrics: dict, cited: list[dict]) -> None:
    assert len(cited) == 1
    assert metrics["qasper_semantic_evidence_set_authority_count"] == 1.0
    assert metrics["qasper_semantic_evidence_set_authority_invalid_count"] == 0.0
    assert metrics["qasper_semantic_proposition_verifier_call_count"] == 2.0
    assert metrics["qasper_semantic_entailment_audit_call_count"] == 1.0
    assert metrics["qasper_semantic_entailment_audit_failure_count"] == 0.0
    assert metrics["qasper_semantic_entailment_audit_rejection_count"] == 0.0
    assert metrics["qasper_semantic_proposition_output_truncation_count"] == 0.0
    assert metrics["qasper_semantic_proposition_json_decode_failure_count"] == 0.0
    assert metrics["qasper_semantic_proposition_verifier_failure_count"] == 0.0
    assert metrics["qasper_semantic_proposition_verifier_context_overflow_count"] == 0.0
    assert (
        metrics["qasper_semantic_proposition_verifier_schema_unsupported_count"] == 0.0
    )
    assert metrics["qasper_composite_authority_count"] == 0.0


def test_semantic_runtime_rejects_tampered_slot_reference_binding() -> None:
    prediction = _semantic_prediction()
    authority = prediction["engine_verify_decision"]["typed_authority"]
    authority["slot_ref_bindings"]["support:left_subject"] = ["tampered"]

    audit = runtime_typed_proposition_authority(prediction)

    assert audit["complete"] is False
    assert audit["authority_kind"] == "semantic_evidence_set"


def test_semantic_authority_rejection_is_a_hard_audit_failure() -> None:
    prediction = _semantic_prediction()
    metadata = prediction["engine_terminal_evidence_bundle"]["metadata"]
    metadata["semantic_proposition_authority"] = {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "status": "rejected",
        "reason": "semantic_premise_quote_unbound",
    }
    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    metrics = qasper_contract_metric_values(
        prediction,
        prediction["evidence_metadata"],
        cited=[],
        contract_items=list(prediction["engine_terminal_evidence_bundle"]["items"]),
    )

    assert metrics["qasper_semantic_evidence_set_authority_invalid_count"] == 1.0


def test_entity_type_derivation_is_declared_in_runtime_query_plan() -> None:
    prediction = _composite_prediction(
        question="Did the authors experiment with the toolkits?",
        evidence=[
            {
                "evidence_id": "definition",
                "source_id": "paper",
                "section_id": "introduction",
                "text": (
                    "We present AtlasCV and AtlasNLP, two open-source toolkits "
                    "for research."
                ),
            },
            {
                "evidence_id": "experiment",
                "source_id": "paper",
                "section_id": "experiments",
                "text": (
                    "In our experiments, we evaluate AtlasCV on two benchmark datasets."
                ),
            },
        ],
    )

    audit = runtime_typed_proposition_authority(prediction)
    plan = audit["authority"]
    terminal_plan = prediction["engine_terminal_evidence_bundle"]["metadata"][
        "query_plan"
    ]

    assert audit["complete"] is True
    assert audit["derivation_status"] == "bound"
    assert plan["authority_derivations"][0]["rule_id"] == (
        "same_source_entity_type_join.v1"
    )
    assert terminal_plan["constraints"]["boolean_support_group"]["rule_id"] == (
        "same_source_entity_type_join.v1"
    )
