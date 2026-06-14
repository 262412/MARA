import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import ktem.docqa.runtime as runtime_module
from ktem.docqa import (
    _runtime_doctor,
    _runtime_elements,
    _runtime_indexing,
    _runtime_pipeline,
    _runtime_selection,
    _runtime_turn,
)
from ktem.docqa._runtime_models import DocQAFileRecord, DocQASession
from ktem.docqa.runtime import DocQARuntime

from kotaemon.base import RetrievedDocument


def test_runtime_selection_module_preserves_boundary_helpers():
    assert _runtime_selection.normalize_selected_file_ids("file-1") == ["file-1"]
    assert _runtime_selection.normalize_page_number(0) == 1
    assert _runtime_selection.normalize_qa_scope("multi-doc") == "multi_document"
    assert _runtime_selection.merge_unique_file_ids(
        ["file-1", "file-2"],
        ["file-2", "file-3"],
    ) == ["file-1", "file-2", "file-3"]


def test_runtime_selection_resolves_file_refs_by_id_exact_name_and_contains():
    records = [
        SimpleNamespace(file_id="file-1", name="Alpha Report.pdf"),
        SimpleNamespace(file_id="file-2", name="Beta Notes.pdf"),
    ]

    assert _runtime_selection.resolve_file_refs(records, ["file-1"])[0].name == (
        "Alpha Report.pdf"
    )
    assert _runtime_selection.resolve_file_refs(records, ["beta"])[0].file_id == (
        "file-2"
    )


def test_runtime_selection_rejects_ambiguous_file_refs():
    records = [
        SimpleNamespace(file_id="file-1", name="Alpha Report.pdf"),
        SimpleNamespace(file_id="file-2", name="Alpha Notes.pdf"),
    ]

    try:
        _runtime_selection.resolve_file_refs(records, ["alpha"])
    except ValueError as exc:
        assert "ambiguous" in str(exc)
    else:
        raise AssertionError("Expected ambiguous file reference to raise")


def test_runtime_indexing_expands_directory_inputs_and_preserves_urls(tmp_path):
    file_index = SimpleNamespace(config={"supported_file_types": ".pdf,.txt"})
    (tmp_path / "keep.pdf").write_text("pdf", encoding="utf-8")
    (tmp_path / "skip.md").write_text("markdown", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "keep.txt").write_text("text", encoding="utf-8")

    expanded = _runtime_indexing.expand_index_inputs(
        file_index,
        [str(tmp_path), "https://example.com/doc.pdf"],
        zip_input_dir=tmp_path / "zip",
    )

    assert expanded == [
        str((tmp_path / "keep.pdf").resolve()),
        str((nested / "keep.txt").resolve()),
        "https://example.com/doc.pdf",
    ]


def test_runtime_indexing_expands_zip_inputs_with_supported_files(tmp_path):
    file_index = SimpleNamespace(config={"supported_file_types": ".txt"})
    zip_path = tmp_path / "bundle.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("keep.txt", "text")
        archive.writestr("skip.md", "markdown")

    expanded = _runtime_indexing.expand_index_inputs(
        file_index,
        [str(zip_path)],
        zip_input_dir=tmp_path / "zip",
    )

    assert len(expanded) == 1
    assert expanded[0].endswith("keep.txt")
    assert Path(expanded[0]).read_text(encoding="utf-8") == "text"


def test_runtime_doctor_treats_empty_model_pools_as_warnings():
    class _NoModelManager:
        @staticmethod
        def get_default_name():
            raise ValueError("No models in pool")

        @staticmethod
        def load_errors():
            return []

    result = _runtime_doctor.build_doctor_result(
        app=SimpleNamespace(app_name="MARA"),
        file_index=None,
        knowledge_graph=None,
        resolved_user_id="user-1",
        list_files=lambda **_kwargs: [],
        list_sessions=lambda **_kwargs: [],
        llms_manager=_NoModelManager(),
        embedding_manager=_NoModelManager(),
        reranking_manager=SimpleNamespace(load_errors=lambda: []),
    )

    assert result.ok is False
    assert result.issues == ["No default FileIndex is available."]
    assert result.warnings == [
        "No default LLM configured yet. DocQA doctor can still run before model setup.",
        "No default embedding model configured yet. DocQA doctor can still run before model setup.",
    ]


def test_runtime_pipeline_applies_request_setting_overrides():
    settings = {
        "reasoning.options.mara.llm": "default-llm",
        "reasoning.options.simple.create_mindmap": False,
        "reasoning.options.simple.highlight_citation": "off",
        "reasoning.lang": "en",
    }
    request = runtime_module.DocQARequest(
        prompt="Question",
        llm="gpt-4o-mini",
        use_mindmap=True,
        use_citation="inline",
        language="zh",
    )

    _runtime_pipeline.apply_request_setting_overrides(settings, "mara", request)

    assert settings["reasoning.options.mara.llm"] == "gpt-4o-mini"
    assert settings["reasoning.options.simple.create_mindmap"] is True
    assert settings["reasoning.options.simple.highlight_citation"] == "inline"
    assert settings["reasoning.lang"] == "zh"


def test_runtime_pipeline_builds_reasoning_state_from_app_and_pipeline_sections():
    state = {"app": {"regen": True}, "mara": {"cursor": "state"}}

    assert _runtime_pipeline.build_reasoning_state(state, "mara") == {
        "app": {"regen": True},
        "pipeline": {"cursor": "state"},
    }


def test_runtime_turn_request_preserves_controller_fields():
    request = runtime_module.DocQARequest(
        prompt="Question",
        conversation_id="conv-old",
        active_file_id="file-1",
        graph_context={"related_file_ids": ["file-1"]},
        controller_mode="llm",
        route_policy="hybrid",
        planner_model="fake-planner",
        allowed_routes=["hybrid"],
        verification_mode="strict",
        max_context_length=3000,
        origin="web",
    )
    session = _session(messages=[("Earlier", "Answer")])

    turn_request = _runtime_turn.build_turn_request(
        request,
        session,
        resolved_user_id="user-1",
        selected_inputs={9: ["file-1"]},
        request_file_ids=["file-1"],
        load_settings=lambda _user_id: {"reasoning.use": "mara"},
    )

    assert turn_request.conversation_id == "conv-1"
    assert turn_request.history == [("Earlier", "Answer")]
    assert turn_request.settings == {"reasoning.use": "mara"}
    assert turn_request.controller_mode == "llm"
    assert turn_request.route_policy == "hybrid"
    assert turn_request.planner_model == "fake-planner"
    assert turn_request.allowed_routes == ["hybrid"]
    assert turn_request.verification_mode == "strict"
    assert turn_request.max_context_length == 3000


def test_runtime_turn_request_preserves_visual_backend_fields():
    request = runtime_module.DocQARequest(prompt="Question")
    request.visual_retriever_backend = "local_late_interaction"
    request.visual_generator_backend = "tests.fake_vlm"
    session = _session()

    turn_request = _runtime_turn.build_turn_request(
        request,
        session,
        resolved_user_id="user-1",
        selected_inputs={},
        request_file_ids=[],
        load_settings=lambda _user_id: {"reasoning.use": "mara"},
    )

    assert turn_request.visual_retriever_backend == "local_late_interaction"
    assert turn_request.visual_generator_backend == "tests.fake_vlm"


def test_runtime_builds_local_file_records_for_route_retrieval():
    runtime = _RuntimeForFileRecords()

    records = runtime._selected_file_records_for_retrieval(
        ["file-a"],
        "file-b",
        "user-1",
    )

    assert records == [
        {
            "file_id": "file-a",
            "file_name": "file-a.pdf",
            "path": "/resolved/file-a.pdf",
        },
        {
            "file_id": "file-b",
            "file_name": "file-b.pdf",
            "path": "/resolved/file-b.pdf",
        },
    ]


def test_runtime_elements_builds_records_from_selected_file_documents(monkeypatch):
    docs = [
        RetrievedDocument(
            text="Revenue grew by region.",
            id_="table-doc",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "element_id": "table-4",
                "element_type": "table",
                "caption": "Regional revenue",
            },
        )
    ]

    monkeypatch.setattr(
        _runtime_elements,
        "documents_for_selected_files",
        lambda _file_index, selected_ids: docs if selected_ids == ["file-1"] else [],
    )

    records = _runtime_elements.element_index_records_for_selected_files(
        object(),
        ["file-1"],
    )

    assert records[0]["evidence_id"] == "element:file-1:4:table-4"
    assert records[0]["text"] == "Revenue grew by region."


def test_runtime_prepare_pipeline_sets_element_index_records(monkeypatch):
    file_index = _PreparePipelineFileIndex()
    pipeline = SimpleNamespace()

    class _Reasoning:
        @staticmethod
        def get_info():
            return {"id": "mara"}

        @staticmethod
        def get_pipeline(_settings, _reasoning_state, _retrievers):
            return pipeline

    runtime = cast(Any, object.__new__(DocQARuntime))
    runtime._app = SimpleNamespace(
        index_manager=SimpleNamespace(indices=[file_index]),
    )
    runtime.file_index = file_index
    runtime._preview = cast(Any, _PreviewForFileRecords())
    runtime._web_search_cls = None
    runtime._resolve_user_id = lambda _user_id=None: "user-1"
    monkeypatch.setitem(runtime_module.reasonings, "mara", _Reasoning)
    monkeypatch.setattr(
        runtime_module._runtime_elements,
        "element_index_records_for_selected_files",
        lambda selected_index, selected_ids: [
            {
                "evidence_id": "element:file-1:4:table-4",
                "file_id": "file-1",
                "page_label": "4",
                "element_id": "table-4",
                "modality": "table",
                "text": "Revenue grew by region.",
            }
        ]
        if selected_index is file_index and selected_ids == ["file-1"]
        else [],
        raising=False,
    )

    prepared = runtime._prepare_pipeline(
        runtime_module.DocQARequest(
            prompt="Which table shows revenue?",
            selected_inputs={file_index.id: ["file-1"]},
            reasoning_type="mara",
            settings={"reasoning.use": "mara"},
            route_policy="element",
        )
    )

    assert prepared.pipeline.element_index_records[0]["evidence_id"] == (
        "element:file-1:4:table-4"
    )


def test_runtime_prepare_pipeline_sets_configured_visual_backends(monkeypatch):
    file_index = _PreparePipelineFileIndex()
    pipeline = SimpleNamespace()
    fake_retriever = SimpleNamespace(name="fake_visual_retriever")
    fake_generator = SimpleNamespace(name="fake_visual_generator")

    class _Reasoning:
        @staticmethod
        def get_info():
            return {"id": "mara"}

        @staticmethod
        def get_pipeline(_settings, _reasoning_state, _retrievers):
            return pipeline

    runtime = cast(Any, object.__new__(DocQARuntime))
    runtime._app = SimpleNamespace(
        index_manager=SimpleNamespace(indices=[file_index]),
    )
    runtime.file_index = file_index
    runtime._preview = cast(Any, _PreviewForFileRecords())
    runtime._web_search_cls = None
    runtime._resolve_user_id = lambda _user_id=None: "user-1"
    monkeypatch.setitem(runtime_module.reasonings, "mara", _Reasoning)
    monkeypatch.setattr(
        runtime_module._runtime_elements,
        "element_index_records_for_selected_files",
        lambda _selected_index, _selected_ids: [],
        raising=False,
    )
    monkeypatch.setattr(
        runtime_module._mara,
        "build_visual_retriever_backend",
        lambda backend_name: fake_retriever
        if backend_name == "local_late_interaction"
        else None,
        raising=False,
    )
    monkeypatch.setattr(
        runtime_module._mara,
        "build_visual_generator_backend",
        lambda backend_name: fake_generator
        if backend_name == "tests.fake_vlm"
        else None,
        raising=False,
    )

    runtime._prepare_pipeline(
        runtime_module.DocQARequest(
            prompt="What does the chart show?",
            selected_inputs={file_index.id: ["file-1"]},
            reasoning_type="mara",
            settings={"reasoning.use": "mara"},
            route_policy="visual",
            visual_retriever_backend="local_late_interaction",
            visual_generator_backend="tests.fake_vlm",
        )
    )

    assert pipeline.visual_retriever is fake_retriever
    assert pipeline.vlm_generator is fake_generator
    assert pipeline.visual_retriever_backend == "local_late_interaction"
    assert pipeline.visual_generator_backend == "tests.fake_vlm"


class _PreviewForFileRecords:
    @staticmethod
    def resolve_file_path(file_id: str) -> str:
        return f"/resolved/{file_id}.pdf"

    @staticmethod
    def resolve_file_name(file_id: str) -> str:
        return f"{file_id}.pdf"

    @staticmethod
    def resolve_selected_file(file_ids: list[str]):
        file_id = file_ids[0] if file_ids else ""
        return file_id, f"{file_id}.pdf" if file_id else "", ""

    @staticmethod
    def get_page_context_text(_file_id: str, _file_name: str, _page_number: int) -> str:
        return ""


class _PreparePipelineFileIndex:
    id = 9

    def resolve_selected_ids(self, _user_id, selected_input):
        return list(selected_input or [])

    def get_retriever_pipelines(self, _settings, _user_id, _selected_input):
        return []


class _RuntimeForFileRecords(DocQARuntime):
    def __init__(self) -> None:
        self._preview = cast(Any, _PreviewForFileRecords())

    def resolve_file_refs(
        self, refs: list[str], user_id: Any = None
    ) -> list[DocQAFileRecord]:
        del user_id
        return [
            DocQAFileRecord(
                file_id=ref,
                name=f"{ref}.pdf",
                size=0,
                tokens=0,
                loader="",
                path=f"/stored/{ref}.pdf",
                date_created=None,
            )
            for ref in refs
        ]


def _session(messages=None):
    return DocQASession(
        conversation_id="conv-1",
        name="Conversation",
        user_id="user-1",
        is_public=False,
        data_source={},
        messages=list(messages or []),
        retrieval_messages=[],
        plot_history=[],
        state={"app": {"regen": False}},
        selected_mapping={},
        graph_source_ids=[],
        origin="cli",
        date_created=None,
        date_updated=None,
    )
