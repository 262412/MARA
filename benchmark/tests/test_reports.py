from __future__ import annotations

import json

from benchmark.reports import write_reports


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_write_reports_emits_required_artifacts_with_jsonl_and_route_metadata(tmp_path):
    report = {
        "summary": {
            "suite_name": "Phase 2 Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "avg_em": 1.0,
            "avg_f1": 1.0,
            "avg_anls": 1.0,
            "avg_page_hit": 1.0,
            "avg_citation_recall": 1.0,
            "avg_abstention_rate": 0.0,
            "avg_false_abstention": 0.0,
            "avg_markdown_table_renderable": 1.0,
            "avg_latex_renderable": 1.0,
            "avg_rewrite_skipped": 1.0,
            "avg_guardrail_expectation_match": 1.0,
            "avg_retrieval_seconds": 0.2,
            "avg_generation_seconds": 0.4,
            "engine": "local",
            "route": "hybrid",
            "scope": "smoke",
        },
        "config": {
            "engine": "config-engine",
            "route": "config-route",
            "scope": "config-scope",
        },
        "predictions": [
            {"example_id": "ex-1", "prediction": "42"},
        ],
        "documents": [{"document_id": "doc-1", "path": "doc.pdf"}],
        "retrieval_traces": [
            {"example_id": "ex-1", "hits": [{"document_id": "doc-1", "page": 3}]}
        ],
    }

    run_dir = write_reports(report, tmp_path, "Phase 2 Suite")

    assert sorted(path.name for path in run_dir.iterdir()) == [
        "documents.json",
        "predictions.jsonl",
        "report.md",
        "retrieval_traces.jsonl",
        "summary.json",
    ]
    assert (
        json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        == report["summary"]
    )
    assert _read_jsonl(run_dir / "predictions.jsonl") == report["predictions"]
    assert (
        json.loads((run_dir / "documents.json").read_text(encoding="utf-8"))
        == report["documents"]
    )
    assert _read_jsonl(run_dir / "retrieval_traces.jsonl") == report["retrieval_traces"]

    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "predictions.jsonl" in markdown
    assert "retrieval_traces.jsonl" in markdown
    assert "documents.json" in markdown
    assert "- Engine: `local`" in markdown
    assert "- Route: `hybrid`" in markdown
    assert "- Scope: `smoke`" in markdown
    assert "- False Abstention: `0.0`" in markdown
    assert "- Markdown Table Renderable: `1.0`" in markdown
    assert "- LaTeX Renderable: `1.0`" in markdown
    assert "- Guardrail Expectation Match: `1.0`" in markdown


def test_write_reports_lists_skipped_routes(tmp_path):
    report = {
        "summary": {
            "suite_name": "Skip Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "num_executed_routes": 1,
            "num_skipped_routes": 1,
            "skipped_routes": [
                {
                    "route_id": "page_image_rag_vlm",
                    "skip_reason": "not_configured: colpali, visual_generator",
                }
            ],
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Skip Suite")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")

    assert "- Executed Routes: `1`" in markdown
    assert "- Skipped Routes: `1`" in markdown
    assert (
        "- `page_image_rag_vlm`: not_configured: colpali, visual_generator" in markdown
    )


def test_write_reports_lists_backend_status_by_route(tmp_path):
    report = {
        "summary": {
            "suite_name": "Backend Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "backend_metadata": {
                "text_rag": {
                    "text_retriever": "docqa_text",
                    "generator_backend": "local_docqa_generator",
                },
                "page_image_rag_vlm": {
                    "backend_status": "not_configured",
                    "visual_retriever": "local_late_interaction",
                    "visual_generator": "evidence_only_without_vlm",
                },
            },
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Backend Suite")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")

    assert "## Backend Status By Route" in markdown
    assert (
        "- `text_rag`: configured; generator_backend=`local_docqa_generator`, text_retriever=`docqa_text`"
        in markdown
    )
    assert (
        "- `page_image_rag_vlm`: not_configured; visual_generator=`evidence_only_without_vlm`, visual_retriever=`local_late_interaction`"
        in markdown
    )


def test_write_reports_derives_minimal_traces_from_predictions_when_missing(tmp_path):
    report = {
        "summary": {
            "suite_name": "Compat Suite",
            "dataset_name": "sample",
            "num_examples": 2,
            "num_documents": 1,
            "avg_em": 0.0,
            "avg_f1": 0.0,
            "avg_anls": 0.0,
            "avg_page_hit": 0.0,
            "avg_citation_recall": 0.0,
            "avg_retrieval_seconds": 0.0,
            "avg_generation_seconds": 0.0,
        },
        "predictions": [
            {
                "example_id": "with-hits",
                "prediction": "alpha",
                "retrieved_hits": [{"document_id": "doc-1", "score": 0.9}],
            },
            {
                "example_id": "with-trace",
                "prediction": "beta",
                "retrieval_trace": {"hits": [{"document_id": "doc-2"}]},
                "agent_trace": [{"stage": "planner", "decision": "retrieve"}],
                "evidence_metadata": {"has_table_evidence": True},
                "claim_verification": {"abstained": False},
            },
        ],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Compat Suite")

    assert _read_jsonl(run_dir / "predictions.jsonl") == report["predictions"]
    assert _read_jsonl(run_dir / "retrieval_traces.jsonl") == [
        {
            "example_id": "with-hits",
            "retrieved_hits": [{"document_id": "doc-1", "score": 0.9}],
        },
        {
            "example_id": "with-trace",
            "retrieval_trace": {"hits": [{"document_id": "doc-2"}]},
            "agent_trace": [{"stage": "planner", "decision": "retrieve"}],
            "evidence_metadata": {"has_table_evidence": True},
            "claim_verification": {"abstained": False},
        },
    ]


def test_write_reports_includes_multimodal_summary_metrics(tmp_path):
    report = {
        "summary": {
            "suite_name": "MARA Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "avg_em": 0.0,
            "avg_f1": 0.0,
            "avg_anls": 0.0,
            "avg_page_hit": 0.0,
            "avg_citation_recall": 0.0,
            "avg_table_hit": 1.0,
            "avg_figure_hit": 0.5,
            "avg_formula_hit": 1.0,
            "avg_slide_hit": 0.0,
            "avg_retrieval_seconds": 0.0,
            "avg_generation_seconds": 0.0,
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "MARA Suite")

    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "- Table Hit: `1.0`" in markdown
    assert "- Figure Hit: `0.5`" in markdown
    assert "- Formula Hit: `1.0`" in markdown
    assert "- Slide Hit: `0.0`" in markdown


def test_write_reports_emits_route_metric_table_csv_and_markdown(tmp_path):
    report = {
        "summary": {
            "suite_name": "Route Suite",
            "dataset_name": "sample",
            "num_examples": 2,
            "num_documents": 1,
            "route_metric_table": [
                {
                    "dataset_name": "sample",
                    "route": "text_rag",
                    "num_predictions": 1,
                    "avg_f1": 0.6,
                    "avg_page_hit": 1.0,
                    "avg_unsupported_claim_rate": 0.2,
                    "avg_total_seconds": 0.4,
                },
                {
                    "dataset_name": "sample",
                    "route": "controller_auto",
                    "num_predictions": 1,
                    "avg_f1": 0.8,
                    "avg_page_hit": 1.0,
                    "avg_unsupported_claim_rate": 0.0,
                    "avg_total_seconds": 0.5,
                },
            ],
            "route_rankings": [
                {
                    "dataset_name": "sample",
                    "rank_metric": "avg_f1",
                    "routes": [
                        {"rank": 1, "route": "controller_auto", "score": 0.8},
                        {"rank": 2, "route": "text_rag", "score": 0.6},
                    ],
                }
            ],
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Route Suite")

    route_metrics = (run_dir / "route_metrics.csv").read_text(encoding="utf-8")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "route_metrics.csv" in {path.name for path in run_dir.iterdir()}
    assert "dataset_name,route,num_predictions,avg_f1" in route_metrics
    assert "sample,controller_auto,1,0.8" in route_metrics
    assert "## Route Metrics" in markdown
    assert "| sample | controller_auto | 1 | 0.8 | 1.0 | 0.0 | 0.5 |" in markdown
    assert "## Route Ranking" in markdown
    assert "1. `controller_auto` avg_f1=`0.8`" in markdown
