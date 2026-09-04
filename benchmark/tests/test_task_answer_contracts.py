from types import SimpleNamespace
from typing import Any

from benchmark.task_answer_contracts import apply_task_answer_contract


class _VerifierLLM:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append((prompt, kwargs))
        return SimpleNamespace(text=self.response)


def test_qasper_adapter_never_recovers_missing_runtime_projection():
    llm = _VerifierLLM(
        '{"verdict":"yes_complete","evidence_ref":"E1:S1","evidence_quote":'
        '"The authors released their source code with the paper."}'
    )
    prediction: dict[str, Any] = {
        "question": "Did the authors release the code?",
        "predicted_answer": "unanswerable",
        "answer_type": "boolean",
        "context_preview": ("The authors released their source code with the paper."),
        "evidence_metadata": {
            "pre_guardrail_answer": "unanswerable",
            "pre_verification_answer": "yes",
        },
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=lambda: llm,
    )

    assert prediction["predicted_answer"] == "unanswerable"
    assert prediction["evidence_metadata"]["qasper_answerability"]["status"] == (
        "violation"
    )
    trace = prediction["evidence_metadata"]["answerability_contract_trace"]
    assert trace["pre_contract_answer"] == ""
    assert trace["post_contract_answer"] == "unanswerable"
    assert trace["rewrite_applied"] is False
    assert trace["rewrite_type"] == "none"
    assert trace["post_engine_answerability_llm_call_count"] == 0
    assert prediction["task_answer_contract"] == {
        "contract_id": "qasper_runtime_authority_audit.v1",
        "status": "violation",
    }
    assert llm.calls == []


def test_qasper_adapter_does_not_reconstruct_evidence_priorities():
    prediction: dict[str, Any] = {
        "question": "Did the authors release the code?",
        "predicted_answer": "yes",
        "answer_type": "boolean",
        "context_preview": "The authors released the code.",
        "evidence_metadata": {},
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    assert prediction["predicted_answer"] == "yes"
    assert prediction["contract_action"] == ("hard_violation_missing_runtime_authority")
    assert prediction["post_engine_answerability_llm_call_count"] == 0


def test_legacy_answerability_trace_cannot_bypass_runtime_audit():
    prediction: dict[str, Any] = {
        "question": "Did the authors release the code?",
        "predicted_answer": "yes",
        "answer_type": "boolean",
        "evidence_metadata": {
            "qasper_answerability": {
                "contract_id": "qasper_answerability.v11",
                "status": "ok",
            }
        },
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    assert prediction["task_answer_contract"]["status"] == "violation"
    assert (
        prediction["evidence_metadata"]["qasper_answerability"]["contract_id"]
        == "qasper_runtime_authority_audit.v1"
    )


def test_task_answer_contract_ignores_other_datasets():
    prediction: dict[str, Any] = {
        "question": "Did revenue grow?",
        "predicted_answer": "yes",
        "evidence_metadata": {},
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="financebench",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    assert "task_answer_contract" not in prediction
