from types import SimpleNamespace
from typing import Any, cast

import ktem.docqa.runtime as runtime_module
from ktem.docqa import _runtime_graph
from ktem.docqa.graph_builder import local_graph_index_from_documents
from ktem.docqa.graph_index import select_graph_index_evidence
from ktem.docqa.runtime import DocQARuntime
from ktem.reasoning import mara_route_retrieval as route_retrieval

from kotaemon.base import RetrievedDocument


def test_local_graph_index_extracts_entities_relations_claims_and_communities():
    docs = [
        RetrievedDocument(
            text="Revenue supports Growth. Revenue increased in 2026.",
            id_="chunk-1",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "2",
            },
        )
    ]

    graph_index = local_graph_index_from_documents(docs)

    assert graph_index["entities"][0]["label"] == "Revenue"
    assert graph_index["relations"][0]["source"] == "Revenue"
    assert graph_index["relations"][0]["target"] == "Growth"
    assert graph_index["claims"][0]["text"] == "Revenue supports Growth."
    assert graph_index["community_summaries"][0]["entity_ids"] == [
        "growth",
        "revenue",
    ]
    assert graph_index["metadata"]["graph_builder"] == "local_graph_builder_v1"


def test_local_graph_index_groups_connected_entities_into_communities():
    docs = [
        RetrievedDocument(
            text=(
                "Revenue supports Growth. Growth drives Margin. "
                "Hiring supports Culture."
            ),
            id_="chunk-1",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "2",
            },
        )
    ]

    graph_index = local_graph_index_from_documents(docs)
    communities = graph_index["community_summaries"]

    assert [item["id"] for item in communities] == [
        "community-growth-margin-revenue",
        "community-culture-hiring",
    ]
    assert communities[0]["entity_ids"] == ["growth", "margin", "revenue"]
    assert "Revenue supports Growth" in communities[0]["summary"]
    assert "Growth drives Margin" in communities[0]["summary"]


def test_graph_index_uses_explicit_global_and_local_query_pipelines():
    graph_context = {
        "graph_index": local_graph_index_from_documents(
            [
                RetrievedDocument(
                    text="Revenue supports Growth. Growth drives Margin.",
                    id_="chunk-1",
                    metadata={"file_id": "file-1", "page_label": "2"},
                )
            ]
        )
    }

    global_metadata = select_graph_index_evidence(
        "Compare revenue and margin themes.",
        graph_context,
    )
    local_metadata = select_graph_index_evidence(
        "What supports Growth?",
        graph_context,
    )

    assert global_metadata["graph_mode"] == "global"
    assert global_metadata["graph_query_pipeline"] == "global_community_summary"
    assert global_metadata["graph_evidence"][0]["kind"] == "community"
    assert local_metadata["graph_mode"] == "local"
    assert local_metadata["graph_query_pipeline"] == "local_entity_relation"
    assert local_metadata["graph_evidence"][0]["kind"] in {"entity", "relation"}


def test_graph_index_honors_forced_graph_mode_over_query_terms():
    graph_context = {
        "graph_index": local_graph_index_from_documents(
            [
                RetrievedDocument(
                    text="Revenue supports Growth. Growth drives Margin.",
                    id_="chunk-1",
                    metadata={"file_id": "file-1", "page_label": "2"},
                )
            ]
        )
    }

    forced_local = select_graph_index_evidence(
        "Compare revenue and margin themes.",
        graph_context,
        graph_mode="local",
    )
    forced_global = select_graph_index_evidence(
        "What supports Growth?",
        graph_context,
        graph_mode="global",
    )

    assert forced_local["graph_mode"] == "local"
    assert forced_local["graph_query_pipeline"] == "local_entity_relation"
    assert forced_local["graph_evidence"][0]["kind"] in {"entity", "relation"}
    assert forced_global["graph_mode"] == "global"
    assert forced_global["graph_query_pipeline"] == "global_community_summary"
    assert forced_global["graph_evidence"][0]["kind"] == "community"


def test_graph_route_retrieval_honors_pipeline_graph_mode():
    graph_index = local_graph_index_from_documents(
        [
            RetrievedDocument(
                text="Revenue supports Growth. Growth drives Margin.",
                id_="chunk-1",
                metadata={"file_id": "file-1", "page_label": "2"},
            )
        ]
    )
    pipeline = SimpleNamespace(
        graph_context={"graph_index": graph_index},
        graph_mode="local",
    )

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "graph_rag",
        "Compare revenue and margin themes.",
        [],
        {"question": "Compare revenue and margin themes.", "modalities": ["text"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("graph route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert metadata["graph_mode"] == "local"
    assert metadata["graph_evidence"][0]["kind"] in {"entity", "relation"}


def test_runtime_graph_context_builds_index_from_selected_file_documents(monkeypatch):
    docs = [
        RetrievedDocument(
            text="Revenue supports Growth.",
            id_="chunk-1",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "2",
            },
        )
    ]
    monkeypatch.setattr(
        _runtime_graph,
        "documents_for_selected_files",
        lambda _file_index, selected_ids: docs if selected_ids == ["file-1"] else [],
    )

    context = _runtime_graph.graph_context_for_selected_files(object(), ["file-1"])

    assert context["graph_index"]["relations"][0]["source"] == "Revenue"
    assert context["graph_index"]["relations"][0]["target"] == "Growth"


def test_runtime_prepare_pipeline_sets_local_graph_index(monkeypatch):
    file_index = _PreparePipelineFileIndex()
    pipeline = SimpleNamespace()
    docs = [
        RetrievedDocument(
            text="Revenue supports Growth.",
            id_="chunk-1",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "2",
            },
        )
    ]

    class _Reasoning:
        @staticmethod
        def get_info():
            return {"id": "mara"}

        @staticmethod
        def get_pipeline(_settings, _reasoning_state, _retrievers):
            return pipeline

    runtime = cast(Any, object.__new__(DocQARuntime))
    runtime._app = SimpleNamespace(index_manager=SimpleNamespace(indices=[file_index]))
    runtime.file_index = file_index
    runtime._preview = _PreviewForFileRecords()
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
        runtime_module._runtime_graph,
        "documents_for_selected_files",
        lambda _file_index, selected_ids: docs if selected_ids == ["file-1"] else [],
        raising=False,
    )

    prepared = runtime._prepare_pipeline(
        runtime_module.DocQARequest(
            prompt="Compare revenue and growth.",
            selected_inputs={file_index.id: ["file-1"]},
            reasoning_type="mara",
            settings={"reasoning.use": "mara"},
            route_policy="graph",
        )
    )

    assert prepared.graph_context["graph_index"]["entities"][0]["label"] == "Revenue"
    assert pipeline.graph_context["graph_index"]["relations"][0]["target"] == "Growth"


class _PreparePipelineFileIndex:
    id = 9

    def resolve_selected_ids(self, _user_id, selected_input):
        return list(selected_input or [])

    def get_retriever_pipelines(self, _settings, _user_id, _selected_input):
        return []


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
