from benchmark.reports import write_reports


def test_write_reports_emits_route_metric_table_csv_and_markdown(tmp_path):
    run_dir = write_reports(_route_metric_report(), tmp_path, "Route Suite")

    route_metrics = (run_dir / "route_metrics.csv").read_text(encoding="utf-8")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "route_metrics.csv" in {path.name for path in run_dir.iterdir()}
    assert "dataset_name,route,num_predictions,avg_em,avg_f1,avg_mara_score" in (
        route_metrics
    )
    assert "sample,controller_auto,1,0.8,0.8,0.9" in route_metrics
    assert "## Route Metrics" in markdown
    assert "- Quality F1: `0.8`" in markdown
    assert "- MARA-Oriented Score: `0.9`" in markdown
    assert "## Quality Route Metrics" in markdown
    assert "## Diagnostic Route Metrics" in markdown
    assert "| sample | controller_auto | 1 | 0.8 | 0.9 | 1.0 | 0.0 | 0.5 |" in markdown
    assert "| sample | direct_answer | 1 | 0.1 | 0.2 | 0.0 | 0.0 | 0.1 |" in markdown
    assert "## Route Ranking" in markdown
    assert "1. `controller_auto` avg_f1=`0.8`" in markdown
    assert "1. `controller_auto` avg_mara_score=`0.9`" in markdown


def _route_metric_report():
    return {
        "summary": {
            "suite_name": "Route Suite",
            "dataset_name": "sample",
            "num_examples": 2,
            "num_documents": 1,
            "route_metric_table": [
                _route_row("text_rag", "qa_quality", 0.6, 0.7, 1.0, 0.2, 0.4),
                _route_row(
                    "controller_auto",
                    "qa_quality",
                    0.8,
                    0.9,
                    1.0,
                    0.0,
                    0.5,
                ),
            ],
            "quality_route_metric_table": [
                _route_row("controller_auto", "qa_quality", 0.8, 0.9, 1.0, 0.0, 0.5)
            ],
            "diagnostic_route_metric_table": [
                _route_row("direct_answer", "diagnostic", 0.1, 0.2, 0.0, 0.0, 0.1)
            ],
            "avg_mara_score": 0.9,
            "quality_avg_f1": 0.8,
            "quality_avg_mara_score": 0.9,
            "route_rankings": [_f1_ranking(), _mara_ranking()],
        },
        "predictions": [],
        "documents": [],
    }


def _route_row(route, role, score, mara_score, page_hit, unsupported_rate, seconds):
    return {
        "dataset_name": "sample",
        "route": route,
        "benchmark_role": role,
        "num_predictions": 1,
        "avg_em": score,
        "avg_f1": score,
        "avg_mara_score": mara_score,
        "avg_page_hit": page_hit,
        "avg_unsupported_claim_rate": unsupported_rate,
        "avg_total_seconds": seconds,
    }


def _f1_ranking():
    return {
        "dataset_name": "sample",
        "rank_metric": "avg_f1",
        "routes": [
            {"rank": 1, "route": "controller_auto", "score": 0.8},
            {"rank": 2, "route": "text_rag", "score": 0.6},
        ],
    }


def _mara_ranking():
    return {
        "dataset_name": "sample",
        "rank_metric": "avg_mara_score",
        "routes": [
            {"rank": 1, "route": "controller_auto", "score": 0.9},
            {"rank": 2, "route": "text_rag", "score": 0.7},
        ],
    }
