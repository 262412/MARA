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
