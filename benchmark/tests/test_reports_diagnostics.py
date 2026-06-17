from benchmark.reports import write_reports


def test_write_reports_includes_generic_diagnostic_tables(tmp_path):
    report = {
        "summary": {
            "suite_name": "Diagnostics Suite",
            "dataset_name": "qasper",
            "num_examples": 1,
            "num_documents": 1,
            "dataset_route_diagnostics": [
                {
                    "dataset_name": "qasper",
                    "route": "controller_auto",
                    "num_predictions": 1,
                    "avg_retrieved_count": 1.0,
                    "avg_evidence_item_count": 1.0,
                    "avg_gold_document_hit": 1.0,
                    "avg_gold_page_hit": 1.0,
                    "avg_gold_span_hit": 1.0,
                    "avg_answer_nonempty_after_cleaning": 1.0,
                }
            ],
            "route_confusion_table": [
                {
                    "dataset_name": "qasper",
                    "route": "controller_auto",
                    "recommended_route": "doc_text",
                    "selected_route": "doc_text",
                    "count": 1,
                }
            ],
            "diagnostic_failure_counts": [
                {
                    "dataset_name": "qasper",
                    "route": "controller_auto",
                    "failure_class": "wrong_locator",
                    "retrieval_failure_type": "wrong_page",
                    "citation_failure_type": "citation_miss",
                    "count": 1,
                }
            ],
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Diagnostics Suite")

    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## Generic Route Diagnostics" in markdown
    assert "| qasper | controller_auto | 1 | 1.0 | 1.0 | 1.0 | 1.0 |" in markdown
    assert "## Route Confusion" in markdown
    assert "| qasper | controller_auto | doc_text | doc_text | 1 |" in markdown
    assert "## Diagnostic Failure Counts" in markdown
    assert (
        "| qasper | controller_auto | wrong_locator | wrong_page | "
        "citation_miss | 1 |"
    ) in markdown
