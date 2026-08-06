import json
from typing import Any

from benchmark.dataset_native_scores import (
    dataset_native_score_metadata,
    native_metrics_for_prediction,
)
from benchmark.mara_oriented_scores import add_mara_oriented_metrics
from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


def test_qasper_native_score_computes_dataset_token_f1_as_mara_score():
    prediction: dict[str, Any] = {
        "predicted_answer": "transformer baseline",
        "gold_answers": ["transformer baseline"],
        "metrics": {
            # Dataset-native scoring computes QASPER F1 from final answer text
            # instead of trusting a stale generic metric from an older artifact.
            "f1": 0.75,
            "page_hit": 0.0,
            "citation_recall": 0.0,
            "citation_precision": 0.0,
        },
        "diagnostics": {"controller_route_match": 0.0},
    }

    add_mara_oriented_metrics(prediction, dataset_name="qasper-dev")

    assert prediction["mara_scoring_contract"] == "qasper_answer_evidence_f1_v3"
    assert prediction["mara_primary_metric"] == "qasper_f1"
    assert prediction["mara_native_metrics"] == [
        "qasper_f1",
        "qasper_evidence_f1",
        "qasper_structure_valid",
        "qasper_typed_accuracy",
    ]
    assert prediction["metrics"]["qasper_f1"] == 1.0
    assert prediction["metrics"]["native_score"] == 1.0
    assert prediction["metrics"]["mara_score"] == 1.0
    assert (
        prediction["metrics"]["mara_proxy_score"] != prediction["metrics"]["mara_score"]
    )


def test_qasper_native_score_normalizes_boolean_aliases_and_unanswerable():
    boolean_metrics, _ = native_metrics_for_prediction(
        {
            "predicted_answer": "yes",
            "gold_answers": ["true"],
            "metrics": {},
        },
        dataset_name="qasper-dev",
    )
    unanswerable_metrics, _ = native_metrics_for_prediction(
        {
            "predicted_answer": "insufficient evidence",
            "gold_answers": ["unanswerable"],
            "metrics": {},
        },
        dataset_name="qasper-dev",
    )

    assert boolean_metrics["qasper_f1"] == 1.0
    assert boolean_metrics["qasper_structure_valid"] == 1.0
    assert unanswerable_metrics["qasper_f1"] == 1.0
    assert unanswerable_metrics["qasper_structure_valid"] == 1.0


def test_qasper_structure_valid_accepts_all_canonical_typed_answers():
    predicted_no_for_unanswerable, _ = native_metrics_for_prediction(
        {
            "predicted_answer": "no",
            "gold_answers": ["unanswerable"],
            "metrics": {},
        },
        dataset_name="qasper-dev",
    )
    predicted_unanswerable_for_boolean, _ = native_metrics_for_prediction(
        {
            "predicted_answer": "unanswerable",
            "gold_answers": ["no"],
            "metrics": {},
        },
        dataset_name="qasper-dev",
    )

    assert predicted_no_for_unanswerable["qasper_structure_valid"] == 1.0
    assert predicted_unanswerable_for_boolean["qasper_structure_valid"] == 1.0
    assert predicted_no_for_unanswerable["qasper_typed_accuracy"] == 0.0
    assert predicted_unanswerable_for_boolean["qasper_typed_accuracy"] == 0.0


def test_qasper_structure_valid_rejects_noncanonical_typed_answer():
    metrics, _ = native_metrics_for_prediction(
        {
            "predicted_answer": "The paper probably implies yes.",
            "gold_answers": ["unanswerable"],
            "metrics": {},
        },
        dataset_name="qasper-dev",
    )

    assert metrics["qasper_structure_valid"] == 0.0


def test_qasper_native_score_computes_token_f1_when_metric_is_missing():
    prediction: dict[str, Any] = {
        "predicted_answer": (
            "<think>Draft answer should not be scored.</think>\n"
            "Final answer: transformer baseline"
        ),
        "gold_answers": ["transformer evidence"],
        "metrics": {},
    }

    metrics, metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="qasper-dev",
    )

    assert metadata["contract_id"] == "qasper_answer_evidence_f1_v3"
    assert metadata["answer_token_f1_contract"] == "token_f1_v2"
    assert metrics["qasper_f1"] == 0.5
    assert metrics["native_score"] == 0.5


def test_qasper_native_score_reports_official_paragraph_evidence_f1():
    prediction: dict[str, Any] = {
        "predicted_answer": "Final answer: retrieval",
        "gold_answers": ["retrieval"],
        "metrics": {"span_recall": 1.0},
        "predicted_evidence": [
            "The method uses retrieval.",
            "A distractor paragraph.",
        ],
        "example_metadata": {
            "qasper_answer_annotations": [
                {
                    "extractive_spans": ["retrieval"],
                    "free_form_answer": "",
                    "yes_no": None,
                    "unanswerable": None,
                    "evidence": [
                        "The method uses retrieval.",
                        "The retrieval module is trained separately.",
                    ],
                },
                {
                    "extractive_spans": ["retrieval module"],
                    "free_form_answer": "",
                    "yes_no": None,
                    "unanswerable": None,
                    "evidence": ["Another annotated paragraph."],
                },
            ]
        },
    }

    metrics, metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="qasper-dev",
    )

    assert metadata["native_metrics"] == (
        "qasper_f1",
        "qasper_evidence_f1",
        "qasper_structure_valid",
        "qasper_typed_accuracy",
    )
    assert metrics["qasper_f1"] == 1.0
    assert metrics["qasper_evidence_f1"] == 0.5
    assert metrics["native_score"] == 1.0


def test_qasper_native_score_matches_gold_paragraph_inside_retrieved_chunk():
    prediction: dict[str, Any] = {
        "predicted_answer": "Final answer: retrieval",
        "gold_answers": ["retrieval"],
        "metrics": {},
        "retrieved_hits": [
            {
                "text": (
                    "The paper introduces the system. The method uses retrieval. "
                    "The following sentence is neighboring chunk context."
                )
            }
        ],
        "example_metadata": {
            "qasper_answer_annotations": [
                {
                    "extractive_spans": ["retrieval"],
                    "free_form_answer": "",
                    "yes_no": None,
                    "unanswerable": None,
                    "evidence": ["The method uses retrieval."],
                }
            ]
        },
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="qasper-dev",
    )

    assert metrics["qasper_evidence_f1"] == 1.0


def test_qasper_native_score_uses_answer_annotations_when_gold_answers_are_missing():
    prediction: dict[str, Any] = {
        "predicted_answer": "Final answer: document retrieval",
        "gold_answers": [],
        "metrics": {},
        "example_metadata": {
            "qasper_answer_annotations": [
                {
                    "extractive_spans": ["retrieval"],
                    "free_form_answer": "",
                    "yes_no": None,
                    "unanswerable": None,
                },
                {
                    "extractive_spans": [],
                    "free_form_answer": "document retrieval",
                    "yes_no": None,
                    "unanswerable": None,
                },
            ]
        },
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="qasper-dev",
    )

    assert metrics["qasper_f1"] == 1.0
    assert metrics["native_score"] == 1.0


def test_mara_score_does_not_fallback_to_proxy_when_native_score_is_missing():
    prediction: dict[str, Any] = {
        "metrics": {
            "f1": 0.9,
            "page_hit": 1.0,
            "citation_recall": 1.0,
            "citation_precision": 1.0,
            "unsupported_claim_rate": 0.0,
            "false_abstention": 0.0,
        },
    }

    add_mara_oriented_metrics(prediction, dataset_name="qasper-dev")

    assert prediction["metrics"]["native_score"] is None
    assert prediction["metrics"]["mara_score"] is None
    assert prediction["metrics"]["mara_proxy_score"] is not None


def test_financebench_native_score_prefers_numeric_match_over_lexical_f1():
    prediction: dict[str, Any] = {
        "predicted_answer": "$12.0 million",
        "gold_answers": ["12 million"],
        "metrics": {
            "f1": 0.1,
            "numeric_match": 1.0,
            "formula_match": 0.0,
            "em": 0.0,
        },
    }

    metrics, metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="financebench-main",
    )

    assert metadata["contract_id"] == "financebench_answer_correctness_v1"
    assert metrics["financebench_answer_score"] == 1.0
    assert metrics["native_score"] == 1.0


def test_financebench_native_score_does_not_use_high_f1_as_correctness():
    prediction: dict[str, Any] = {
        "predicted_answer": "Revenue was 12 million, not 15 million.",
        "gold_answers": ["Revenue was 15 million."],
        "metrics": {
            "f1": 0.9,
            "numeric_match": 0.0,
            "formula_match": 0.0,
            "em": 0.0,
        },
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="financebench-main",
    )

    assert metrics["financebench_answer_score"] == 0.0
    assert metrics["native_score"] == 0.0


def test_financebench_native_score_computes_f1_fallback_when_metric_is_missing():
    prediction: dict[str, Any] = {
        "predicted_answer": "Final answer: revenue increased",
        "gold_answers": ["revenue declined"],
        "metrics": {},
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="financebench-main",
    )

    assert metrics["financebench_answer_score"] == 0.5
    assert metrics["native_score"] == 0.5


def test_alce_native_score_combines_correctness_and_citation_quality():
    prediction: dict[str, Any] = {
        "predicted_answer": "Ada Lovelace [1]",
        "gold_answers": ["Ada Lovelace"],
        "metrics": {
            "f1": 0.5,
            "citation_recall": 1.0,
            "citation_precision": 1.0,
            "unsupported_claim_rate": 0.0,
        },
    }

    metrics, metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="alce-asqa",
    )

    assert metadata["contract_id"] == "alce_correctness_citation_v1"
    assert metrics["alce_correctness"] == 1.0
    assert metrics["alce_citation_f1"] == 1.0
    assert metrics["native_score"] == 1.0


def test_alce_correctness_does_not_use_citation_metrics_as_answer_score():
    prediction: dict[str, Any] = {
        "predicted_answer": "Charles Babbage [1]",
        "gold_answers": ["Ada Lovelace"],
        "metrics": {
            "f1": 0.0,
            "em": 0.0,
            "anls": 0.0,
            "citation_recall": 1.0,
            "citation_precision": 1.0,
            "unsupported_claim_rate": 0.0,
        },
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="alce-asqa",
    )

    assert metrics["alce_correctness"] == 0.0
    assert metrics["alce_citation_f1"] == 1.0
    assert metrics["native_score"] == 0.5


def test_alce_correctness_computes_answer_f1_when_metric_is_missing():
    prediction: dict[str, Any] = {
        "predicted_answer": "Ada Byron [1]",
        "gold_answers": ["Ada Lovelace"],
        "metrics": {
            "citation_recall": 1.0,
            "citation_precision": 1.0,
            "unsupported_claim_rate": 0.0,
        },
    }

    metrics, _metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="alce-asqa",
    )

    assert metrics["alce_correctness"] == 0.5
    assert metrics["alce_citation_f1"] == 1.0
    assert metrics["native_score"] == 0.75


def test_alce_qampari_native_score_uses_list_f1_not_generic_text_f1():
    prediction: dict[str, Any] = {
        "predicted_answer": "Heat [1], Sanctuary [2], Not a manga [3]",
        "gold_answers": [
            "Heat, Mai, the Psychic Girl, Wounded Man, Sanctuary, "
            "Crying Freeman, Strain."
        ],
        "metrics": {"f1": 0.9},
        "example_metadata": {
            "alce_task": "qampari",
            "alce_answers": [
                ["Heat"],
                ["Mai, the Psychic Girl"],
                ["Wounded Man"],
                ["Sanctuary"],
                ["Crying Freeman"],
                ["Strain"],
            ],
        },
    }

    metrics, metadata = native_metrics_for_prediction(
        prediction,
        dataset_name="alce-qampari",
    )

    assert metadata["contract_id"] == "alce_qampari_f1_v1"
    assert metadata["primary_metric"] == "qampari_f1"
    assert metrics["qampari_num_preds"] == 3.0
    assert metrics["qampari_prec"] == 0.6667
    assert metrics["qampari_rec"] == 0.3333
    assert metrics["qampari_rec_top5"] == 0.4
    assert metrics["qampari_f1"] == 0.4444
    assert metrics["qampari_f1_top5"] == 0.5
    assert metrics["native_score"] == 0.4444


def test_runner_promotes_native_score_and_records_scoring_contract(
    monkeypatch,
    tmp_path,
):
    class _RagTruthEngine:
        def __init__(self, _engine_name, _config):
            pass

        @staticmethod
        def run_example(_bundle, example):
            return {
                "example_id": example.example_id,
                "document_id": example.document_id,
                "question": example.question,
                "gold_answers": example.answers,
                "gold_pages": example.evidence_pages,
                "gold_sources": example.evidence_sources,
                "predicted_answer": json.dumps(
                    {"hallucination list": ["profit doubled"]}
                ),
                "predicted_pages": [],
                "predicted_sources": ["doc#source"],
                "predicted_element_ids": [],
                "retrieved_hits": [],
            }

    manifest_path = _write_ragtruth_manifest(tmp_path)
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _RagTruthEngine(engine_name, config),
    )

    report = run_benchmark(
        str(manifest_path),
        BenchmarkConfig(
            suite_name="ragtruth_native",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["example_metadata"]["labels"][0]["text"] == "profit doubled"
    assert prediction["mara_scoring_contract"] == "ragtruth_hallucination_spans_v1"
    assert prediction["mara_primary_metric"] == "ragtruth_hallucination_span_f1"
    assert prediction["metrics"]["native_score"] == 1.0
    assert prediction["metrics"]["mara_score"] == 1.0
    assert report["summary"]["mara_score_metadata"] == dataset_native_score_metadata(
        "ragtruth_plan5_guardrail_current"
    )
    assert report["summary"]["mara_proxy_score_metadata"]["scoring_mode"] == (
        "diagnostic_proxy_v1"
    )
    assert report["summary"]["mara_proxy_score_metadata"]["excluded_from_headline"] is (
        True
    )
    assert report["summary"]["avg_native_score"] == 1.0
    assert report["summary"]["quality_avg_native_score"] == 1.0
    assert report["summary"]["route_rankings"][0]["rank_metric"] == "avg_native_score"
    assert report["summary"]["primary_score_metric"] == "quality_avg_native_score"
    assert report["summary"]["primary_score_label"] == "Dataset-Native Local Score"
    assert report["summary"]["primary_score_scope"] == "qa_quality"
    assert report["summary"]["score_authority_level"] == "local_dataset_native"
    assert report["summary"]["paper_grade_score_available"] is False
    assert report["summary"]["primary_score"] == 1.0
    assert report["summary"]["diagnostic_score_metrics"] == [
        "avg_em",
        "avg_f1",
        "avg_anls",
    ]


def _write_ragtruth_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("Revenue rose.", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "ragtruth_plan5_guardrail_current",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "Check hallucination.",
                        "answers": ["Revenue rose and profit doubled."],
                        "metadata": {
                            "labels": [
                                {
                                    "label_type": "hallucination",
                                    "text": "profit doubled",
                                }
                            ]
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path
