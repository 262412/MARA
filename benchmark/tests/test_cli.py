import sys
import types

from benchmark.cli import main


def _empty_report(config):
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


def _run_args(manifest_path):
    return [
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
        "--reasoning",
        "mara",
        "--agent-mode",
        "thorough",
        "--task-type",
        "quiz",
        "--artifact-type",
        "quiz",
        "--artifact-detail",
        "full",
        "--limit",
        "25",
        "--sample-seed",
        "1234",
        "--shard-index",
        "1",
        "--num-shards",
        "4",
    ]


def test_run_cli_writes_v2_route_options_into_config(monkeypatch, tmp_path):
    captured = {}

    def fake_run_benchmark(manifest_path, config):
        captured["manifest_path"] = manifest_path
        captured["config"] = config
        return _empty_report(config)

    def fake_write_reports(report, output_dir, suite_name, *, artifact_detail):
        captured["report"] = report
        captured["artifact_detail"] = artifact_detail
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

    exit_code = main(_run_args(manifest_path))

    assert exit_code == 0
    assert captured["config"].engine == "direct_paste"
    assert captured["config"].scope == "multi_document"
    assert captured["config"].route == "table"
    assert captured["config"].cost_profile == "low-cost"
    assert captured["config"].llm_name == "Deepseek"
    assert captured["config"].docqa_citation_mode == "off"
    assert captured["config"].reasoning_type == "mara"
    assert captured["config"].agent_mode == "thorough"
    assert captured["config"].task_type == "quiz"
    assert captured["config"].artifact_type == "quiz"
    assert captured["config"].artifact_detail == "full"
    assert captured["artifact_detail"] == "full"
    assert captured["config"].limit == 25
    assert captured["config"].sample_seed == 1234
    assert captured["config"].shard_index == 1
    assert captured["config"].num_shards == 4
