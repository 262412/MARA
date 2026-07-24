import benchmark.system as system_module
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


class _StaticReader:
    def __init__(self, text):
        self.text = text

    def load_data(self, path, extra_info=None, **kwargs):
        del path, kwargs
        document = Document(self.text, metadata={"page_label": "1"})
        if extra_info:
            document.metadata.update(extra_info)
        return [document]


class _PromptRecordingLLM:
    def __init__(self):
        self.prompts: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return "alpha"


class _SequenceLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def __call__(self, prompt: str, **kwargs):
        self.calls.append((prompt, kwargs))
        return next(self.responses)


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


def test_text_rag_system_runs_multi_document_text_retrieval(monkeypatch, tmp_path):
    first_path = tmp_path / "first.txt"
    second_path = tmp_path / "second.txt"
    first_path.write_text("alpha", encoding="utf-8")
    second_path.write_text("beta", encoding="utf-8")
    readers = {
        first_path: _CountingReader(),
        second_path: _CountingReader(),
    }
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="coverage",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=False,
            cache_mode="warm",
            top_k=2,
        )
    )
    monkeypatch.setattr(system, "_get_reader", readers.__getitem__)
    documents = [
        BenchmarkDocument(document_id="doc-a", path=first_path, format_type="txt"),
        BenchmarkDocument(document_id="doc-b", path=second_path, format_type="txt"),
    ]
    example = BenchmarkExample(
        example_id="example-a",
        document_id="doc-a",
        question="Where is cached alpha text?",
        answers=["cached alpha text"],
        evidence_pages=["1"],
    )

    result = system.run_example_documents(documents, example)

    assert result["example_id"] == "example-a"
    assert result["predicted_answer"] == "cached alpha text"
    assert result["predicted_pages"] == ["1", "1"]
    assert result["predicted_sources"] == [
        "first.txt#page:1",
        "first.txt#page:1",
    ]
    assert result["performance"]["num_documents"] == 2
    assert result["performance"]["num_chunks"] == 2
    assert result["cache"]["parse"] == {"hits": 0, "misses": 2, "writes": 2}
    assert [item["document_id"] for item in system.document_reports()] == [
        "doc-a",
        "doc-b",
    ]
    assert all(reader.calls == 1 for reader in readers.values())


def test_text_rag_system_preserves_full_retrieved_text_for_diagnostics(
    monkeypatch, tmp_path
):
    doc_path = tmp_path / "long.txt"
    full_text = "alpha " + ("padding " * 100) + "gold evidence after preview"
    doc_path.write_text(full_text, encoding="utf-8")
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="diagnostic coverage",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=False,
            top_k=1,
        )
    )
    monkeypatch.setattr(system, "_get_reader", lambda _path: _StaticReader(full_text))

    result = system.run_example(
        BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt"),
        BenchmarkExample(
            example_id="example",
            document_id="doc",
            question="Where is the gold evidence?",
            answers=["gold evidence after preview"],
            evidence_pages=["1"],
        ),
    )

    hit = result["retrieved_hits"][0]
    assert "gold evidence after preview" not in hit["text_preview"]
    assert "gold evidence after preview" in hit["text"]
    assert len(hit["text"]) > 400


def test_text_rag_system_lexical_helpers_cover_empty_and_ranked_queries(tmp_path):
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="coverage",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=False,
            top_k=1,
        )
    )
    documents = [
        Document("alpha alpha beta", doc_id="one"),
        Document("beta gamma", doc_id="two"),
        Document("", doc_id="empty"),
    ]

    assert system._lexical_hits("", documents, 3) == []
    assert system._lexical_hits("missing", documents, 3) == []
    hits = system._lexical_hits("alpha beta", documents, 3)

    assert [hit.doc_id for hit in hits] == ["one", "two"]
    assert system._combine_hits("alpha beta", [], hits) == [hits[0]]


def test_text_rag_system_selects_configured_pdf_reader_and_cold_cache(tmp_path):
    expected_readers = {
        "adobe": system_module.adobe_reader,
        "azure-di": system_module.azure_reader,
        "docling": system_module.docling_reader,
    }

    for reader_mode, expected_reader in expected_readers.items():
        system = KotaemonTextRAGSystem(
            BenchmarkConfig(
                suite_name="reader coverage",
                route="text route",
                output_dir=tmp_path / "out",
                retrieval_mode="text",
                use_generation=False,
                reader_mode=reader_mode,
                cache_mode="cold",
            )
        )

        assert system._get_reader(tmp_path / "document.pdf") is expected_reader
        assert (
            system._get_reader(tmp_path / "document.unknown")
            is system_module.unstructured
        )
        cache_dir = system._embedding_cache_dir()
        assert cache_dir is not None
        assert cache_dir.name == "embedding"
        assert cache_dir.parent.name.startswith("cold-")
        assert cache_dir.parent.parent.name == "text-route"


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


def test_qasper_text_rag_runs_answerability_verifier_after_generation(
    monkeypatch,
    tmp_path,
):
    llm = _SequenceLLM(
        [
            "The baseline was NDCG 55.46.",
            '{"verdict":"unsupported","evidence_quote":'
            '"The proposed system reports NDCG 55.46."}',
        ]
    )
    monkeypatch.setattr(KotaemonTextRAGSystem, "_resolve_llm", lambda *_args: llm)
    system = KotaemonTextRAGSystem(
        BenchmarkConfig(
            suite_name="qasper-typed",
            output_dir=tmp_path / "out",
            retrieval_mode="text",
            use_generation=True,
        )
    )

    answer, _evidence, _seconds, metadata = system._generate_answer(
        BenchmarkExample(
            example_id="ex",
            document_id="paper",
            question="What was the baseline?",
            answer_type="unanswerable",
            answers=["unanswerable"],
        ),
        [
            RetrievedDocument(
                text=(
                    "The proposed system reports NDCG 55.46. No baseline is identified."
                ),
                metadata={"file_name": "paper.txt"},
                score=1.0,
            )
        ],
    )

    assert answer == "unanswerable"
    assert len(llm.calls) == 2
    assert metadata["qasper_answerability"] == {
        "contract_id": "qasper_answerability.v7",
        "status": "ok",
        "verdict": "unsupported",
        "action": "abstained_unsupported_candidate",
        "evidence_quote": "The proposed system reports NDCG 55.46.",
        "quote_grounded": "true",
        "quote_supports_relation": "false",
        "parser_status": "ok",
        "repair_attempted": "false",
    }


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
