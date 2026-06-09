from ktem.docqa.artifact_evaluation import (
    evaluate_artifact,
    evaluate_artifact_collection,
)


def test_evaluate_artifact_reports_proxy_metrics_without_paper_grade_claims():
    report = evaluate_artifact(
        {
            "artifact_id": "artifact-1",
            "type": "briefing_doc",
            "title": "Launch briefing",
            "status": "ready",
            "source_scope": {
                "mode": "multi-document",
                "source_ids": ["file-1", "file-2"],
            },
            "payload": {
                "sections": [
                    {
                        "title": "Finding",
                        "summary": "Source-grounded evidence.",
                        "source_ids": ["file-1"],
                    }
                ]
            },
            "citations": [
                {"citation_id": "c1", "source_id": "file-1", "page_label": "3"}
            ],
            "exports": [{"format": "md", "path": "briefing.md"}],
            "generation": {
                "adapter": "schema_builder",
                "parameters": {"latency_seconds": 1.25},
            },
        }
    )

    assert report["artifact"] == {
        "artifact_id": "artifact-1",
        "type": "briefing_doc",
        "title": "Launch briefing",
        "status": "ready",
    }
    assert report["document_scope"] == {
        "mode": "multi-document",
        "source_count": 2,
        "citation_count": 1,
        "cited_source_count": 1,
        "export_count": 1,
    }
    assert report["metric_tiers"]["proxy_metric"] == {
        "citation_coverage": 0.5,
        "groundedness_proxy": 1.0,
        "artifact_usefulness_proxy": 1.0,
        "latency_seconds": 1.25,
    }
    assert report["metric_tiers"]["external_metric"]["status"] == "not_configured"
    assert report["metric_tiers"]["paper_grade_metric"]["status"] == "not_claimed"


def test_evaluate_artifact_collection_reports_source_format_summary():
    report = evaluate_artifact_collection(
        [
            {
                "artifact_id": "artifact-1",
                "type": "briefing_doc",
                "title": "Briefing",
                "status": "ready",
                "source_scope": {
                    "mode": "multi-document",
                    "source_ids": ["pdf-1", "pptx-1"],
                },
                "payload": {"sections": [{"summary": "Grounded."}]},
                "citations": [
                    {
                        "citation_id": "c1",
                        "source_id": "pdf-1",
                        "source_name": "report.pdf",
                    },
                    {
                        "citation_id": "c2",
                        "source_id": "pptx-1",
                        "source_name": "slides.pptx",
                    },
                ],
                "generation": {"parameters": {"latency_seconds": 2.0}},
            },
            {
                "artifact_id": "artifact-2",
                "type": "study_guide",
                "title": "Study Guide",
                "status": "ready",
                "source_scope": {
                    "mode": "multi-document",
                    "source_ids": ["docx-1", "image-1"],
                },
                "payload": {"overview": "Grounded overview."},
                "citations": [
                    {
                        "citation_id": "c3",
                        "source_id": "docx-1",
                        "source_name": "brief.docx",
                    },
                    {
                        "citation_id": "c4",
                        "source_id": "image-1",
                        "source_name": "figure.png",
                    },
                ],
                "generation": {"parameters": {"latency_seconds": 4.0}},
            },
        ]
    )

    assert report["artifact_count"] == 2
    assert report["source_format_summary"] == {
        "docx": {"artifact_count": 1, "citation_count": 1, "source_count": 1},
        "image": {"artifact_count": 1, "citation_count": 1, "source_count": 1},
        "pdf": {"artifact_count": 1, "citation_count": 1, "source_count": 1},
        "pptx": {"artifact_count": 1, "citation_count": 1, "source_count": 1},
    }
    proxy = report["metric_tiers"]["proxy_metric"]
    assert proxy["mean_citation_coverage"] == 1.0
    assert proxy["mean_groundedness_proxy"] == 1.0
    assert proxy["mean_artifact_usefulness_proxy"] == 1.0
    assert proxy["mean_latency_seconds"] == 3.0
    assert report["metric_tiers"]["external_metric"]["status"] == "not_configured"
    assert report["metric_tiers"]["paper_grade_metric"]["status"] == "not_claimed"
