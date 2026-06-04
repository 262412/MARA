import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import ktem.docqa.runtime as runtime_module
from ktem.docqa import (
    _runtime_doctor,
    _runtime_indexing,
    _runtime_pipeline,
    _runtime_selection,
    _runtime_sessions,
    _runtime_turn,
)
from ktem.docqa._runtime_models import DocQAFileRecord, DocQASession, _PreparedPipeline
from ktem.docqa._runtime_notebook import NOTEBOOK_KEY
from ktem.docqa.runtime import DocQARuntime

from kotaemon.base import Document


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


class _PreviewForFileRecords:
    @staticmethod
    def resolve_file_path(file_id: str) -> str:
        return f"/resolved/{file_id}.pdf"

    @staticmethod
    def resolve_file_name(file_id: str) -> str:
        return f"{file_id}.pdf"


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


def test_runtime_turn_stream_capture_collects_channels_and_mara_payloads():
    prepared = _PreparedPipeline(
        pipeline=_StreamingPipeline(),
        reasoning_state={"pipeline": {"step": "done"}},
        selected_file_ids=[],
        active_file_id="",
        active_file_name="",
        qa_scope="document",
        page_number=None,
        selected_text="",
        graph_context={},
        settings={},
        reasoning_id="mara",
    )
    request = runtime_module.DocQARequest(prompt="Question", state={"app": {}})

    result = _runtime_turn.collect_stream_result(
        prepared,
        request,
        conversation_id="conv-1",
        history=[],
        empty_message="empty",
    )

    assert result.text == "answer"
    assert result.refs == "refs<svg class='markmap'></svg>"
    assert result.mindmap_html == "<svg class='markmap'></svg>"
    assert result.plot == {"nodes": []}
    assert result.state["mara"] == {"step": "done"}
    assert result.stream_events[-1]["channel"] == "plot"
    assert result.capture.agent_trace == [{"event": "route"}]


def test_runtime_sessions_prepares_append_and_regen_histories():
    appended = _runtime_sessions.prepare_conversation_histories(
        retrieval_message="refs-2",
        plot_data={"plot": 2},
        retrieval_history=["refs-1"],
        plot_history=[{"plot": 1}],
        state={"app": {"regen": False}},
    )
    regenerated = _runtime_sessions.prepare_conversation_histories(
        retrieval_message="refs-new",
        plot_data={"plot": "new"},
        retrieval_history=["refs-old"],
        plot_history=[{"plot": "old"}],
        state={"app": {"regen": True}},
    )

    assert appended.retrieval_history == ["refs-1", "refs-2"]
    assert appended.plot_history == [{"plot": 1}, {"plot": 2}]
    assert appended.state["app"]["regen"] is False
    assert regenerated.retrieval_history == ["refs-new"]
    assert regenerated.plot_history == [{"plot": "new"}]
    assert regenerated.state["app"]["regen"] is False


def test_runtime_sessions_builds_owner_data_source_preserving_notebook_state():
    data_source = {
        "selected": {"9": ["select", ["old"], "user-1"]},
        "likes": [{"message": 1}],
        "chat_suggestions": ["next"],
        "origin": "cli",
        NOTEBOOK_KEY: {"notes": [{"note_id": "note-1", "text": "note text"}]},
    }

    updated = _runtime_sessions.build_conversation_data_source(
        data_source=data_source,
        selected_mapping={"9": ["select", ["file-1"], "user-1"]},
        is_owner=True,
        messages=[("question", "answer")],
        retrieval_history=["refs"],
        plot_history=[{"plot": 1}],
        state={"app": {"regen": False}},
        graph_source_ids=["file-1"],
        origin="web",
    )

    assert updated["selected"] == {"9": ["select", ["file-1"], "user-1"]}
    assert updated["likes"] == [{"message": 1}]
    assert updated["chat_suggestions"] == ["next"]
    assert updated["origin"] == "web"
    assert updated[NOTEBOOK_KEY]["notes"][0]["note_id"] == "note-1"


def test_runtime_sessions_preserves_selected_mapping_for_non_owner():
    updated = _runtime_sessions.build_conversation_data_source(
        data_source={"selected": {"9": ["select", ["old"], "owner"]}},
        selected_mapping={"9": ["select", ["new"], "other"]},
        is_owner=False,
        messages=[],
        retrieval_history=[],
        plot_history=[],
        state={"app": {"regen": False}},
        graph_source_ids=[],
        origin=None,
    )

    assert updated["selected"] == {"9": ["select", ["old"], "owner"]}


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


class _StreamingPipeline:
    @staticmethod
    def get_info():
        return {"id": "mara"}

    def stream(self, _prompt, _conversation_id, _history):
        yield Document(
            channel="debug",
            content={
                "mara_channel": "agent_trace",
                "payload": {"event": "route"},
            },
        )
        yield Document(channel="chat", content="answer")
        yield Document(channel="info", content="refs")
        yield Document(channel="info", content="<svg class='markmap'></svg>")
        yield Document(channel="plot", content={"nodes": []})
