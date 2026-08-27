from __future__ import annotations

from benchmark.dataset_native_scores import qasper_annotation_diagnostics


def test_qasper_scores_each_annotation_and_marks_disagreement() -> None:
    rows, diagnostics = qasper_annotation_diagnostics(
        {
            "predicted_answer": "yes",
            "predicted_evidence": ["The authors compared both systems."],
            "example_metadata": {
                "qasper_answer_annotations": [
                    {
                        "annotation_id": "a1",
                        "worker_id": "w1",
                        "yes_no": True,
                        "unanswerable": False,
                        "extractive_spans": [],
                        "free_form_answer": "",
                        "evidence": ["The authors compared both systems."],
                    },
                    {
                        "annotation_id": "a2",
                        "worker_id": "w2",
                        "yes_no": None,
                        "unanswerable": True,
                        "extractive_spans": [],
                        "free_form_answer": "",
                        "evidence": [],
                    },
                ]
            },
        }
    )

    assert [row["annotation_id"] for row in rows] == ["a1", "a2"]
    assert rows[0]["typed_accuracy"] == 1.0
    assert rows[1]["typed_accuracy"] == 0.0
    assert rows[0]["evidence_f1"] == 1.0
    assert diagnostics["annotation_count"] == 2
    assert diagnostics["ambiguous"] is True
    assert diagnostics["ambiguity_reasons"] == [
        "annotation_answer_disagreement",
        "annotation_type_disagreement",
    ]
    assert all(row["ambiguity_marker"] for row in rows)


def test_qasper_no_annotation_records_auditable_role_incompatibility() -> None:
    rows, diagnostics = qasper_annotation_diagnostics(
        {
            "question": "Did the authors collect the two datasets?",
            "predicted_answer": "no",
            "predicted_evidence": [],
            "example_metadata": {
                "qasper_answer_annotations": [
                    {
                        "annotation_id": "no-role-mismatch",
                        "yes_no": False,
                        "unanswerable": False,
                        "extractive_spans": [],
                        "free_form_answer": "",
                        "evidence": [
                            "We evaluated two datasets: Alpha and Beta.",
                            "We collected Alpha, while Beta came from an existing "
                            "external source.",
                        ],
                    }
                ]
            },
        }
    )

    semantics = rows[0]["no_evidence_semantics"]
    assert semantics["classification"] == "role_incompatibility"
    assert semantics["admissible_as_explicit_contradiction"] is True
    assert diagnostics["ambiguous"] is False
    assert diagnostics["boolean_no_evidence_semantics"] == {"role_incompatibility": 1}


def test_qasper_no_annotation_marks_closed_world_contract_ambiguity() -> None:
    rows, diagnostics = qasper_annotation_diagnostics(
        {
            "question": "Did the authors collect the two datasets?",
            "predicted_answer": "unanswerable",
            "predicted_evidence": [],
            "example_metadata": {
                "qasper_answer_annotations": [
                    {
                        "annotation_id": "no-by-omission",
                        "yes_no": False,
                        "unanswerable": False,
                        "extractive_spans": [],
                        "free_form_answer": "",
                        "evidence": ["We evaluated two datasets in the experiments."],
                    }
                ]
            },
        }
    )

    semantics = rows[0]["no_evidence_semantics"]
    assert semantics["classification"] == "absence_only"
    assert semantics["closed_world_inference_required"] is True
    assert diagnostics["ambiguous"] is True
    assert diagnostics["ambiguity_reasons"] == [
        "boolean_no_requires_closed_world_inference"
    ]
