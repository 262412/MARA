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


def test_qasper_answerability_contract_runs_after_engine_projection():
    llm = _VerifierLLM(
        '{"verdict":"yes_complete","evidence_quote":'
        '"The authors released their source code with the paper."}'
    )
    prediction: dict[str, Any] = {
        "question": "Did the authors release the code?",
        "predicted_answer": "unanswerable",
        "answer_type": "boolean",
        "context_preview": ("The authors released their source code with the paper."),
        "evidence_metadata": {},
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper",
        llm_factory=lambda: llm,
    )

    assert prediction["predicted_answer"] == "yes"
    assert prediction["evidence_metadata"]["qasper_answerability"]["status"] == "ok"
    assert prediction["task_answer_contract"] == {
        "contract_id": "qasper_answerability.v12",
        "status": "applied",
    }
    assert len(llm.calls) == 1


def test_qasper_answerability_contract_does_not_run_twice():
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

    assert prediction["task_answer_contract"]["status"] == "already_applied"


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
