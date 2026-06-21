from types import SimpleNamespace

from benchmark.engines import DocQARuntimeEngine
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample


def test_docqa_runtime_engine_sends_selected_short_text_to_runtime_request(tmp_path):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text(
        "The short source text should reach generation.", encoding="utf-8"
    )
    engine = DocQARuntimeEngine(
        BenchmarkConfig(suite_name="runtime", output_dir=tmp_path / "out")
    )

    kwargs = engine._docqa_request_kwargs(
        example=BenchmarkExample(
            example_id="ex",
            document_id="doc",
            question="Question?",
            answers=["runtime answer"],
        ),
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt")
        ],
        selected_file_ids=["file-1"],
        active_record=SimpleNamespace(file_id="file-1", name="doc.txt"),
    )

    assert kwargs["selected_text"] == "The short source text should reach generation."


def test_docqa_runtime_engine_uses_benchmark_prompt_contract(tmp_path):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    engine = DocQARuntimeEngine(
        BenchmarkConfig(
            suite_name="qasper",
            output_dir=tmp_path / "out",
            benchmark_prompt_policy="benchmark_v1",
        )
    )

    kwargs = engine._docqa_request_kwargs(
        example=BenchmarkExample(
            example_id="ex",
            document_id="doc",
            question="What does the paper show?",
            answers=["runtime answer"],
        ),
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt")
        ],
        selected_file_ids=["file-1"],
        active_record=SimpleNamespace(file_id="file-1", name="doc.txt"),
    )

    assert kwargs["prompt"].startswith("Benchmark prompt contract:")
    assert (
        "Prompt source: allenai/qasper-led-baseline dataset contract"
        in kwargs["prompt"]
    )
    assert "Question: What does the paper show?" in kwargs["prompt"]
    assert "Answer formatting requirements:" not in kwargs["prompt"]
    assert "Return the final answer as Markdown" not in kwargs["prompt"]
    assert "Do not include hidden reasoning" in kwargs["prompt"]
