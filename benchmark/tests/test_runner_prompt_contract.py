import json

from benchmark.runner import run_benchmark
from benchmark.schemas import BenchmarkConfig


class _FakeEngine:
    def __init__(self, engine_name, config):
        self.engine_name = engine_name
        self.config = config

    def run_example(self, bundle, example):
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
        }


def test_run_benchmark_records_benchmark_prompt_contract(monkeypatch, tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "alce",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What is alpha?",
                        "answer_type": "citation_qa",
                        "answers": ["alpha"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "benchmark.runner.get_engine",
        lambda engine_name, config: _FakeEngine(engine_name, config),
    )

    report = run_benchmark(
        manifest_path,
        BenchmarkConfig(
            suite_name="prompt_contract",
            output_dir=tmp_path / "out",
            use_generation=False,
        ),
    )

    prediction = report["predictions"][0]
    assert prediction["question"] == "What is alpha?"
    assert prediction["benchmark_prompt_policy"] == "benchmark_v1"
    assert prediction["benchmark_prompt_profile"] == "citation_grounded_qa"
    assert prediction["benchmark_question"] == "What is alpha?"
    assert prediction["benchmark_retrieval_query"] == "What is alpha?"
    assert "Benchmark prompt contract:" in prediction["benchmark_runtime_prompt"]
    assert (
        "using only the provided search results"
        in prediction["benchmark_runtime_prompt"]
    )
    assert (
        "Answer formatting requirements:" not in prediction["benchmark_runtime_prompt"]
    )
    assert (
        "Return the final answer as Markdown"
        not in prediction["benchmark_runtime_prompt"]
    )
    assert (
        prediction["benchmark_prompt_source"]
        == "princeton-nlp/ALCE prompts/asqa_default.json"
    )
    assert report["summary"]["benchmark_prompt_policy"] == "benchmark_v1"
    assert report["summary"]["benchmark_prompt_profiles"] == {"citation_grounded_qa": 1}
