from types import SimpleNamespace
from typing import Any, cast

import ktem.docqa.runtime as runtime_module
from ktem.docqa.runtime import DocQARuntime


def test_runtime_prepare_pipeline_scopes_graph_index_to_graph_source_ids(monkeypatch):
    file_index = _PreparePipelineFileIndex()
    pipeline = SimpleNamespace()
    graph_calls = []

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

    def fake_graph_context(selected_index, selected_ids):
        graph_calls.append((selected_index, list(selected_ids)))
        return {
            "graph_index": {
                "entities": [{"id": "graph-only"}],
                "relations": [],
            }
        }

    monkeypatch.setattr(
        runtime_module._runtime_graph,
        "graph_context_for_selected_files",
        fake_graph_context,
        raising=False,
    )

    prepared = runtime._prepare_pipeline(
        runtime_module.DocQARequest(
            prompt="Compare graph sources.",
            selected_inputs={file_index.id: ["chat-file"]},
            graph_source_ids=["graph-file"],
            reasoning_type="mara",
            settings={"reasoning.use": "mara"},
            route_policy="graph",
        )
    )

    assert graph_calls == [(file_index, ["graph-file"])]
    assert prepared.graph_context["graph_index"]["entities"][0]["id"] == "graph-only"


class _PreparePipelineFileIndex:
    id = 9

    def resolve_selected_ids(self, _user_id, selected_input):
        return list(selected_input or [])

    def get_retriever_pipelines(self, _settings, _user_id, _selected_input):
        return []


class _PreviewForFileRecords:
    @staticmethod
    def resolve_file_path(file_id: str, *, user_id=None) -> str:
        return f"/resolved/{file_id}.pdf"

    @staticmethod
    def resolve_file_name(file_id: str, *, user_id=None) -> str:
        return f"{file_id}.pdf"

    @staticmethod
    def resolve_selected_file(file_ids: list[str], *, user_id=None):
        file_id = file_ids[0] if file_ids else ""
        return file_id, f"{file_id}.pdf" if file_id else "", ""

    @staticmethod
    def get_page_context_text(
        _file_id: str, _file_name: str, _page_number: int, *, user_id=None
    ) -> str:
        return ""

    @staticmethod
    def resolve_sources(file_ids, *, user_id=None, strict=True):
        return [
            SimpleNamespace(
                file_id=file_id,
                name=f"{file_id}.pdf",
                path=f"/resolved/{file_id}.pdf",
            )
            for file_id in file_ids
        ]
