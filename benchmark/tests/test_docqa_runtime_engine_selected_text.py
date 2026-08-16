from pathlib import Path
from types import SimpleNamespace

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa._runtime_turn import build_turn_request
from ktem.docqa.typed_retrieval_recovery import typed_qasper_recovery_requests

from benchmark.engines import DocQARuntimeEngine
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample

QASPER_FIXTURE = Path(__file__).parent / "fixtures" / "qasper_2001_05865.txt"
QASPER_TITLE = "Ensemble based discriminative models for Visual Dialog Challenge 2018"


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


def test_qasper_long_document_title_reaches_runtime_recovery_query(tmp_path):
    question = "What was the baseline?"
    assert QASPER_FIXTURE.stat().st_size == 4471
    engine = DocQARuntimeEngine(
        BenchmarkConfig(suite_name="qasper", output_dir=tmp_path / "out")
    )

    kwargs = engine._docqa_request_kwargs(
        example=BenchmarkExample(
            example_id="ambiguous-free-text",
            document_id="2001.05865",
            question=question,
            answers=["unanswerable"],
            answer_type="free_text",
        ),
        documents=[
            BenchmarkDocument(
                document_id="2001.05865",
                path=QASPER_FIXTURE,
                format_type="txt",
                metadata={"title": QASPER_TITLE, "dataset_family": "scientific_qa"},
            )
        ],
        selected_file_ids=["runtime-file-1"],
        active_record=SimpleNamespace(
            file_id="runtime-file-1",
            name="2001_05865.txt",
        ),
    )

    assert kwargs["selected_text"] == ""
    assert kwargs["selected_source_title"] == QASPER_TITLE
    runtime_request = build_turn_request(
        DocQARequest(**kwargs),
        SimpleNamespace(conversation_id="conversation", state={}, messages=[]),
        resolved_user_id=1,
        selected_inputs={},
        request_file_ids=["runtime-file-1"],
        load_settings=lambda _user_id: {},
    )
    assert runtime_request.selected_source_title == QASPER_TITLE
    [recovery] = typed_qasper_recovery_requests(
        runtime_request,
        [{"query_id": "round2:quality_retry", "query": question}],
    )
    assert recovery["query"] == f"{question} {QASPER_TITLE}"
    assert recovery["query_metadata"]["document_context"] == {
        "kind": "selected_document_title",
        "text": QASPER_TITLE,
    }


def test_multi_source_request_does_not_bind_one_document_title(tmp_path):
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("first", encoding="utf-8")
    second_path.write_text("second", encoding="utf-8")
    engine = DocQARuntimeEngine(
        BenchmarkConfig(suite_name="qasper", output_dir=tmp_path / "out")
    )

    kwargs = engine._docqa_request_kwargs(
        example=BenchmarkExample(
            example_id="multi-source",
            document_id="first",
            document_ids=["first", "second"],
            question="What was the baseline?",
            answers=["unanswerable"],
            answer_type="free_text",
        ),
        documents=[
            BenchmarkDocument(
                document_id="first",
                path=first_path,
                format_type="txt",
                metadata={"title": "First paper"},
            ),
            BenchmarkDocument(
                document_id="second",
                path=second_path,
                format_type="txt",
                metadata={"title": "Second paper"},
            ),
        ],
        selected_file_ids=["runtime-file-1", "runtime-file-2"],
        active_record=SimpleNamespace(file_id="runtime-file-1", name="first.txt"),
    )

    assert kwargs["selected_source_title"] == ""


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
