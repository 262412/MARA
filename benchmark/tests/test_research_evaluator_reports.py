from benchmark.reports import write_reports


def test_write_reports_lists_external_research_evaluator_status(tmp_path):
    report = {
        "summary": {
            "suite_name": "Evaluator Suite",
            "dataset_name": "research",
            "num_examples": 1,
            "num_documents": 1,
            "external_adapter_metric_metadata": {
                "alce": {
                    "status": "configured",
                    "backend": "tests.fixture_alce",
                    "paper_grade": True,
                },
                "mmdocrag": {
                    "status": "not_configured",
                    "requires_external_resources": ["MMDocRAG dataset"],
                    "excluded_from_summary": True,
                },
            },
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Evaluator Suite")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")

    assert "## External Research Evaluators" in markdown
    assert "- `alce`: configured via `tests.fixture_alce`, paper_grade=`True`" in (
        markdown
    )
    assert "- `mmdocrag`: not_configured, excluded_from_summary=`True`" in markdown
