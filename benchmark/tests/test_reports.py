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
