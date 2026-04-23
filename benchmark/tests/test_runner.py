import json
from types import SimpleNamespace

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _FakeEngine:
    def __init__(self, engine_name, config, calls):
        self.engine_name = engine_name
        self.config = config
        self.calls = calls

    def run_example(self, bundle, example):
        self.calls.append((self.engine_name, self.config.route, example.example_id))
        document_ids = example.document_ids or [example.document_id]
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": f"{self.engine_name}:{self.config.route}",
            "predicted_pages": [1],
            "predicted_sources": [f"{document_ids[0]}#page:1"],
            "predicted_element_ids": [],
            "retrieved_hits": [
                {
                    "doc_id": "hit-1",
                    "document_id": document_ids[0],
                    "page_label": "1",
                    "score": 1.0,
                }
            ],
            "retrieval_trace": {
                "route": self.config.route,
                "engine": self.engine_name,
                "retrieved_elements": ["hit-1"],
            },
            "timings": {
                "parse_seconds": 0.0,
                "index_seconds": 0.0,
                "retrieval_seconds": 0.01,
                "generation_seconds": 0.02,
            },
            "context_preview": "context",
        }

    def document_reports(self):
        return [{"engine": self.engine_name, "route": self.config.route}]


def test_run_benchmark_expands_manifest_route_matrix(monkeypatch, tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "routes",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {
                        "route_id": "page_fast",
                        "engine": "legacy_text_rag",
                        "scope": "page",
                        "retrieval_mode": "text",
                    },
                    {
                        "route_id": "direct",
                        "engine": "direct_paste",
                        "scope": "document",
                    },
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "scope": "page",
                        "question": "What is alpha?",
                        "answers": ["alpha"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    calls = []

    def fake_get_engine(engine_name, config):
        return _FakeEngine(engine_name, config, calls)

    monkeypatch.setattr("benchmark.runner.get_engine", fake_get_engine)

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="routes",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    assert calls == [
        ("legacy_text_rag", "page_fast", "ex"),
        ("direct_paste", "direct", "ex"),
    ]
    assert [item["route"] for item in report["predictions"]] == ["page_fast", "direct"]
    assert [item["engine"] for item in report["predictions"]] == [
        "legacy_text_rag",
        "direct_paste",
    ]
    assert report["summary"]["num_routes"] == 2
    assert len(report["retrieval_traces"]) == 2


def test_run_benchmark_filters_manifest_route_by_id(monkeypatch, tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {"route_id": "skip", "engine": "legacy_text_rag"},
                    {"route_id": "keep", "engine": "oracle_page"},
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What is alpha?",
                        "answers": ["alpha"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    calls = []

    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _FakeEngine(engine_name, config, calls),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="routes",
            output_dir=tmp_path / "out",
            route="keep",
            use_generation=False,
        ),
    )

    assert calls == [("oracle_page", "keep", "ex")]
    assert len(report["predictions"]) == 1
    assert report["predictions"][0]["route"] == "keep"


def test_run_benchmark_handles_empty_manifest(tmp_path):
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"schema_version": 2, "documents": [], "examples": []}),
        encoding="utf-8",
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="empty",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    assert report["summary"]["num_examples"] == 0
    assert report["summary"]["avg_em"] is None
    assert report["predictions"] == []
    assert report["retrieval_traces"] == []
