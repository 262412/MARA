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


def _install_fake_docqa_runtime(monkeypatch, doc_path):
    class FakeRequest:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)

    class FakeResponse:
        answer = "runtime answer"
        references_text = "doc.txt#page:1"
        agent_trace = [{"stage": "planner", "decision": "retrieve"}]
        evidence_metadata = {"has_formula_evidence": True}
        claim_verification = {"rewrite_skipped": True}
        presentation = {"markdown_normalized": True}
        controller_trace = [{"stage": "planner", "route": "graph_global"}]
        controller_decision = {"route": "graph_rag"}
        route_decision = {"route": "graph_global"}
        retrieve_decision = {"status": "good"}
        verify_decision = {"status": "supported"}
        guardrail_decision = {"status": "ok", "action": "return"}
        evidence_bundle = {"route": "graph_global", "items": []}
        workflow_plan = {
            "route": "graph_global",
            "steps": [{"executor": "retrieve_graph"}],
        }

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
    return fake_runtime


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
    assert result.agent_trace == []
    assert result.evidence_metadata == {}
    assert result.controller_trace == []
    assert result.controller_decision == {}
    assert result.route_decision == {}
    assert result.retrieve_decision == {}
    assert result.verify_decision == {}
    assert result.guardrail_decision == {}
    assert result.evidence_bundle == {}
    assert result.workflow_plan == {}
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
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    fake_runtime = _install_fake_docqa_runtime(monkeypatch, doc_path)
    engine = get_engine(
        "docqa_runtime",
        BenchmarkConfig(
            suite_name="runtime",
            output_dir=tmp_path / "out",
            scope="document",
            max_context_length=3000,
            llm_name="Deepseek",
            docqa_citation_mode="off",
            reasoning_type="mara",
            agent_mode="thorough",
            task_type="quiz",
            artifact_type="quiz",
            controller_mode="llm",
            route_policy="graph",
            planner_model="gpt-4o-mini",
            allowed_routes=["doc_text", "graph_global"],
            verification_mode="strict",
            graph_mode="global",
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
    assert fake_runtime.requests[0].max_context_length == 3000
    assert fake_runtime.requests[0].llm == "Deepseek"
    assert fake_runtime.requests[0].use_citation == "off"
    assert fake_runtime.requests[0].reasoning_type == "mara"
    assert fake_runtime.requests[0].agent_mode == "thorough"
    assert fake_runtime.requests[0].task_type == "quiz"
    assert fake_runtime.requests[0].artifact_type == "quiz"
    assert fake_runtime.requests[0].controller_mode == "llm"
    assert fake_runtime.requests[0].route_policy == "graph"
    assert fake_runtime.requests[0].planner_model == "gpt-4o-mini"
    assert fake_runtime.requests[0].allowed_routes == ["doc_text", "graph_global"]
    assert fake_runtime.requests[0].verification_mode == "strict"
    assert fake_runtime.requests[0].graph_mode == "global"
    assert result.answer == "runtime answer"
    assert result.predicted_pages == ["1"]
    assert result.predicted_sources == ["doc.txt#page:1"]
    assert result.agent_trace == [{"stage": "planner", "decision": "retrieve"}]
    assert result.evidence_metadata == {"has_formula_evidence": True}
    assert result.controller_trace == [{"stage": "planner", "route": "graph_global"}]
    assert result.controller_decision == {"route": "graph_rag"}
    assert result.route_decision == {"route": "graph_global"}
    assert result.retrieve_decision == {"status": "good"}
    assert result.verify_decision == {"status": "supported"}
    assert result.guardrail_decision == {"status": "ok", "action": "return"}
    assert result.evidence_bundle == {"route": "graph_global", "items": []}
    assert result.workflow_plan == {
        "route": "graph_global",
        "steps": [{"executor": "retrieve_graph"}],
    }
    assert result.claim_verification == {"rewrite_skipped": True}
    assert result.presentation == {"markdown_normalized": True}


def test_docqa_runtime_engine_passes_visual_backend_config(monkeypatch, tmp_path):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    fake_runtime = _install_fake_docqa_runtime(monkeypatch, doc_path)
    config = BenchmarkConfig(
        suite_name="runtime",
        output_dir=tmp_path / "out",
        scope="document",
        route_policy="visual",
    )
    config.visual_retriever_backend = "local_late_interaction"
    config.visual_generator_backend = "tests.fake_vlm"
    engine = get_engine("docqa_runtime", config)

    engine.run(
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

    assert fake_runtime.requests[0].visual_retriever_backend == (
        "local_late_interaction"
    )
    assert fake_runtime.requests[0].visual_generator_backend == "tests.fake_vlm"


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
