from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import benchmark.prediction_completion as prediction_completion


def test_post_contract_recovery_overrides_legacy_product_abstention(
    monkeypatch,
) -> None:
    prediction: dict[str, Any] = {
        "question": "Did the authors evaluate the model on relevant tasks?",
        "answer_type": "boolean",
        "predicted_answer": "unanswerable",
        "guardrail_decision": {
            "status": "not_enough_evidence",
            "action": "abstain",
        },
        "verify_decision": {
            "status": "not_enough_evidence",
            "action": "abstain",
        },
        "evidence_metadata": {},
    }

    def apply_contract(
        prediction: dict[str, Any],
        *,
        dataset_name: str,
        llm_factory,
    ) -> bool:
        assert dataset_name == "qasper_typed_v2"
        prediction["predicted_answer"] = "yes"
        prediction["verify_decision"] = {
            "status": "supported",
            "action": "return",
        }
        prediction["post_contract_verification"] = {
            "answer": "yes",
            "status": "supported",
            "verify_decision": dict(prediction["verify_decision"]),
        }
        prediction["task_answer_contract"] = {
            "contract_id": "qasper_answerability.v14",
            "status": "applied",
        }
        prediction["evidence_metadata"].update(
            {
                "qasper_answerability": {
                    "final_post_contract_answer": "yes",
                    "verdict": "yes",
                },
                "answerability_contract_trace": {
                    "post_contract_answer": "yes",
                    "final_post_contract_answer": "yes",
                },
                "answer_dependent_state": "post_contract_verified",
            }
        )
        return True

    monkeypatch.setattr(
        prediction_completion,
        "apply_task_answer_contract",
        apply_contract,
    )

    prediction_completion._finalize_answer(
        prediction,
        dataset_name="qasper_typed_v2",
        answer_mode="scoring_adapter_v1",
        engine=SimpleNamespace(task_contract_llm=lambda: None),
    )

    assert prediction["predicted_answer"] == "yes"
    assert prediction["answer_for_user"] == "yes"
    assert prediction["answer_for_scoring"] == "yes"
    assert prediction["answer_status"] == "answered"
    assert prediction["post_contract_verification"]["answer"] == "yes"


def test_post_contract_recovery_survives_final_citation_rendering(
    monkeypatch,
) -> None:
    prediction: dict[str, Any] = {
        "question": "Did the authors evaluate the model on relevant tasks?",
        "answer_type": "boolean",
        "predicted_answer": "unanswerable",
        "gold_evidence": [{"document_id": "paper", "page": "1"}],
        "guardrail_decision": {
            "status": "not_enough_evidence",
            "action": "abstain",
        },
        "verify_decision": {
            "status": "not_enough_evidence",
            "action": "abstain",
        },
        "evidence_metadata": {},
    }

    def apply_contract(
        prediction: dict[str, Any],
        *,
        dataset_name: str,
        llm_factory,
    ) -> bool:
        assert dataset_name == "qasper_typed_v2"
        prediction["predicted_answer"] = "yes"
        prediction["structured_citations"] = [
            {
                "kind": "page",
                "source_id": "paper",
                "page_label": "1",
            }
        ]
        prediction["predicted_citations"] = ["paper#page:1"]
        prediction["verify_decision"] = {
            "status": "supported",
            "action": "return",
        }
        prediction["post_contract_verification"] = {
            "answer": "yes",
            "status": "supported",
            "verify_decision": dict(prediction["verify_decision"]),
        }
        prediction["task_answer_contract"] = {
            "contract_id": "qasper_answerability.v14",
            "status": "applied",
        }
        prediction["evidence_metadata"].update(
            {
                "qasper_answerability": {
                    "final_post_contract_answer": "yes",
                    "verdict": "yes",
                },
                "answerability_contract_trace": {
                    "post_contract_answer": "yes",
                    "final_post_contract_answer": "yes",
                },
                "answer_dependent_state": "post_contract_verified",
            }
        )
        return True

    monkeypatch.setattr(
        prediction_completion,
        "apply_task_answer_contract",
        apply_contract,
    )

    prediction_completion._finalize_answer(
        prediction,
        dataset_name="qasper_typed_v2",
        answer_mode="scoring_adapter_v1",
        engine=SimpleNamespace(task_contract_llm=lambda: None),
    )

    assert prediction["answer_for_user"] == "yes paper#page:1"
    assert prediction["answer_for_scoring"] == "yes"
    assert prediction["answer_status"] == "answered"
    assert prediction["post_contract_verification"]["answer"] == "yes"
