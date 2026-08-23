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
