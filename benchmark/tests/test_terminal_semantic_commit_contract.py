from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.execution import (
    ABSTAIN_MESSAGE,
    GuardrailDecision,
    _result,
    execute_controller_turn,
)
from ktem.docqa.execution_models import RouteExecutionResult
from ktem.docqa.route_selection import ControllerDecision
from ktem.docqa.terminal_semantic_commit import build_terminal_semantic_commit
from ktem.docqa.verification import VerifyDecision

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.metrics import normalize_text
from benchmark.qasper_runtime_projection import (
    runtime_projection_present,
    terminal_commit_projection_present,
)
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)


def _runtime_prediction(answer: str, *, dataset_name: str) -> dict:
    question = "Which inputs does the method rely on?"
    evidence = {
        "evidence_id": "inputs",
        "source_id": "paper",
        "span_id": "inputs-span",
        "text": answer,
    }
    execution = execute_controller_turn(
        DocQARequest(
            prompt=question,
            retrieval_query=question,
            task_type="free_text",
            verification_domain="general",
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
        "question": question,
        "answer_type": "free_text",
        "predicted_answer": execution.answer,
        "route": "text_rag",
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    finalize_prediction_answer(
        prediction,
        dataset_name=dataset_name,
        mode="scoring_adapter_v1",
    )
    synchronize_terminal_answer_state(prediction)
    return prediction


def _safe_abstention_execution() -> tuple[str, RouteExecutionResult]:
    question = "Which inputs does the method rely on?"
    verify = VerifyDecision(
        mode="strict",
        status="unknown",
        reason="Strict verification could not establish claim-level support.",
        action="abstain",
        claims=["The method relies on an unsupported input."],
        unknown_claims=["The method relies on an unsupported input."],
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": "The method relies on an unsupported input.",
                "status": "unknown",
                "supporting_evidence_ids": [],
                "contradicting_evidence_ids": [],
            }
        ],
    )
    guardrail = GuardrailDecision(
        "unknown",
        "abstain",
        "Strict verification could not establish claim-level support.",
    )
    return question, _result(
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
        ControllerDecision(
            route="doc_text",
            legacy_route="doc_text",
            policy="document",
            controller_mode="heuristic",
            requires_retrieval=True,
            reason="test route",
        ),
        RetrieveDecision("good", "evidence found"),
        verify,
        guardrail,
        EvidenceBundle(
            route="doc_text",
            items=[
                {
                    "evidence_id": "retrieved-only",
                    "source_id": "paper",
                    "text": "The paper describes a different input.",
                }
            ],
        ),
        {"route": "doc_text"},
        ABSTAIN_MESSAGE,
        raw_generated_answer="The method relies on an unsupported input.",
    )


def _safe_abstention_prediction() -> tuple[dict, dict, dict]:
    question, execution = _safe_abstention_execution()
    prediction = {
        **execution.as_dict(),
        "question": question,
        "answer_type": "free_text",
        "predicted_answer": execution.answer,
        "route": "text_rag",
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    before_verify = deepcopy(prediction["engine_verify_decision"])
    before_guardrail = deepcopy(prediction["engine_terminal_guardrail_decision"])
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_contract_smoke",
        mode="scoring_adapter_v1",
    )
    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_contract_smoke",
        llm_factory=lambda: (_ for _ in ()).throw(
            AssertionError("terminal commit must remain the only semantic writer")
        ),
    )
    assert synchronize_terminal_answer_state(prediction)
    return prediction, before_verify, before_guardrail


def test_safe_abstention_has_one_runtime_semantic_identity() -> None:
    prediction, before_verify, before_guardrail = _safe_abstention_prediction()

    committed_answers = {
        prediction["engine_terminal_commit"]["semantic_answer"],
        prediction["engine_terminal_answer"],
        prediction["terminal_answer_state"]["answer"],
        prediction["predicted_answer"],
        prediction["answer_for_scoring"],
    }
    assert committed_answers == {"unanswerable"}
    assert prediction["engine_terminal_commit"]["contract_id"] == (
        "terminal_semantic_commit.v2"
    )
    assert prediction["engine_terminal_commit"]["state_version"] == 2
    assert prediction["answer_for_user"] == ABSTAIN_MESSAGE
    assert prediction["answer_status"] == "abstained"
    assert prediction["terminal_answer_state"]["supporting_evidence"] == []
    assert prediction["structured_citations"] == []
    assert prediction["predicted_citations"] == []
    assert prediction["verify_decision"] == before_verify
    assert prediction["guardrail_decision"] == before_guardrail
    assert prediction["engine_verify_decision"] == before_verify
    assert prediction["engine_terminal_guardrail_decision"] == before_guardrail
    assert runtime_projection_present(prediction)
    assert terminal_commit_projection_present(prediction["engine_terminal_commit"])
    assert (
        contract_invariant_summary([prediction])["qasper_stale_verifier_state_count"]
        == 0.0
    )


def test_safe_abstention_finalization_and_synchronization_are_idempotent() -> None:
    prediction, before_verify, before_guardrail = _safe_abstention_prediction()
    expected = deepcopy(prediction)

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_contract_smoke",
        mode="scoring_adapter_v1",
    )
    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_contract_smoke",
        llm_factory=lambda: (_ for _ in ()).throw(
            AssertionError("idempotent finalization must not invoke an LLM")
        ),
    )
    assert synchronize_terminal_answer_state(prediction)

    for key in (
        "engine_terminal_commit",
        "engine_terminal_answer",
        "terminal_answer_state",
        "predicted_answer",
        "answer_for_scoring",
        "answer_for_user",
        "answer_status",
        "structured_citations",
        "predicted_citations",
    ):
        assert prediction[key] == expected[key]
    assert prediction["verify_decision"] == before_verify
    assert prediction["guardrail_decision"] == before_guardrail


def test_safe_abstention_hashed_semantic_projection_rejects_tampering() -> None:
    prediction, _before_verify, _before_guardrail = _safe_abstention_prediction()

    for path in (
        ("engine_terminal_commit", "semantic_answer"),
        ("engine_terminal_state", "answer"),
        ("engine_terminal_answer",),
    ):
        tampered = deepcopy(prediction)
        target = tampered
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = "tampered"
        assert not runtime_projection_present(tampered)

    tampered_terminal = deepcopy(prediction)
    tampered_terminal["terminal_answer_state"]["answer"] = "tampered"
    assert (
        contract_invariant_summary([tampered_terminal])[
            "qasper_stale_verifier_state_count"
        ]
        == 1.0
    )

    legacy = deepcopy(prediction["engine_terminal_commit"])
    legacy["contract_id"] = "terminal_semantic_commit.v1"
    legacy["state_version"] = 1
    legacy["projection_hash"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in legacy.items() if key != "projection_hash"},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    assert not terminal_commit_projection_present(legacy)


def test_runtime_commit_preserves_every_free_text_sentence_and_qualifier():
    answer = (
        "The method uses labeled features.\n"
        "It also relies on class distribution, only for in-domain queries."
    )
    prediction = _runtime_prediction(answer, dataset_name="docqa_contract_smoke")

    expected = normalize_text(answer)
    assert normalize_text(prediction["engine_terminal_answer"]) == expected
    assert normalize_text(prediction["predicted_answer"]) == expected
    assert normalize_text(prediction["answer_for_scoring"]) == expected
    assert normalize_text(prediction["terminal_answer_state"]["answer"]) == expected


def test_runtime_commit_exposes_immutable_semantic_projection_and_hash():
    prediction = _runtime_prediction(
        "The method uses labeled features [1].",
        dataset_name="docqa_contract_smoke",
    )

    commit = prediction["engine_terminal_commit"]
    assert commit["semantic_answer"] == "The method uses labeled features [1]."
    assert commit["answer_status"] == "answered"
    assert commit["authoritative_evidence"]
    assert commit["projection_hash"]
    assert terminal_commit_projection_present(commit)
    assert prediction["engine_terminal_state"]["terminal_semantic_commit"] == commit

    tampered = deepcopy(commit)
    tampered["semantic_answer"] = "tampered"
    assert terminal_commit_projection_present(commit)
    assert not terminal_commit_projection_present(tampered)
    tampered["projection_hash"] = hashlib.sha256(
        json.dumps(
            {key: value for key, value in tampered.items() if key != "projection_hash"},
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    tampered_prediction = deepcopy(prediction)
    tampered_prediction["engine_terminal_commit"] = tampered
    assert terminal_commit_projection_present(tampered)
    assert not runtime_projection_present(tampered_prediction)
    prediction["answer_for_scoring"] = "tampered"
    assert prediction["engine_terminal_commit"] == commit
    assert prediction["engine_terminal_state"]["terminal_semantic_commit"] == commit


def test_citation_only_cleanup_does_not_drop_later_answer_items():
    answer = (
        "The method uses labeled features [1]. It also uses class distribution [2]."
    )
    prediction = _runtime_prediction(answer, dataset_name="qasper_contract_smoke")

    scored = normalize_text(prediction["answer_for_scoring"])
    assert scored == normalize_text(
        "The method uses labeled features. It also uses class distribution."
    )
    assert "class distribution" in scored


def test_terminal_scoring_preserves_it_is_and_it_was_sentences():
    answer = "It is a multi-stage method. It was evaluated on two tasks."
    prediction = _runtime_prediction(answer, dataset_name="docqa_contract_smoke")

    assert prediction["answer_for_scoring"] == (
        "It is a multi-stage method. It was evaluated on two tasks"
    )


def test_terminal_scoring_preserves_every_committed_list_item():
    answer = "- first finding [1]\n- second finding [2]\n3. third finding."
    prediction = _runtime_prediction(answer, dataset_name="docqa_contract_smoke")

    assert prediction["answer_for_scoring"] == (
        "first finding second finding 3. third finding"
    )
    assert all(
        item in prediction["answer_for_scoring"]
        for item in ("first finding", "second finding", "third finding")
    )


def test_summary_retains_agent_mode_and_route_policy_observability():
    from benchmark.summary import _route_metric_table

    prediction = {
        "route": "controller_auto",
        "agent_mode": "thorough",
        "route_policy": "auto",
        "metrics": {},
        "benchmark_role": "qa_quality",
        "verifier_observability": {},
    }

    [row] = _route_metric_table("qasper", [prediction])

    assert row["agent_modes"] == ["thorough"]
    assert row["route_policies"] == ["auto"]


def test_terminal_commit_never_promotes_unverified_retrieved_items():
    for status in ("not_required", "unsupported"):
        commit = build_terminal_semantic_commit(
            "retrieved prose",
            {
                "status": status,
                "verified_citations": [],
            },
            {"status": "ok", "action": "return"},
            {
                "items": [{"evidence_id": "retrieved-only", "text": "raw"}],
                "metadata": {
                    "selected_evidence": [
                        {"evidence_id": "selected-only", "text": "raw"}
                    ]
                },
            },
        )

        assert commit.authoritative_evidence == ()


def test_terminal_commit_projection_ignores_mutable_claim_verification():
    prediction = _runtime_prediction(
        "The method uses labeled features.", dataset_name="docqa_contract_smoke"
    )
    prediction["claim_verification"] = {
        "status": "tampered",
        "claim_results": [{"status": "unsupported"}],
    }

    assert synchronize_terminal_answer_state(prediction) is True
    state_claims = prediction["terminal_answer_state"]["claim_verification"]
    assert (
        state_claims["status"]
        == prediction["engine_terminal_commit"]["verify_decision"]["status"]
    )
    assert state_claims["status"] != "tampered"


def test_terminal_commit_projection_rejects_mutable_scoring_answer():
    prediction = _runtime_prediction(
        "The method uses labeled features [1].",
        dataset_name="docqa_contract_smoke",
    )
    prediction["answer_for_scoring"] = "tampered"

    assert synchronize_terminal_answer_state(prediction) is True
    assert (
        prediction["predicted_answer"]
        == prediction["engine_terminal_commit"]["semantic_answer"]
    )
    assert prediction["answer_for_scoring"] == "The method uses labeled features"
