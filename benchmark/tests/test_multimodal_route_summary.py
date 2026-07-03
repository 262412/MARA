from benchmark.multimodal_route_report import phase3_report_sections
from benchmark.multimodal_route_summary import phase3_multimodal_summary
from benchmark.summary import add_mara_summary_fields


def test_phase3_summary_reports_backend_readiness_and_element_coverage():
    predictions = [
        {
            "route": "page_image_rag_vlm",
            "benchmark_role": "qa_quality",
            "question": "Which chart label is shown on the slide?",
            "evidence_metadata": {
                "page_image_index": [
                    {"evidence_id": "page-image:doc:1", "modality": "page_image"}
                ],
            },
            "retrieved_hits": [
                {"evidence_id": "page-image:doc:1", "modality": "page_image"}
            ],
            "metrics": {"f1": 0.4, "native_score": 0.4, "page_hit": 1.0},
            "performance": {},
        },
        {
            "example_id": "ex-element-ok",
            "route": "element_rag",
            "benchmark_role": "prototype",
            "question": "What value is in the table?",
            "evidence_metadata": {
                "element_index": [
                    {
                        "evidence_id": "element:doc:1:table1",
                        "modality": "table",
                    },
                    {
                        "evidence_id": "element:doc:1:figure1",
                        "modality": "figure",
                    },
                ],
            },
            "retrieved_hits": [
                {"evidence_id": "element:doc:1:table1", "modality": "table"}
            ],
            "metrics": {"f1": 0.2, "element_hit": 1.0},
            "performance": {},
        },
    ]

    summary = phase3_multimodal_summary(
        "slidevqa_test_shard0_multimodal",
        predictions,
        backend_metadata={
            "page_image_rag_vlm": {
                "visual_retriever": "colqwen",
                "generator_backend": "local_qwen3_vl",
                "requires_backend_config": True,
            }
        },
        skipped_routes=[],
        active_routes=[
            {"route_id": "page_image_rag_vlm"},
            {"route_id": "element_rag"},
        ],
    )

    assert summary["page_image"]["status"] == "vlm_live"
    assert summary["page_image"]["visual_retriever"] == "colqwen"
    assert summary["page_image"]["visual_generator"] == "local_qwen3_vl"
    assert summary["element"]["status"] == "index_coverage_present"
    assert summary["element"]["predictions_with_element_index"] == 1
    assert summary["element"]["avg_element_index_records"] == 2.0
    assert summary["element"]["coverage_report"] == {
        "total_predictions": 1,
        "predictions_with_element_index": 1,
        "predictions_without_element_index": 0,
        "total_element_index_records": 2,
        "records_by_modality": {"figure": 1, "table": 1},
        "records_by_source": {"unknown": 2},
        "missing_example_ids": [],
    }
    assert summary["graph"]["scope"] == "local_lightweight_only"
    assert summary["graph"]["full_graphrag_claim"] is False


def test_phase3_summary_marks_blocked_vlm_and_element_coverage_gap():
    summary = phase3_multimodal_summary(
        "slidevqa_test_shard0_multimodal",
        [
            {
                "example_id": "ex-element-gap",
                "route": "element_rag",
                "benchmark_role": "prototype",
                "question": "What value is in the table?",
                "evidence_metadata": {},
                "retrieved_hits": [],
                "metrics": {"element_hit": 0.0},
                "performance": {},
            }
        ],
        backend_metadata={},
        skipped_routes=[
            {
                "route": "page_image_rag_vlm",
                "backend_status": "not_configured",
                "missing_backends": ["visual_generator"],
            }
        ],
        active_routes=[
            {"route_id": "page_image_rag_vlm"},
            {"route_id": "element_rag"},
        ],
    )

    assert summary["page_image"]["status"] == "blocked_backend"
    assert summary["page_image"]["missing_backends"] == ["visual_generator"]
    assert summary["element"]["status"] == "index_coverage_gap"
    assert summary["element"]["coverage_report"] == {
        "total_predictions": 1,
        "predictions_with_element_index": 0,
        "predictions_without_element_index": 1,
        "total_element_index_records": 0,
        "records_by_modality": {},
        "records_by_source": {},
        "missing_example_ids": ["ex-element-gap"],
    }


def test_phase3_summary_groups_hybrid_metrics_by_question_type():
    predictions = [
        {
            "route": "text_rag",
            "benchmark_role": "qa_quality",
            "question": "Which slide shows the architecture diagram?",
            "metrics": {"f1": 0.1, "native_score": 0.1, "page_hit": 0.0},
            "performance": {},
        },
        {
            "route": "hybrid_rag",
            "benchmark_role": "qa_quality",
            "question": "Which slide shows the architecture diagram?",
            "metrics": {"f1": 0.6, "native_score": 0.6, "page_hit": 1.0},
            "performance": {},
        },
        {
            "route": "hybrid_rag",
            "benchmark_role": "qa_quality",
            "question": "What revenue number is reported?",
            "metrics": {"f1": 0.3, "native_score": 0.3, "page_hit": 0.0},
            "performance": {},
        },
    ]

    summary = phase3_multimodal_summary("mixed", predictions)

    assert summary["hybrid"]["status"] == "question_type_breakdown_available"
    rows = summary["hybrid"]["question_type_route_metrics"]
    assert {
        "dataset_name": "mixed",
        "question_type": "visual_page",
        "route": "hybrid_rag",
        "count": 1,
        "avg_f1": 0.6,
        "avg_native_score": 0.6,
        "avg_page_hit": 1.0,
    } in rows
    assert {
        "dataset_name": "mixed",
        "question_type": "numeric",
        "route": "hybrid_rag",
        "count": 1,
        "avg_f1": 0.3,
        "avg_native_score": 0.3,
        "avg_page_hit": 0.0,
    } in rows


def test_phase3_report_sections_include_element_coverage_report():
    sections = dict(
        phase3_report_sections(
            {
                "phase3_multimodal_summary": {
                    "element": {
                        "coverage_report": {
                            "total_predictions": 2,
                            "predictions_with_element_index": 1,
                            "predictions_without_element_index": 1,
                            "total_element_index_records": 3,
                            "records_by_modality": {"figure": 1, "table": 2},
                            "records_by_source": {
                                "offline_layout_sidecar": 2,
                                "persisted_fixture": 1,
                            },
                            "missing_example_ids": ["ex-missing"],
                        }
                    }
                }
            }
        )
    )

    assert sections["Phase3 Element Coverage Report"] == [
        "- Total Predictions: `2`",
        "- Predictions With Element Index: `1`",
        "- Predictions Without Element Index: `1`",
        "- Total Element Index Records: `3`",
        "- Records By Modality: `figure=1`, `table=2`",
        "- Records By Source: `offline_layout_sidecar=2`, `persisted_fixture=1`",
        "- Missing Example IDs: `ex-missing`",
    ]


def test_rescored_summary_includes_phase3_multimodal_summary():
    rescored = add_mara_summary_fields(
        {"dataset_name": "slidevqa_test_shard0_multimodal"},
        [
            {
                "route": "page_image_rag_vlm",
                "benchmark_role": "qa_quality",
                "question": "Which figure is shown?",
                "evidence_metadata": {
                    "page_image_index": [
                        {"evidence_id": "page-image:doc:1", "modality": "page_image"}
                    ],
                },
                "retrieved_hits": [],
                "metrics": {"f1": 0.5, "page_hit": 1.0},
                "performance": {},
            }
        ],
    )

    assert rescored["phase3_multimodal_summary"]["page_image"]["status"] == (
        "vlm_route_observed"
    )
    assert rescored["phase3_multimodal_summary"]["hybrid"]["status"] == "not_evaluated"
