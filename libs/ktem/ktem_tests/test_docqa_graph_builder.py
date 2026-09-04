from types import SimpleNamespace
from typing import Any, cast

import ktem.docqa.runtime as runtime_module
from ktem.docqa import _runtime_graph
from ktem.docqa.graph_builder import (
    local_graph_index_from_documents,
    update_graph_index_incrementally,
)
from ktem.docqa.graph_index import select_graph_index_evidence
from ktem.docqa.runtime import DocQARuntime
from ktem.reasoning import mara_route_retrieval as route_retrieval

from kotaemon.base import RetrievedDocument


class _FixtureEntityBackend:
    name = "fixture_entity_backend"

    def __init__(self, calls):
        self.calls = calls

    def extract(self, documents):
        self.calls.append(("entities", len(list(documents))))
        return [
            {
                "id": "alpha",
                "label": "Alpha",
                "summary": "Alpha appears in fixture docs.",
                "source_backrefs": ["file-1#page:1"],
            },
            {
                "id": "beta",
                "label": "Beta",
                "summary": "Beta appears in fixture docs.",
                "source_backrefs": ["file-1#page:2"],
            },
        ]


class _FixtureRelationBackend:
    name = "fixture_relation_backend"

    def __init__(self, calls):
        self.calls = calls

    def extract(self, documents, entities):
        self.calls.append(("relations", len(list(documents)), len(entities)))
        return [
            {
                "id": "alpha-drives-beta",
                "source": "Alpha",
                "target": "Beta",
                "label": "drives",
                "description": "Alpha drives Beta.",
                "source_backrefs": ["file-1#page:1", "file-1#page:2"],
            }
        ]


class _FixtureCommunityDetector:
    name = "fixture_community_detector"

    def __init__(self, calls):
        self.calls = calls

    def detect(self, entities, relations):
        self.calls.append(("communities", len(entities), len(relations)))
        return [
            {
                "id": "community-alpha-beta",
                "entity_ids": ["alpha", "beta"],
                "relation_ids": ["alpha-drives-beta"],
            }
        ]


class _FixtureCommunitySummaryBackend:
    name = "fixture_community_summary"

    def __init__(self, calls):
        self.calls = calls

    def summarize(self, community, entities, relations):
        self.calls.append(("summary", community["id"], len(entities), len(relations)))
        return {
            "id": community["id"],
            "label": "Alpha, Beta",
            "summary": "Alpha and Beta form one fixture community.",
            "entity_ids": community["entity_ids"],
            "source_backrefs": ["file-1#page:1", "file-1#page:2"],
        }


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


def test_local_graph_index_uses_configured_extraction_and_community_backends():
    calls: list[tuple[Any, ...]] = []

    graph_index = local_graph_index_from_documents(
        [RetrievedDocument(text="Ignored by fixture.", id_="chunk-1", metadata={})],
        entity_extractor=_FixtureEntityBackend(calls),
        relation_extractor=_FixtureRelationBackend(calls),
        community_detector=_FixtureCommunityDetector(calls),
        community_summarizer=_FixtureCommunitySummaryBackend(calls),
    )

    assert graph_index["entities"][0]["label"] == "Alpha"
    assert graph_index["relations"][0]["id"] == "alpha-drives-beta"
    assert graph_index["community_summaries"][0]["summary"] == (
        "Alpha and Beta form one fixture community."
    )
    assert graph_index["metadata"] == {
        "graph_builder": "local_graph_builder_v1",
        "entity_extraction_backend": "fixture_entity_backend",
        "relation_extraction_backend": "fixture_relation_backend",
        "community_detection_backend": "fixture_community_detector",
        "community_summary_backend": "fixture_community_summary",
    }
    assert calls == [
        ("entities", 1),
        ("relations", 1, 2),
        ("communities", 2, 1),
        ("summary", "community-alpha-beta", 2, 1),
    ]


def test_update_graph_index_incrementally_merges_new_documents_and_rebuilds_communities():
    existing = local_graph_index_from_documents(
        [
            RetrievedDocument(
                text="Revenue supports Growth.",
                id_="chunk-old",
                metadata={"file_id": "file-1", "page_label": "1"},
            )
        ]
    )

    updated = update_graph_index_incrementally(
        existing,
        [
            RetrievedDocument(
                text="Growth drives Margin.",
                id_="chunk-new",
                metadata={"file_id": "file-2", "page_label": "3"},
            )
        ],
    )

    assert [item["id"] for item in updated["relations"]] == [
        "revenue-supports-growth",
        "growth-drives-margin",
    ]
    assert updated["community_summaries"][0]["entity_ids"] == [
        "growth",
        "margin",
        "revenue",
    ]
    assert updated["metadata"]["graph_builder"] == "incremental_graph_index_v1"
    assert updated["metadata"]["previous_entity_count"] == 2
    assert updated["metadata"]["new_relation_count"] == 1


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


def test_runtime_graph_context_prefers_persisted_graph_index(monkeypatch):
    persisted_doc = RetrievedDocument(
        text="Persisted graph index.",
        id_="graph-index-doc",
        metadata={
            "type": "mara_graph_index",
            "source_id": "file-1",
            "graph_index_relation_type": "graph_index",
            "graph_index": {
                "entities": [
                    {
                        "id": "persisted-revenue",
                        "label": "Persisted Revenue",
                        "summary": "Persisted graph summary.",
                        "source_backrefs": ["file-1#page:9"],
                    }
                ],
                "relations": [],
                "claims": [],
                "community_summaries": [],
                "metadata": {"graph_builder": "persisted_fixture"},
            },
        },
    )
    fallback_doc = RetrievedDocument(
        text="Fallback supports Runtime.",
        id_="fallback-doc",
        metadata={"file_id": "file-1", "page_label": "2"},
    )

    monkeypatch.setattr(
        _runtime_graph,
        "_documents_for_relation",
        lambda _file_index, selected_ids, relation_type: [persisted_doc]
        if selected_ids == ["file-1"] and relation_type == "graph_index"
        else [],
        raising=False,
    )
    monkeypatch.setattr(
        _runtime_graph,
        "documents_for_selected_files",
        lambda _file_index, selected_ids: [fallback_doc]
        if selected_ids == ["file-1"]
        else [],
        raising=False,
    )

    context = _runtime_graph.graph_context_for_selected_files(object(), ["file-1"])

    assert context["graph_index"]["entities"][0]["label"] == "Persisted Revenue"
    assert context["graph_index"]["metadata"]["graph_builder"] == "persisted_fixture"


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
    def resolve_selected_file(file_ids: list[str], *, user_id=None):
        assert user_id == "user-1"
        file_id = file_ids[0] if file_ids else ""
        return file_id, f"{file_id}.pdf" if file_id else "", ""

    @staticmethod
    def resolve_sources(file_ids: list[str], *, user_id=None, strict=False):
        assert user_id == "user-1"
        assert strict is True
        return [
            SimpleNamespace(
                file_id=file_id,
                name=f"{file_id}.pdf",
                path=f"/resolved/{file_id}.pdf",
            )
            for file_id in file_ids
        ]

    @staticmethod
    def get_page_context_text(_file_id: str, _file_name: str, _page_number: int) -> str:
        return ""
