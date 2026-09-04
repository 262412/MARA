import json
from time import monotonic

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _DeadlineCapturingEngine:
    def __init__(self):
        self.deadlines = []

    def set_route_deadline_monotonic(self, deadline):
        self.deadlines.append(deadline)

    def run_example(self, _bundle, example):
        return {
            "example_id": example.example_id,
            "document_id": example.document_id,
            "question": example.question,
            "gold_answers": example.answers,
            "gold_pages": example.evidence_pages,
            "gold_sources": example.evidence_sources,
            "predicted_answer": "alpha",
            "predicted_pages": [1],
            "predicted_sources": ["doc#page:1"],
            "predicted_element_ids": [],
            "retrieved_hits": [],
        }


def test_runner_creates_one_absolute_deadline_and_passes_it_to_engine(
    monkeypatch, tmp_path
):
    manifest_path = _write_manifest(tmp_path)
    engine = _DeadlineCapturingEngine()
    monkeypatch.setattr("benchmark.runner.get_engine", lambda *_args: engine)
    before = monotonic()

    run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="absolute_route_deadline",
            output_dir=tmp_path / "out",
            route_timeout_seconds=7.5,
            use_generation=False,
        ),
    )

    assert len(engine.deadlines) == 1
    assert before + 7.4 <= engine.deadlines[0] <= monotonic() + 7.5


def _write_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "single-route.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "timeout",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [{"route_id": "text_rag", "engine": "legacy_text_rag"}],
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
    return manifest_path
