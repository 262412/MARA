from benchmark.reports import write_reports
from benchmark.summary import add_mara_summary_fields


def test_write_reports_emits_route_metric_table_csv_and_markdown(tmp_path):
    run_dir = write_reports(_route_metric_report(), tmp_path, "Route Suite")

    route_metrics = (run_dir / "route_metrics.csv").read_text(encoding="utf-8")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "route_metrics.csv" in {path.name for path in run_dir.iterdir()}
    assert "avg_citation_metadata_recall,avg_citation_metadata_precision" in (
        route_metrics
    )
    assert "avg_citation_inline_recall,avg_citation_inline_precision" in (route_metrics)
    assert "dataset_name,route,num_predictions,avg_mara_score" in route_metrics
    assert (
        "avg_mara_score,avg_native_score,avg_mara_proxy_score,avg_em,avg_f1"
        in route_metrics
    )
    assert "sample,controller_auto,1,0.9,0.9,0.72,0.8,0.8" in route_metrics
    assert "## Route Metrics" in markdown
    assert "- Primary Score: `0.9`" in markdown
    assert "- Primary Score Metric: `quality_avg_mara_score`" in markdown
    assert "- Primary Score Scope: `qa_quality`" in markdown
    assert "- MARA Native Score: `0.9`" in markdown
    assert "- MARA Proxy Score: `0.72`" in markdown
    assert "- Diagnostic F1: `None`" in markdown
    assert "- Quality Diagnostic F1: `0.8`" in markdown
    assert "- Citation Metadata Recall: `0.8`" in markdown
    assert "- Citation Inline Recall: `0.4`" in markdown
    assert "## Quality Route Metrics" in markdown
    assert "## Diagnostic Route Metrics" in markdown
    assert (
        "| sample | controller_auto | 1 | 0.9 | 0.72 | 0.8 | 1.0 | 0.8 / 0.7 | "
        "0.4 / 0.3 | 0.0 | 0.5 |"
    ) in markdown
    assert (
        "| sample | direct_answer | 1 | 0.2 | 0.16 | 0.1 | 0.0 | 0.8 / 0.7 | "
        "0.4 / 0.3 | 0.0 | 0.1 |"
    ) in markdown
    assert "## Route Ranking" in markdown
    assert "1. `controller_auto` avg_mara_score=`0.9`" in markdown
    assert "1. `controller_auto` avg_f1=`0.8`" in markdown
    assert markdown.index("avg_mara_score=`0.9`") < markdown.index("avg_f1=`0.8`")


def test_add_mara_summary_fields_preserves_citation_split_summaries():
    summary = {"dataset_name": "sample"}
    predictions = [
        {
            "benchmark_role": "qa_quality",
            "route": "text_rag",
            "metrics": {
                "citation_metadata_recall": 0.5,
                "citation_metadata_precision": 0.25,
                "citation_inline_recall": 1.0,
                "citation_inline_precision": 1.0,
            },
            "performance": {},
        }
    ]

    rescored = add_mara_summary_fields(summary, predictions)

    assert rescored["avg_citation_metadata_recall"] == 0.5
    assert rescored["avg_citation_metadata_precision"] == 0.25
    assert rescored["avg_citation_inline_recall"] == 1.0
    assert rescored["avg_citation_inline_precision"] == 1.0


def test_add_mara_summary_fields_reports_prediction_level_native_contract():
    summary = {"dataset_name": "alce"}
    predictions = [
        {
            "mara_scoring_contract": "alce_qampari_f1_v1",
            "mara_primary_metric": "qampari_f1",
            "metrics": {"mara_score": 0.4444, "native_score": 0.4444},
            "performance": {},
        }
    ]

    rescored = add_mara_summary_fields(summary, predictions)

    assert rescored["mara_score_metadata"]["contracts"] == {"alce_qampari_f1_v1": 1}
    assert rescored["mara_score_metadata"]["primary_metrics"] == {"qampari_f1": 1}
    assert rescored["mara_score_metadata"]["paper_grade"] is False
    assert rescored["mara_score_metadata"]["scoring_mode"] == "dataset_native_v1"


def test_add_mara_summary_fields_surfaces_dataset_native_detail_metrics():
    summary = {"dataset_name": "qasper"}
    predictions = [
        {
            "route": "text_rag",
            "mara_native_metrics": ["qasper_f1", "qasper_evidence_f1"],
            "metrics": {
                "qasper_f1": 0.75,
                "qasper_evidence_f1": 0.5,
                "mara_score": 0.75,
                "native_score": 0.75,
            },
            "performance": {},
        }
    ]

    rescored = add_mara_summary_fields(summary, predictions)

    assert rescored["avg_qasper_f1"] == 0.75
    assert rescored["avg_qasper_evidence_f1"] == 0.5
    assert rescored["route_metric_table"][0]["avg_qasper_f1"] == 0.75
    assert rescored["route_metric_table"][0]["avg_qasper_evidence_f1"] == 0.5


def test_primary_score_uses_quality_routes_not_diagnostic_routes():
    summary = {"dataset_name": "sample"}
    predictions = [
        {
            "benchmark_role": "qa_quality",
            "route": "controller_auto",
            "metrics": {
                "mara_score": 0.9,
                "native_score": 0.9,
                "mara_proxy_score": 0.8,
            },
            "performance": {},
        },
        {
            "benchmark_role": "diagnostic",
            "route": "direct_answer",
            "metrics": {
                "mara_score": 0.1,
                "native_score": 0.1,
                "mara_proxy_score": 0.1,
            },
            "performance": {},
        },
    ]

    rescored = add_mara_summary_fields(summary, predictions)

    assert rescored["avg_mara_score"] == 0.5
    assert rescored["quality_avg_mara_score"] == 0.9
    assert rescored["primary_score_metric"] == "quality_avg_mara_score"
    assert rescored["primary_score_scope"] == "qa_quality"
    assert rescored["primary_score"] == 0.9


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
            "avg_native_score": 0.9,
            "avg_mara_proxy_score": 0.72,
            "primary_score": 0.9,
            "primary_score_metric": "quality_avg_mara_score",
            "primary_score_scope": "qa_quality",
            "quality_avg_f1": 0.8,
            "quality_avg_mara_score": 0.9,
            "quality_avg_native_score": 0.9,
            "quality_avg_mara_proxy_score": 0.72,
            "avg_citation_metadata_recall": 0.8,
            "avg_citation_inline_recall": 0.4,
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
        "avg_native_score": mara_score,
        "avg_mara_proxy_score": round(mara_score * 0.8, 2),
        "avg_citation_metadata_recall": 0.8,
        "avg_citation_metadata_precision": 0.7,
        "avg_citation_inline_recall": 0.4,
        "avg_citation_inline_precision": 0.3,
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
