from __future__ import annotations

from typing import Any

from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_authority import required_authority_audit
from benchmark.qasper_contract_invariants import qasper_contract_metric_values
from benchmark.qasper_evidence_priorities import qasper_evidence_priorities
from benchmark.qasper_prompt_budget import fit_qasper_verifier_items
from benchmark.qasper_support_binding import bind_answerability_support
from benchmark.task_answer_contracts import apply_task_answer_contract


def _item(evidence_id: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }


def _plan_prediction(slots: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "evidence_metadata": {
            "query_plan": {"evidence_slots": slots},
        }
    }


def test_required_verification_slots_remain_required_across_binding_states() -> None:
    filled = _item("filled", "The authors evaluate the model.")
    retrieved = _item("retrieved", "The authors report the evaluation results.")
    prediction = _plan_prediction(
        [
            {
                "slot_id": "support:missing",
                "required_for_retrieval": False,
                "required_for_execution": False,
                "required_for_verification": True,
                "status": "missing",
                "evidence_ids": [],
            },
            {
                "slot_id": "support:filled",
                "required_for_retrieval": False,
                "required_for_execution": False,
                "required_for_verification": True,
                "status": "filled",
                "evidence_ids": ["evidence:paper:filled"],
            },
            {
                "slot_id": "support:retrieved",
                "required_for_retrieval": False,
                "required_for_execution": False,
                "required_for_verification": True,
                "status": "retrieved_unverified",
                "evidence_ids": ["evidence:paper:retrieved"],
            },
        ]
    )

    priorities = qasper_evidence_priorities(
        prediction,
        [filled, retrieved],
        question="Did the authors evaluate the model?",
        candidate_answer="yes",
    )

    assert priorities.required_slot_ids == (
        "support:missing",
        "support:filled",
        "support:retrieved",
    )
    assert priorities.missing_required_slot_ids == ("support:missing",)
    assert set(priorities.required_evidence_ids) == {
        "evidence:paper:filled",
        "evidence:paper:retrieved",
    }


def test_missing_required_slot_has_zero_authority_coverage_not_not_applicable() -> None:
    prediction = _plan_prediction(
        [
            {
                "slot_id": "support:missing",
                "required_for_retrieval": False,
                "required_for_execution": False,
                "required_for_verification": True,
                "status": "missing",
                "evidence_ids": [],
            }
        ]
    )
    evidence = _item("context", "The appendix describes the implementation.")
    priorities = qasper_evidence_priorities(
        prediction,
        [evidence],
        question="Did the authors evaluate the model?",
        candidate_answer="yes",
    )

    _prompt, _bounded, trace = fit_qasper_verifier_items(
        [evidence],
        lambda value: f"QUESTION\n{value}",
        question="Did the authors evaluate the model?",
        candidate_answer="yes",
        required_evidence_ids=list(priorities.required_evidence_ids),
        required_slot_ids=list(priorities.required_slot_ids),
        missing_required_slot_ids=list(priorities.missing_required_slot_ids),
        missing_required_evidence_ids=list(priorities.missing_required_evidence_ids),
    )

    assert trace["verifier_required_slot_ids"] == "support:missing"
    assert trace["verifier_required_authority_status"] == "missing_required_evidence"
    assert trace["verifier_required_evidence_coverage"] == "0.000000"


def test_authority_audit_treats_explicit_missing_slot_as_applicable() -> None:
    trace = required_authority_audit(
        required=set(),
        selected_aliases=[],
        required_slot_ids=[],
        missing_required_slot_ids=["support:missing"],
        missing_required_evidence_ids=[],
    )

    assert trace["verifier_required_slot_ids"] == "support:missing"
    assert trace["verifier_required_authority_status"] == ("missing_required_evidence")
    assert trace["verifier_required_evidence_coverage"] == "0.000000"


def test_required_verification_candidates_are_forwarded_as_bounded_canonical_ids() -> (
    None
):
    items = [
        _item(f"candidate-{index}", f"The authors evaluate model variant {index}.")
        for index in range(5)
    ]
    prediction = _plan_prediction(
        [
            {
                "slot_id": "support:boolean_proposition",
                "required_for_retrieval": False,
                "required_for_execution": False,
                "required_for_verification": True,
                "statement_kind": "boolean_proposition",
                "status": "retrieved_unverified",
                "evidence_ids": [
                    f"evidence:paper:candidate-{index}" for index in range(5)
                ],
            }
        ]
    )

    priorities = qasper_evidence_priorities(
        prediction,
        items,
        question="Did the authors evaluate the model?",
        candidate_answer="yes",
    )

    assert len(priorities.required_evidence_ids) == 2
    assert set(priorities.required_evidence_ids) <= {
        f"evidence:paper:candidate-{index}" for index in range(5)
    }


def test_ambiguous_canonical_quote_does_not_promote_retrieved_slot_to_verified() -> (
    None
):
    quote = "The authors evaluate the model."
    first = _item("first", quote)
    first.update({"canonical_start": 0, "canonical_end": len(quote)})
    second = _item("second", quote)
    second.update({"canonical_start": 100, "canonical_end": 100 + len(quote)})
    metadata: dict[str, Any] = {
        "qasper_answerability": {
            "quote_grounded": "true",
            "evidence_quote": quote,
        },
        "query_plan": {
            "evidence_slots": [
                {
                    "slot_id": "support:boolean_proposition",
                    "role": "support",
                    "statement_kind": "boolean_proposition",
                    "required_for_verification": True,
                    "required_for_retrieval": False,
                    "status": "retrieved_unverified",
                    "evidence_ids": [
                        "evidence:paper:first",
                        "evidence:paper:second",
                    ],
                }
            ]
        },
    }

    bind_answerability_support(
        {
            "answer_type": "boolean",
            "evidence_metadata": metadata,
        },
        metadata,
        answer="yes",
        trace=metadata["qasper_answerability"],
        evidence_items=[first, second],
    )

    [slot] = metadata["query_plan"]["evidence_slots"]
    assert slot["status"] == "retrieved_unverified"


def test_applicable_authority_metric_defaults_to_zero_when_trace_omits_coverage() -> (
    None
):
    prediction = {
        "answer_type": "free_text",
        "gold_answers": ["The evaluation"],
        "answer_for_scoring": "unanswerable",
    }
    metadata = {
        "qasper_answerability": {
            "verifier_required_slot_ids": "support:answer",
            "verifier_required_evidence_ids": "",
            "verifier_required_authority_status": "missing_required_evidence",
        }
    }

    metrics = qasper_contract_metric_values(
        prediction,
        metadata,
        cited=[],
        contract_items=[],
    )

    assert metrics["verifier_required_evidence_coverage"] == 0.0


def test_missing_boolean_candidate_still_records_required_slot_authority() -> None:
    prediction: dict[str, Any] = {
        "question": "Did the authors evaluate the model?",
        "answer_type": "boolean",
        "predicted_answer": "unanswerable",
        "evidence_metadata": {
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:boolean_proposition",
                        "statement_kind": "boolean_proposition",
                        "required_for_verification": True,
                        "status": "missing",
                        "evidence_ids": [],
                    }
                ]
            }
        },
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(
            AssertionError("missing authority must not call the verifier")
        ),
    )

    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert trace["verifier_required_slot_ids"] == "support:boolean_proposition"
    assert trace["verifier_missing_required_slot_ids"] == (
        "support:boolean_proposition"
    )
    assert trace["verifier_required_authority_status"] == ("missing_required_evidence")
    assert trace["verifier_required_evidence_coverage"] == "0.000000"


def test_qasper_boolean_summary_exposes_real_required_slot_denominator() -> None:
    prediction = {
        "question": "Did the authors evaluate the model?",
        "answer_type": "boolean",
        "predicted_answer": "unanswerable",
        "answer_for_scoring": "unanswerable",
        "mara_scoring_contract": "qasper_answer_evidence_f1_v3",
        "evidence_metadata": {
            "qasper_answerability": {
                "contract_id": "qasper_answerability.v15",
                "status": "not_required",
            }
        },
    }

    summary = contract_invariant_summary([prediction])

    assert summary["qasper_required_verification_applicable_count"] == 1.0
    assert summary["qasper_required_slot_nonempty_state_count"] == 0.0
    assert summary["qasper_required_slot_empty_state_count"] == 1.0
    assert summary["qasper_required_evidence_coverage_missing_count"] == 1.0
    assert summary["verifier_required_evidence_coverage"] == 0.0
    assert summary["qasper_required_slot_authority_empty_count"] == 1.0
