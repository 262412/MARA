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
                    "metric_category": "paper_grade_metric",
                },
                "mmdocrag": {
                    "status": "not_configured",
                    "requires_external_resources": ["MMDocRAG dataset"],
                    "excluded_from_summary": True,
                    "metric_category": "external_metric",
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
    assert "metric_category=`paper_grade_metric`" in markdown
    assert "- `mmdocrag`: not_configured, excluded_from_summary=`True`" in markdown


def test_write_reports_lists_external_research_evaluator_status_by_route(tmp_path):
    report = {
        "summary": {
            "suite_name": "External Matrix",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "external_adapter_metric_metadata_by_route": {
                "paper": {
                    "alce": {
                        "status": "configured",
                        "backend": "tests.fixture_alce",
                        "paper_grade": True,
                        "metric_category": "paper_grade_metric",
                    }
                },
                "proxy_only": {
                    "alce": {
                        "status": "not_configured",
                        "excluded_from_summary": True,
                        "metric_category": "external_metric",
                    }
                },
            },
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "External Matrix")

    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## External Research Evaluators By Route" in markdown
    assert (
        "- `paper` / `alce`: configured via `tests.fixture_alce`, paper_grade=`True`"
        in markdown
    )
    assert "metric_category=`paper_grade_metric`" in markdown
    assert (
        "- `proxy_only` / `alce`: not_configured, excluded_from_summary=`True`"
        in markdown
    )
