from benchmark.reports import write_reports


def _diagnostics_report():
    return {
        "summary": {
            "suite_name": "Diagnostics Suite",
            "dataset_name": "qasper",
            "num_examples": 1,
            "num_documents": 1,
            **_generic_diagnostics_summary(),
            **_taxonomy_summary(),
            **_verifier_summary(),
        },
        "predictions": [],
        "documents": [],
    }


def _generic_diagnostics_summary():
    return {
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
    }


def _taxonomy_summary():
    return {
        "failure_taxonomy_counts": [
            {
                "dataset_name": "qasper",
                "failure_taxonomy": "bad_citation",
                "count": 1,
                "unit": "prediction",
            }
        ],
        "failure_taxonomy_by_route": [
            {
                "dataset_name": "qasper",
                "route": "controller_auto",
                "routing_taxonomy": "controller",
                "failure_taxonomy": "bad_citation",
                "count": 1,
                "unit": "prediction",
            }
        ],
        "routing_taxonomy_counts": [
            {
                "dataset_name": "qasper",
                "routing_taxonomy": "controller",
                "count": 1,
            }
        ],
    }


def _verifier_summary():
    return {
        "verifier_observability_by_route": [
            {
                "dataset_name": "qasper",
                "route": "crag_guarded",
                "num_predictions": 2,
                "num_true_abstention": 1,
                "num_false_abstention": 1,
                "num_unsupported_claim": 1,
                "total_unsupported_claim_count": 3,
                "num_retry": 2,
                "total_retry_count": 4,
                "num_route_switch": 1,
                "total_route_switch_count": 1,
                "true_abstention_rate": 0.5,
                "false_abstention_rate": 0.5,
                "unsupported_claim_rate": 0.5,
                "retry_rate": 1.0,
                "route_switch_rate": 0.5,
            }
        ],
    }


def test_write_reports_includes_generic_diagnostic_tables(tmp_path):
    run_dir = write_reports(_diagnostics_report(), tmp_path, "Diagnostics Suite")

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
    assert "## Verifier Observability" in markdown
    assert "| qasper | crag_guarded | 2 | 1 | 1 | 1 | 3 | 2 | 4 | 1 | 1 |" in markdown


def test_write_reports_includes_failure_and_routing_taxonomy(tmp_path):
    run_dir = write_reports(_diagnostics_report(), tmp_path, "Diagnostics Suite")

    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "## Failure Taxonomy" in markdown
    assert "| qasper | bad_citation | prediction | 1 |" in markdown
    assert "## Failure Taxonomy By Route" in markdown
    assert (
        "| qasper | controller_auto | controller | bad_citation | prediction | 1 |"
        in (markdown)
    )
    assert "## Routing Taxonomy" in markdown
    assert "| qasper | controller | 1 |" in markdown
