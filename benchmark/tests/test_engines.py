import sys
import types

import pytest

from benchmark.engines import (
    DirectPasteEngine,
    EngineRunResult,
    OraclePageEngine,
    get_engine,
)
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument, BenchmarkExample


def test_engine_run_result_exposes_phase_two_fields():
    result = EngineRunResult(answer="answer")

    assert result.answer == "answer"
    assert result.predicted_pages == []
    assert result.predicted_sources == []
    assert result.predicted_element_ids == []
    assert result.retrieved_hits == []
    assert result.timings == {}
    assert result.context_preview == ""
    assert result.retrieval_trace == []
    assert result.evidence_metadata == {}
    assert result.claim_verification == {}
    assert result.presentation == {}


@pytest.mark.parametrize(
    ("name", "expected_type"),
    [
        ("legacy_text_rag", "LegacyTextRAGEngine"),
        ("kotaemon-text-rag", "KotaemonTextRAGEngine"),
        ("docqa_runtime", "DocQARuntimeEngine"),
        ("direct_paste", "DirectPasteEngine"),
        ("oracle_page", "OraclePageEngine"),
    ],
)
def test_get_engine_returns_supported_adapter(name, expected_type):
    engine = get_engine(name, {"max_context_length": 128})

    assert type(engine).__name__ == expected_type


def test_get_engine_rejects_unknown_name_with_supported_names():
    with pytest.raises(ValueError) as exc_info:
        get_engine("missing", {})

    message = str(exc_info.value)
    assert "Unknown benchmark engine 'missing'" in message
    assert "direct_paste" in message
    assert "oracle_page" in message


def test_direct_paste_context_concatenates_document_text_and_truncates():
    engine = DirectPasteEngine({"max_context_length": 24})

    context = engine.select_context(
        documents=[
            {"document_id": "doc-1", "text": "Alpha document text."},
            {"document_id": "doc-2", "content": "Beta document text."},
        ],
        example={},
    )

    assert context == "Alpha document text.\n\nBe"


def test_oracle_page_context_prefers_gold_evidence_pages():
    engine = OraclePageEngine({"max_context_length": 200})

    context = engine.select_context(
        documents=[
            {
                "document_id": "doc-1",
                "pages": [
                    {"page": 1, "text": "Page one should be skipped."},
                    {"page": 2, "text": "Page two should be included."},
                    {"page": "A3", "text": "Appendix should be included."},
                ],
            }
        ],
        example={
            "evidence_pages": [2],
            "gold_evidence": [{"page": "A3", "span": "Appendix"}],
        },
    )

    assert context == "Page two should be included.\n\nAppendix should be included."


def test_oracle_page_context_falls_back_to_full_text_when_no_pages_match():
    engine = OraclePageEngine({"max_context_length": 200})

    context = engine.select_context(
        documents=[
            {
                "document_id": "doc-1",
                "text": "Full text fallback.",
                "pages": [{"page": 1, "text": "Page one."}],
            }
        ],
        example={"evidence_pages": [99], "gold_evidence": []},
    )

    assert context == "Full text fallback."


def test_docqa_runtime_engine_indexes_documents_and_runs_turn(monkeypatch, tmp_path):
    class FakeRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeResponse:
        answer = "runtime answer"
        references_text = "doc.txt#page:1"
        evidence_metadata = {"has_formula_evidence": True}
        claim_verification = {"rewrite_skipped": True}
        presentation = {"markdown_normalized": True}

    class FakeRecord:
        file_id = "file-1"
        name = "doc.txt"

    class FakeRuntime:
        def __init__(self):
            self.indexed = []
            self.requests = []
            self.file_ids_by_ref = {}

        def index_paths(self, paths, reindex=False):
            self.indexed.append((paths, reindex))
            self.file_ids_by_ref[str(doc_path)] = FakeRecord()
            self.file_ids_by_ref[doc_path.name] = FakeRecord()

        def resolve_file_refs(self, refs):
            return [
                self.file_ids_by_ref[ref] for ref in refs if ref in self.file_ids_by_ref
            ]

        def run_turn(self, request):
            self.requests.append(request)
            return FakeResponse()

    fake_runtime = FakeRuntime()
    monkeypatch.setitem(
        sys.modules,
        "ktem.docqa",
        types.SimpleNamespace(
            DocQARuntime=lambda: fake_runtime,
            DocQARequest=FakeRequest,
        ),
    )
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    engine = get_engine(
        "docqa_runtime",
        BenchmarkConfig(
            suite_name="runtime",
            output_dir=tmp_path / "out",
            scope="document",
            llm_name="Deepseek",
            docqa_citation_mode="off",
        ),
    )

    result = engine.run(
        example=BenchmarkExample(
            example_id="ex",
            document_id="doc",
            document_ids=["doc"],
            question="Question?",
            answers=["runtime answer"],
        ),
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt")
        ],
    )

    assert fake_runtime.indexed == [([str(doc_path)], False)]
    assert fake_runtime.requests[0].selected_file_ids == ["file-1"]
    assert fake_runtime.requests[0].qa_scope == "document"
    assert fake_runtime.requests[0].llm == "Deepseek"
    assert fake_runtime.requests[0].use_citation == "off"
    assert result.answer == "runtime answer"
    assert result.predicted_pages == ["1"]
    assert result.predicted_sources == ["doc.txt#page:1"]
    assert result.evidence_metadata == {"has_formula_evidence": True}
    assert result.claim_verification == {"rewrite_skipped": True}
    assert result.presentation == {"markdown_normalized": True}


def test_docqa_runtime_engine_reuses_already_indexed_documents(monkeypatch, tmp_path):
    class FakeRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeResponse:
        answer = "runtime answer"
        references_text = "doc.txt#page:1"

    class FakeRecord:
        file_id = "file-existing"
        name = "doc.txt"
        path = str(tmp_path / "doc.txt")
        size = 1
        tokens = 1
        loader = "test"
        date_created = None

    class FakeRuntime:
        def __init__(self):
            self.indexed = []
            self.requests = []

        def index_paths(self, paths, reindex=False):
            self.indexed.append((paths, reindex))

        def resolve_file_refs(self, refs):
            if refs and refs[0] in {"doc", "doc.txt", str(tmp_path / "doc.txt")}:
                return [FakeRecord()]
            if refs and refs[0] == "file-existing":
                return [FakeRecord()]
            return []

        def list_files(self, user_id=None):
            return [FakeRecord()]

        def run_turn(self, request):
            self.requests.append(request)
            return FakeResponse()

    fake_runtime = FakeRuntime()
    monkeypatch.setitem(
        sys.modules,
        "ktem.docqa",
        types.SimpleNamespace(
            DocQARuntime=lambda: fake_runtime,
            DocQARequest=FakeRequest,
        ),
    )
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    engine = get_engine(
        "docqa_runtime",
        BenchmarkConfig(
            suite_name="runtime",
            output_dir=tmp_path / "out",
            scope="document",
        ),
    )

    result = engine.run(
        example=BenchmarkExample(
            example_id="ex",
            document_id="doc",
            document_ids=["doc"],
            question="Question?",
            answers=["runtime answer"],
        ),
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt")
        ],
    )

    assert fake_runtime.indexed == []
    assert fake_runtime.requests[0].selected_file_ids == ["file-existing"]
    assert result.answer == "runtime answer"
