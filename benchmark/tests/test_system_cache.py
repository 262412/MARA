from benchmark.schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample
from benchmark.system import KotaemonTextRAGSystem, _evidence_metadata
from kotaemon.base import Document, RetrievedDocument


class _CountingReader:
    def __init__(self):
        self.calls = 0

    def load_data(self, path, extra_info=None, **kwargs):
        del path, kwargs
        self.calls += 1
        document = Document("cached alpha text", metadata={"page_label": "1"})
        if extra_info:
            document.metadata.update(extra_info)
        return [document]


class _PromptRecordingLLM:
    def __init__(self):
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "alpha"


def test_text_rag_system_uses_parse_cache_for_same_file_across_documents(
    monkeypatch, tmp_path
):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("alpha", encoding="utf-8")
    reader = _CountingReader()
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="cache",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=False,
            cache_mode="warm",
        )
    )
    monkeypatch.setattr(system, "_get_reader", lambda _path: reader)

    first = system._build_index(
        BenchmarkDocument(document_id="doc-a", path=doc_path, format_type="txt")
    )
    second = system._build_index(
        BenchmarkDocument(document_id="doc-b", path=doc_path, format_type="txt")
    )

    assert reader.calls == 1
    assert first.parse_cache_hit is False
    assert first.parse_cache_stats == {"hits": 0, "misses": 1, "writes": 1}
    assert second.parse_cache_hit is True
    assert second.parse_cache_stats == {"hits": 1, "misses": 0, "writes": 0}
    assert second.parsed_documents[0].metadata["file_id"] == "doc-b"


def test_text_rag_system_bypasses_parse_cache_when_requested(monkeypatch, tmp_path):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("alpha", encoding="utf-8")
    reader = _CountingReader()
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="cache",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=False,
            cache_mode="bypass",
        )
    )
    monkeypatch.setattr(system, "_get_reader", lambda _path: reader)

    first = system._build_index(
        BenchmarkDocument(document_id="doc-a", path=doc_path, format_type="txt")
    )
    second = system._build_index(
        BenchmarkDocument(document_id="doc-b", path=doc_path, format_type="txt")
    )

    assert reader.calls == 2
    assert first.parse_cache_hit is False
    assert second.parse_cache_hit is False
    assert first.parse_cache_stats == {"hits": 0, "misses": 0, "writes": 0}
    assert second.parse_cache_stats == {"hits": 0, "misses": 0, "writes": 0}


def test_text_rag_generation_uses_benchmark_prompt_not_user_template(
    monkeypatch,
    tmp_path,
):
    llm = _PromptRecordingLLM()
    monkeypatch.setattr(KotaemonTextRAGSystem, "_resolve_llm", lambda *_args: llm)
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="alce",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=True,
            prompt_template="USER SIDE TEMPLATE {context} {question}",
        )
    )

    answer, _evidence, _seconds, _metadata = system._generate_answer(
        BenchmarkExample(
            example_id="ex",
            document_id="doc",
            question="What is alpha?",
            answer_type="citation_qa",
            answers=["alpha"],
        ),
        [
            RetrievedDocument(
                text="alpha evidence",
                metadata={"file_name": "doc.txt", "page_label": "1"},
                score=1.0,
            )
        ],
    )

    assert answer == "alpha"
    assert llm.prompts
    prompt = llm.prompts[0]
    assert "Benchmark prompt contract:" in prompt
    assert "using only the provided search results" in prompt
    assert "alpha evidence" in prompt
    assert "USER SIDE TEMPLATE" not in prompt
    assert "Use the following context" not in prompt
    assert "Return the final answer as Markdown" not in prompt


def test_evidence_metadata_marks_visual_and_formula_context():
    metadata = _evidence_metadata(
        "multimodal",
        images=["page-image"],
        hits=[
            RetrievedDocument(
                text="formula text",
                metadata={
                    "element_type": "formula",
                    "latex": r"E=mc^2",
                    "page_image_path": "page.png",
                },
                score=1.0,
            )
        ],
    )

    assert metadata["evidence_mode"] == "multimodal"
    assert metadata["image_count"] == 1
    assert metadata["has_figure_evidence"] is True
    assert metadata["has_formula_evidence"] is True
    assert metadata["has_table_evidence"] is False
    assert metadata["has_slide_evidence"] is False
    assert metadata["has_page_visual_context"] is True
    assert metadata["source_kinds"] == ["formula"]


def test_evidence_metadata_marks_table_and_slide_context():
    metadata = _evidence_metadata(
        "hybrid",
        images=[],
        hits=[
            RetrievedDocument(
                text="table text",
                metadata={"element_type": "table", "table_html": "<table></table>"},
                score=1.0,
            ),
            RetrievedDocument(
                text="slide text",
                metadata={"content_type": "slide", "slide_number": 4},
                score=1.0,
            ),
        ],
    )

    assert metadata["has_table_evidence"] is True
    assert metadata["has_slide_evidence"] is True
