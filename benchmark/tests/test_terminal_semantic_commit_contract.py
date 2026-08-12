from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.terminal_semantic_commit import build_terminal_semantic_commit

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.metrics import normalize_text
from benchmark.qasper_runtime_projection import (
    runtime_projection_present,
    terminal_commit_projection_present,
)
from benchmark.task_answer_contracts import synchronize_terminal_answer_state


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
