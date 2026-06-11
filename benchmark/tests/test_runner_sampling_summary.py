import json

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _FakeEngine:
    def __init__(self, engine_name, config, calls):
        self.engine_name = engine_name
        self.config = config
        self.calls = calls

    def run_example(self, bundle, example):
        self.calls.append((self.engine_name, self.config.route, example.example_id))
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": f"{self.engine_name}:{self.config.route}",
            "predicted_pages": [1],
            "predicted_sources": ["doc#page:1"],
            "predicted_element_ids": [],
            "retrieved_hits": [],
            "timings": {
                "parse_seconds": 0.1,
                "index_seconds": 0.2,
                "retrieval_seconds": 0.01,
                "generation_seconds": 0.02,
            },
        }


def test_run_benchmark_applies_seeded_limit_and_sharding(monkeypatch, tmp_path):
    manifest_path = _write_sampling_manifest(tmp_path)
    calls: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _FakeEngine(engine_name, config, calls),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="sampled",
            output_dir=tmp_path / "out",
            sample_seed=7,
            shard_index=1,
            num_shards=2,
            limit=2,
            use_generation=False,
        ),
    )

    assert [call[2] for call in calls] == ["ex-7", "ex-4"]
    assert [item["example_id"] for item in report["predictions"]] == ["ex-7", "ex-4"]
    assert report["summary"]["num_manifest_examples"] == 8
    assert report["summary"]["num_examples"] == 2
    assert report["summary"]["selection"] == {
        "limit": 2,
        "sample_seed": 7,
        "shard_index": 1,
        "num_shards": 2,
    }


def test_run_benchmark_summarizes_metrics_by_route(monkeypatch, tmp_path):
    manifest_path = _write_route_summary_manifest(tmp_path)
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _FakeEngine(engine_name, config, []),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="routes",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    metric_rows = report["summary"]["route_metric_table"]
    assert [row["route"] for row in metric_rows] == ["text_rag", "controller_auto"]
    assert all(row["dataset_name"] == "routes" for row in metric_rows)
    assert all(row["num_predictions"] == 1 for row in metric_rows)
    assert metric_rows[0]["avg_em"] == 0.0
    assert metric_rows[1]["avg_em"] == 1.0
    assert metric_rows[1]["avg_f1"] > metric_rows[0]["avg_f1"]
    assert metric_rows[0]["avg_total_seconds"] == 0.33
    assert metric_rows[1]["avg_total_seconds"] == 0.33
    assert {
        "avg_page_hit",
        "avg_citation_recall",
        "avg_citation_precision",
        "avg_unsupported_claim_rate",
        "avg_abstention_rate",
        "avg_multimodal_answer_support",
    } <= set(metric_rows[0])
    ranking = report["summary"]["route_rankings"][0]
    assert ranking["dataset_name"] == "routes"
    assert ranking["rank_metric"] == "avg_f1"
    assert ranking["routes"][0] == {
        "rank": 1,
        "route": "controller_auto",
        "score": 1.0,
    }
    assert ranking["routes"][1]["rank"] == 2
    assert ranking["routes"][1]["route"] == "text_rag"
    assert ranking["routes"][1]["score"] == metric_rows[0]["avg_f1"]


def _write_sampling_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "sampling.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "sampled",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [{"route_id": "text", "engine": "legacy_text_rag"}],
                "examples": [
                    {
                        "example_id": f"ex-{index}",
                        "document_id": "doc",
                        "question": f"Question {index}?",
                        "answers": ["alpha"],
                    }
                    for index in range(8)
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path


def _write_route_summary_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "route-summary.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "routes",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {"route_id": "text_rag", "engine": "legacy_text_rag"},
                    {"route_id": "controller_auto", "engine": "legacy_text_rag"},
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What is alpha?",
                        "answers": ["legacy_text_rag:controller_auto"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest_path
