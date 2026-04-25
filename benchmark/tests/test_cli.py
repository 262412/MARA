import sys
import types

from benchmark.cli import main


def test_run_cli_writes_v2_route_options_into_config(monkeypatch, tmp_path):
    captured = {}

    def fake_run_benchmark(manifest_path, config):
        captured["manifest_path"] = manifest_path
        captured["config"] = config
        return {
            "summary": {
                "suite_name": config.suite_name,
                "dataset_name": "suite",
                "num_examples": 0,
                "num_documents": 0,
                "avg_em": None,
                "avg_f1": None,
                "avg_anls": None,
                "avg_page_hit": None,
                "avg_citation_recall": None,
                "avg_retrieval_seconds": None,
                "avg_generation_seconds": None,
            },
            "documents": [],
            "predictions": [],
        }

    def fake_write_reports(report, output_dir, suite_name):
        captured["report"] = report
        return tmp_path / "run"

    monkeypatch.setitem(
        sys.modules,
        "benchmark.runner",
        types.SimpleNamespace(run_benchmark=fake_run_benchmark),
    )
    monkeypatch.setitem(
        sys.modules,
        "benchmark.reports",
        types.SimpleNamespace(write_reports=fake_write_reports),
    )

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"examples": []}', encoding="utf-8")

    exit_code = main(
        [
            "run",
            "--manifest",
            str(manifest_path),
            "--engine",
            "direct_paste",
            "--scope",
            "multi-document",
            "--route",
            "table",
            "--cost-profile",
            "low-cost",
            "--llm-name",
            "Deepseek",
            "--docqa-citation-mode",
            "off",
        ]
    )

    assert exit_code == 0
    assert captured["config"].engine == "direct_paste"
    assert captured["config"].scope == "multi_document"
    assert captured["config"].route == "table"
    assert captured["config"].cost_profile == "low-cost"
    assert captured["config"].llm_name == "Deepseek"
    assert captured["config"].docqa_citation_mode == "off"
