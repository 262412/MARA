import html
import json

from ktem.pages.chat.knowledge_graph_service import GlobalKnowledgeGraphService


class _DummyApp:
    pass


class _DummyIndex:
    pass


def _make_service(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "ktem.pages.chat.knowledge_graph_service.flowsettings.KH_APP_DATA_DIR",
        tmp_path,
        raising=False,
    )
    return GlobalKnowledgeGraphService(_DummyApp(), _DummyIndex())


def test_conversation_graph_groups_related_and_unrelated_files(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)
    monkeypatch.setattr(
        service,
        "_build_file_graph",
        lambda file_id, source: {
            "file_id": file_id,
            "file_name": source["name"],
            "summary": f"Summary for {source['name']}",
            "summary_support_pages": {file_id: ["1"]},
            "summary_support_chunk_ids": {file_id: [f"{file_id}-chunk-summary"]},
            "top_keywords": {
                "file-a": ["rag", "retrieval", "chunking"],
                "file-b": ["rag", "retrieval", "citation"],
                "file-c": ["biology", "cells", "genetics"],
            }[file_id],
            "knowledge_points": [
                {
                    "id": f"point::{file_id}::1",
                    "type": "knowledge_point",
                    "file_id": file_id,
                    "label": f"Point for {source['name']}",
                    "keywords": {
                        "file-a": ["rag", "retrieval"],
                        "file-b": ["rag", "citation"],
                        "file-c": ["biology", "cells"],
                    }[file_id],
                    "related_file_ids": [file_id],
                    "support_pages": {file_id: ["1"]},
                    "support_chunk_ids": {file_id: [f"{file_id}-chunk-1"]},
                }
            ],
        },
    )

    graph = service._build_conversation_graph(
        "conv-1",
        {
            "file-a": {"name": "Alpha.pdf"},
            "file-b": {"name": "Beta.pdf"},
            "file-c": {"name": "Cells.pdf"},
        },
    )

    systems = graph["systems"]
    assert len(systems) == 2
    system_sizes = sorted(len(system["related_file_ids"]) for system in systems)
    assert system_sizes == [1, 2]
    assert graph["split_reason"] == "weakly_connected_sources"
    assert len(graph["maps"]) == 2
    map_sizes = sorted(len(item["related_file_ids"]) for item in graph["maps"])
    assert map_sizes == [1, 2]
    assert graph["support_pages"]["file-a"] == ["1"]
    assert graph["support_pages"]["file-b"] == ["1"]
    assert graph["support_pages"]["file-c"] == ["1"]
    assert "file-a-chunk-summary" in graph["support_chunk_ids"]["file-a"]
    assert "file-a-chunk-1" in graph["support_chunk_ids"]["file-a"]


def test_builder_conversation_graph_uses_service_file_graph_seam(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)

    monkeypatch.setattr(
        service._builder,
        "build_file_graph",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("builder should route through service._build_file_graph")
        ),
    )
    monkeypatch.setattr(
        service,
        "_build_file_graph",
        lambda file_id, source: {
            "file_id": file_id,
            "file_name": source["name"],
            "summary": f"Summary for {source['name']}",
            "summary_support_pages": {file_id: ["1"]},
            "summary_support_chunk_ids": {file_id: [f"{file_id}-chunk-summary"]},
            "top_keywords": ["rag", "retrieval"],
            "knowledge_points": [],
        },
    )

    graph = service._builder.build_conversation_graph(
        "conv-builder",
        {
            "file-a": {"name": "Alpha.pdf"},
            "file-b": {"name": "Beta.pdf"},
        },
    )

    assert graph["source_ids"] == ["file-a", "file-b"]
    assert len(graph["file_cards"]) == 2


def test_get_graph_view_does_not_auto_build_without_force_rebuild(
    monkeypatch, tmp_path
):
    service = _make_service(monkeypatch, tmp_path)
    monkeypatch.setattr(
        service,
        "_load_sources",
        lambda source_ids: {
            "file-a": {
                "id": "file-a",
                "name": "Alpha.pdf",
                "path": "",
                "size": 1,
                "date_created": "2026-01-01",
            }
        },
    )

    build_calls = []

    def _build_graph(conversation_id, sources):
        build_calls.append((conversation_id, sorted(sources.keys())))
        return {
            "conversation_id": conversation_id,
            "source_ids": list(sources.keys()),
            "systems": [],
            "file_cards": [],
            "knowledge_points": [],
            "edges": [],
            "support_pages": {},
            "support_chunk_ids": {},
        }

    monkeypatch.setattr(service, "_build_conversation_graph", _build_graph)

    first_view = service.get_graph_view(
        "conv-2",
        ["file-a"],
        focus_file_id="file-a",
        force_rebuild=False,
    )
    assert first_view["status"] == "stale"
    assert first_view["graph"] is None
    assert "not been generated" in first_view["status_message"]
    assert first_view["support_pages"] == {}
    assert first_view["support_chunk_ids"] == {}
    assert build_calls == []

    built_view = service.get_graph_view(
        "conv-2",
        ["file-a"],
        focus_file_id="file-a",
        force_rebuild=True,
    )
    assert built_view["status"] == "ready"
    assert build_calls == [("conv-2", ["file-a"])]

    refreshed_view = service.get_graph_view(
        "conv-2",
        ["file-a"],
        focus_file_id="file-a",
        force_rebuild=False,
    )
    assert refreshed_view["status"] == "ready"
    assert build_calls == [("conv-2", ["file-a"])]


def test_get_graph_view_returns_focus_html_and_prunes_missing_sources(
    monkeypatch, tmp_path
):
    service = _make_service(monkeypatch, tmp_path)
    monkeypatch.setattr(
        service,
        "_load_sources",
        lambda source_ids: {
            "file-a": {
                "id": "file-a",
                "name": "Alpha.pdf",
                "path": "",
                "size": 1,
                "date_created": "2026-01-01",
            },
            "file-b": {
                "id": "file-b",
                "name": "Beta.pdf",
                "path": "",
                "size": 1,
                "date_created": "2026-01-02",
            },
        },
    )
    monkeypatch.setattr(
        service,
        "_build_conversation_graph",
        lambda conversation_id, sources: {
            "conversation_id": conversation_id,
            "source_ids": list(sources.keys()),
            "systems": [
                {
                    "id": "system::1",
                    "type": "knowledge_system",
                    "label": "Shared knowledge system",
                    "summary": "Connects uploaded sources through rag.",
                    "related_file_ids": ["file-a", "file-b"],
                    "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                    "support_chunk_ids": {"file-a": ["a1"], "file-b": ["b1"]},
                    "themes": [],
                }
            ],
            "file_cards": [
                {
                    "id": "file::file-a",
                    "type": "file_summary",
                    "system_id": "system::1",
                    "file_id": "file-a",
                    "label": "Alpha.pdf",
                    "summary": "Alpha summary",
                    "related_file_ids": ["file-a", "file-b"],
                    "support_pages": {"file-a": ["1"]},
                    "support_chunk_ids": {"file-a": ["a1"]},
                    "top_keywords": ["rag"],
                }
            ],
            "knowledge_points": [
                {
                    "id": "point::file-a::1",
                    "type": "knowledge_point",
                    "system_id": "system::1",
                    "file_id": "file-a",
                    "label": "Alpha point",
                    "related_file_ids": ["file-a", "file-b"],
                    "support_pages": {"file-a": ["1"]},
                    "support_chunk_ids": {"file-a": ["a1"]},
                }
            ],
            "edges": [],
            "support_pages": {"file-a": ["1"]},
            "support_chunk_ids": {"file-a": ["a1"]},
        },
    )

    graph_view = service.get_graph_view(
        "conv-1",
        ["file-a", "file-b", "missing"],
        focus_file_id="file-a",
        force_rebuild=True,
    )

    assert graph_view["status"] == "ready"
    assert graph_view["graph_source_ids"] == ["file-a", "file-b"]
    assert "kg-tree-node" in graph_view["html"]
    assert "data-kg-payload" in graph_view["html"]
    assert graph_view["support_pages"] == {"file-a": ["1"]}
    assert graph_view["support_chunk_ids"] == {"file-a": ["a1"]}


def test_build_file_graph_uses_llm_outline_and_maps_support(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)

    class _FakeDoc:
        def __init__(self, doc_id, text, page_label):
            self.doc_id = doc_id
            self.text = text
            self.metadata = {"type": "text", "page_label": page_label}

    fake_docs = [
        _FakeDoc(
            "chunk-1",
            "Retrieval augmented generation combines search and synthesis. "
            "Chunk ranking improves grounded answers for enterprise docs.",
            "1",
        ),
        _FakeDoc(
            "chunk-2",
            "Citation mapping links generated statements to page evidence. "
            "This improves traceability and review workflows.",
            "2",
        ),
    ]

    monkeypatch.setattr(service, "_load_file_docs", lambda file_id: fake_docs)
    monkeypatch.setattr(
        service,
        "_generate_outline_with_llm",
        lambda file_name, candidates: {
            "summary": "The document explains a RAG pipeline with citation-backed evidence alignment.",
            "knowledge_points": [
                {
                    "label": "RAG combines retrieval with generation for grounded responses.",
                    "keywords": ["rag", "retrieval", "generation"],
                },
                {
                    "label": "Citation mapping ties statements to evidence chunks and pages.",
                    "keywords": ["citation", "evidence", "traceability"],
                },
            ],
        },
    )

    file_graph = service._build_file_graph(
        "file-rag",
        {
            "id": "file-rag",
            "name": "RAG-Guide.pdf",
            "path": "",
            "size": 1,
            "date_created": "2026-04-16",
        },
    )

    assert file_graph["summary"]
    assert len(file_graph["knowledge_points"]) >= 2
    assert file_graph["summary_support_pages"]["file-rag"]
    assert file_graph["summary_support_chunk_ids"]["file-rag"]
    for point in file_graph["knowledge_points"]:
        assert point["support_pages"]["file-rag"]
        assert point["support_chunk_ids"]["file-rag"]


def test_payload_attr_includes_prompt_and_graph_context(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)

    payload = service._payload_attr(
        {
            "type": "knowledge_point",
            "label": "Evidence alignment",
            "related_file_ids": ["file-a"],
            "support_pages": {"file-a": ["2"]},
            "support_chunk_ids": {"file-a": ["chunk-2"]},
        },
        "file-a",
    )
    payload = json.loads(html.unescape(payload))

    assert "graph_context" in payload
    assert payload["graph_context"]["focus_file_id"] == "file-a"
    assert payload["node_label"] == "Evidence alignment"
    assert payload["prompt"]
    assert payload["suggested_question"]
    assert payload["node_role"] == "knowledge_point"
    assert payload["node_id"] == ""
    assert payload["suggested_question"] == (
        "Can you explain this knowledge point: 'Evidence alignment'?"
    )
    assert payload["fill_question"] == payload["suggested_question"]
    assert payload["prompt"] != payload["suggested_question"]


def test_render_graph_html_wraps_ready_graph_in_preview_card_and_viewer(
    monkeypatch, tmp_path
):
    service = _make_service(monkeypatch, tmp_path)

    graph = {
        "schema_version": 2,
        "source_ids": ["file-a", "file-b"],
        "maps": [
            {
                "id": "map::1",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Knowledge System 1",
                "summary": "Connected source set.",
                "related_file_ids": ["file-a", "file-b"],
                "component_ids": ["component::1"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
            }
        ],
        "components": [
            {
                "id": "component::1",
                "type": "component",
                "kind": "component",
                "label": "Component 1",
                "summary": "Shared concepts",
                "related_file_ids": ["file-a", "file-b"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
                "children": [],
            }
        ],
        "themes": [],
        "subthemes": [],
        "knowledge_points": [],
        "node_index": {
            "component::1": {
                "id": "component::1",
                "type": "component",
                "kind": "component",
                "label": "Component 1",
                "summary": "Shared concepts",
                "related_file_ids": ["file-a", "file-b"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
                "children": [],
            }
        },
        "support_pages": {"file-a": ["1"], "file-b": ["2"]},
        "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
    }

    rendered = service._render_graph_html(graph, focus_file_id="", status="ready")

    assert "kg-preview-card" in rendered
    assert "data-kg-open-viewer='true'" in rendered
    assert "kg-viewer-overlay" in rendered
    assert "kg-viewer-viewport" in rendered
    assert "kg-viewer-stage" in rendered
    assert "Component 1" in rendered


def test_render_graph_html_renders_flat_v2_map_branches(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)

    graph = {
        "schema_version": 2,
        "source_ids": ["file-a", "file-b"],
        "maps": [
            {
                "id": "map::1",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Knowledge System 1",
                "summary": "Connected source set.",
                "related_file_ids": ["file-a", "file-b"],
                "component_ids": ["component::1"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
            }
        ],
        "components": [
            {
                "id": "component::1",
                "type": "component",
                "kind": "component",
                "label": "Component 1",
                "summary": "Shared concepts",
                "related_file_ids": ["file-a", "file-b"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
                "children": ["theme::1"],
            }
        ],
        "themes": [
            {
                "id": "theme::1",
                "type": "theme",
                "kind": "theme",
                "label": "Theme 1",
                "summary": "Shared concepts",
                "related_file_ids": ["file-a", "file-b"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {
                    "file-a": ["chunk-a"],
                    "file-b": ["chunk-b"],
                },
                "component_id": "component::1",
                "parent_id": "component::1",
                "children": ["subtheme::1"],
            }
        ],
        "subthemes": [
            {
                "id": "subtheme::1",
                "type": "subtheme",
                "kind": "subtheme",
                "label": "Subtheme 1",
                "summary": "Focus details",
                "related_file_ids": ["file-a"],
                "support_pages": {"file-a": ["1"]},
                "support_chunk_ids": {"file-a": ["chunk-a"]},
                "component_id": "component::1",
                "theme_id": "theme::1",
                "parent_id": "theme::1",
                "children": ["point::1"],
            }
        ],
        "knowledge_points": [
            {
                "id": "point::1",
                "type": "knowledge_point",
                "kind": "knowledge_point",
                "label": "Point 1",
                "related_file_ids": ["file-a"],
                "file_id": "file-a",
                "component_id": "component::1",
                "theme_id": "theme::1",
                "subtheme_id": "subtheme::1",
                "parent_id": "subtheme::1",
                "support_pages": {"file-a": ["1"]},
                "support_chunk_ids": {"file-a": ["chunk-a"]},
            }
        ],
        "node_index": {
            "component::1": {
                "id": "component::1",
                "type": "component",
                "kind": "component",
                "label": "Component 1",
                "summary": "Shared concepts",
                "related_file_ids": ["file-a", "file-b"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
                "children": ["theme::1"],
            },
            "theme::1": {
                "id": "theme::1",
                "type": "theme",
                "kind": "theme",
                "label": "Theme 1",
                "summary": "Shared concepts",
                "related_file_ids": ["file-a", "file-b"],
                "support_pages": {"file-a": ["1"], "file-b": ["2"]},
                "support_chunk_ids": {
                    "file-a": ["chunk-a"],
                    "file-b": ["chunk-b"],
                },
                "component_id": "component::1",
                "parent_id": "component::1",
                "children": ["subtheme::1"],
            },
            "subtheme::1": {
                "id": "subtheme::1",
                "type": "subtheme",
                "kind": "subtheme",
                "label": "Subtheme 1",
                "summary": "Focus details",
                "related_file_ids": ["file-a"],
                "support_pages": {"file-a": ["1"]},
                "support_chunk_ids": {"file-a": ["chunk-a"]},
                "component_id": "component::1",
                "theme_id": "theme::1",
                "parent_id": "theme::1",
                "children": ["point::1"],
            },
            "point::1": {
                "id": "point::1",
                "type": "knowledge_point",
                "kind": "knowledge_point",
                "label": "Point 1",
                "related_file_ids": ["file-a"],
                "file_id": "file-a",
                "component_id": "component::1",
                "theme_id": "theme::1",
                "subtheme_id": "subtheme::1",
                "parent_id": "subtheme::1",
                "support_pages": {"file-a": ["1"]},
                "support_chunk_ids": {"file-a": ["chunk-a"]},
            },
        },
        "support_pages": {},
        "support_chunk_ids": {},
    }

    rendered = service._render_graph_html(graph, focus_file_id="", status="ready")

    assert "data-kg-layout='mindmap'" in rendered
    assert "data-kg-schema='v2'" in rendered
    assert "Conversation Knowledge Map" in rendered
    assert "Component 1" in rendered
    assert "Theme 1" in rendered
    assert "Subtheme 1" in rendered
    assert "Point 1" in rendered


def test_render_graph_html_shows_split_banner_for_multiple_maps(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)

    graph = {
        "schema_version": 2,
        "source_ids": ["file-a", "file-b"],
        "split_reason": "weakly_connected_sources",
        "maps": [
            {
                "id": "map::1",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Knowledge System 1",
                "summary": "Related sources A.",
                "related_file_ids": ["file-a"],
                "component_ids": [],
                "support_pages": {"file-a": ["1"]},
                "support_chunk_ids": {"file-a": ["chunk-a"]},
            },
            {
                "id": "map::2",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Knowledge System 2",
                "summary": "Related sources B.",
                "related_file_ids": ["file-b"],
                "component_ids": [],
                "support_pages": {"file-b": ["2"]},
                "support_chunk_ids": {"file-b": ["chunk-b"]},
            },
        ],
        "components": [],
        "themes": [],
        "subthemes": [],
        "knowledge_points": [],
        "node_index": {},
        "support_pages": {},
        "support_chunk_ids": {},
    }

    rendered = service._render_graph_html(graph, focus_file_id="", status="ready")

    assert "kg-map-split-banner" in rendered
    assert "split into 2 separate maps" in rendered


def test_render_graph_html_shows_split_summary_on_preview_card(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)

    graph = {
        "schema_version": 2,
        "source_ids": ["file-a", "file-b"],
        "split_reason": "weakly_connected_sources",
        "maps": [
            {
                "id": "map::1",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Map 1",
                "summary": "A",
                "related_file_ids": ["file-a"],
                "component_ids": [],
                "support_pages": {},
                "support_chunk_ids": {},
            },
            {
                "id": "map::2",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Map 2",
                "summary": "B",
                "related_file_ids": ["file-b"],
                "component_ids": [],
                "support_pages": {},
                "support_chunk_ids": {},
            },
        ],
        "components": [],
        "themes": [],
        "subthemes": [],
        "knowledge_points": [],
        "node_index": {},
        "support_pages": {},
        "support_chunk_ids": {},
    }

    rendered = service._render_graph_html(graph, focus_file_id="", status="ready")

    assert "kg-preview-card" in rendered
    assert "Split into 2 separate maps" in rendered


def test_render_empty_html_uses_non_interactive_preview_card(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)

    rendered = service._render_empty_html(
        "No graph available yet.",
        "Upload related sources to generate a map.",
    )

    assert "kg-preview-card" in rendered
    assert "data-kg-open-viewer='false'" in rendered
    assert "No graph available yet." in rendered


def test_conversation_graph_builds_schema_v2_theme_first_artifact(
    monkeypatch, tmp_path
):
    service = _make_service(monkeypatch, tmp_path)
    monkeypatch.setattr(
        service,
        "_build_file_graph",
        lambda file_id, source: {
            "file_id": file_id,
            "file_name": source["name"],
            "summary": f"Summary for {source['name']}",
            "summary_support_pages": {file_id: ["1"]},
            "summary_support_chunk_ids": {file_id: [f"{file_id}-chunk-summary"]},
            "top_keywords": {
                "file-a": ["rag", "retrieval", "grounding"],
                "file-b": ["rag", "retrieval", "citation"],
            }[file_id],
            "knowledge_points": [
                {
                    "id": f"point::{file_id}::1",
                    "type": "knowledge_point",
                    "file_id": file_id,
                    "label": f"Point for {source['name']}",
                    "keywords": ["rag", "retrieval"],
                    "related_file_ids": [file_id],
                    "support_pages": {file_id: ["1"]},
                    "support_chunk_ids": {file_id: [f"{file_id}-chunk-1"]},
                }
            ],
        },
    )

    graph = service._build_conversation_graph(
        "conv-v2",
        {
            "file-a": {"name": "Alpha.pdf"},
            "file-b": {"name": "Beta.pdf"},
        },
    )

    assert graph["schema_version"] == 2
    assert graph["root"]["id"] == "root::conversation"
    assert graph["maps"]
    assert graph["components"]
    assert graph["themes"]
    assert graph["node_index"]["root::conversation"]["kind"] == "root"
    assert graph["support_pages"]["file-a"] == ["1"]
    assert graph["support_chunk_ids"]["file-b"]


def test_get_graph_view_marks_legacy_cache_stale_even_when_manifest_matches(
    monkeypatch, tmp_path
):
    service = _make_service(monkeypatch, tmp_path)
    monkeypatch.setattr(
        service,
        "_load_sources",
        lambda source_ids: {
            "file-a": {
                "id": "file-a",
                "name": "Alpha.pdf",
                "path": "",
                "size": 1,
                "date_created": "2026-01-01",
            }
        },
    )
    manifest = {
        "file-a": "file-a|Alpha.pdf||1|2026-01-01",
    }
    monkeypatch.setattr(
        service,
        "_make_signature",
        lambda source: manifest[str(source["id"])],
    )
    monkeypatch.setattr(
        service,
        "_load_cached_state",
        lambda conversation_id: {
            "conversation_id": conversation_id,
            "manifest": manifest,
            "graph": {
                "conversation_id": conversation_id,
                "source_ids": ["file-a"],
                "systems": [],
                "file_cards": [],
                "knowledge_points": [],
                "support_pages": {},
                "support_chunk_ids": {},
            },
        },
    )

    graph_view = service.get_graph_view(
        "conv-cache",
        ["file-a"],
        focus_file_id="file-a",
        force_rebuild=False,
    )

    assert graph_view["status"] == "stale"
    assert "schema" in graph_view["status_message"].lower()


def test_get_graph_view_rebuilds_stale_graph_to_ready_when_forced(
    monkeypatch, tmp_path
):
    service = _make_service(monkeypatch, tmp_path)
    monkeypatch.setattr(
        service,
        "_load_sources",
        lambda source_ids: {
            "file-a": {
                "id": "file-a",
                "name": "Alpha.pdf",
                "path": "",
                "size": 1,
                "date_created": "2026-01-01",
            }
        },
    )

    stale_graph = {
        "conversation_id": "conv-stale",
        "source_ids": ["file-a"],
        "systems": [],
        "file_cards": [],
        "knowledge_points": [],
        "edges": [],
        "support_pages": {"file-a": ["old-page"]},
        "support_chunk_ids": {"file-a": ["old-chunk"]},
    }
    cached_manifest = {"file-a": "file-a|Alpha.pdf||1|2025-01-01"}
    monkeypatch.setattr(
        service,
        "_load_cached_state",
        lambda conversation_id: {
            "conversation_id": conversation_id,
            "manifest": cached_manifest,
            "graph": stale_graph,
        },
    )

    build_calls = []
    saved_states = []

    def _build_graph(conversation_id, sources):
        build_calls.append((conversation_id, sorted(sources.keys())))
        return {
            "conversation_id": conversation_id,
            "source_ids": list(sources.keys()),
            "systems": [
                {
                    "id": "system::1",
                    "type": "knowledge_system",
                    "label": "Shared knowledge system",
                    "summary": "Rebuilt from current sources.",
                    "related_file_ids": ["file-a"],
                    "support_pages": {"file-a": ["1"]},
                    "support_chunk_ids": {"file-a": ["chunk-1"]},
                    "themes": [],
                }
            ],
            "file_cards": [],
            "knowledge_points": [],
            "edges": [],
            "support_pages": {"file-a": ["1"]},
            "support_chunk_ids": {"file-a": ["chunk-1"]},
        }

    monkeypatch.setattr(service, "_build_conversation_graph", _build_graph)
    monkeypatch.setattr(
        service,
        "_save_cached_state",
        lambda conversation_id, state: saved_states.append((conversation_id, state)),
    )

    stale_view = service.get_graph_view(
        "conv-stale",
        ["file-a"],
        focus_file_id="file-a",
        force_rebuild=False,
    )
    assert stale_view["status"] == "stale"
    assert stale_view["graph"] == stale_graph
    assert build_calls == []

    ready_view = service.get_graph_view(
        "conv-stale",
        ["file-a"],
        focus_file_id="file-a",
        force_rebuild=True,
    )
    assert ready_view["status"] == "ready"
    assert ready_view["graph"]["systems"][0]["id"] == "system::1"
    assert ready_view["status_message"].startswith("Ready: 1 sources")
    assert build_calls == [("conv-stale", ["file-a"])]
    assert saved_states[-1][0] == "conv-stale"
    assert saved_states[-1][1]["manifest"] == {
        "file-a": "file-a|Alpha.pdf||1|2026-01-01",
    }
    assert saved_states[-1][1]["graph"] == ready_view["graph"]


def test_get_graph_view_ready_status_mentions_split_maps(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)
    monkeypatch.setattr(
        service,
        "_load_sources",
        lambda source_ids: {
            "file-a": {
                "id": "file-a",
                "name": "Alpha.pdf",
                "path": "",
                "size": 1,
                "date_created": "2026-01-01",
            },
            "file-b": {
                "id": "file-b",
                "name": "Beta.pdf",
                "path": "",
                "size": 1,
                "date_created": "2026-01-02",
            },
        },
    )
    monkeypatch.setattr(
        service,
        "_build_conversation_graph",
        lambda conversation_id, sources: {
            "schema_version": 2,
            "conversation_id": conversation_id,
            "source_ids": list(sources.keys()),
            "maps": [
                {
                    "id": "map::1",
                    "type": "knowledge_map",
                    "kind": "map",
                    "label": "Knowledge System 1",
                    "summary": "Map A",
                    "related_file_ids": ["file-a"],
                    "component_ids": [],
                    "support_pages": {"file-a": ["1"]},
                    "support_chunk_ids": {"file-a": ["chunk-a"]},
                },
                {
                    "id": "map::2",
                    "type": "knowledge_map",
                    "kind": "map",
                    "label": "Knowledge System 2",
                    "summary": "Map B",
                    "related_file_ids": ["file-b"],
                    "component_ids": [],
                    "support_pages": {"file-b": ["2"]},
                    "support_chunk_ids": {"file-b": ["chunk-b"]},
                },
            ],
            "components": [],
            "themes": [],
            "subthemes": [],
            "knowledge_points": [],
            "node_index": {},
            "systems": [],
            "file_cards": [],
            "support_pages": {"file-a": ["1"], "file-b": ["2"]},
            "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
            "split_reason": "weakly_connected_sources",
        },
    )

    graph_view = service.get_graph_view(
        "conv-split",
        ["file-a", "file-b"],
        focus_file_id="",
        force_rebuild=True,
    )

    assert graph_view["status"] == "ready"
    assert "split into 2 separate maps" in graph_view["status_message"].lower()


def test_payload_attr_keeps_graph_context_aliases_and_v2_node_metadata(
    monkeypatch, tmp_path
):
    service = _make_service(monkeypatch, tmp_path)

    payload = service._payload_attr(
        {
            "id": "component::1",
            "type": "knowledge_system",
            "kind": "component",
            "component_id": "component::1",
            "map_id": "map::1",
            "label": "Evidence alignment",
            "related_file_ids": ["file-a"],
            "support_pages": {"file-a": ["2"]},
            "support_chunk_ids": {"file-a": ["chunk-2"]},
        },
        "file-a",
    )
    payload = json.loads(html.unescape(payload))

    assert payload["graph_context"]["node_id"] == "component::1"
    assert payload["graph_context"]["node_role"] == "component"
    assert payload["graph_context"]["kind"] == "component"
    assert payload["graph_context"]["component_id"] == "component::1"
    assert payload["graph_context"]["map_id"] == "map::1"
    assert payload["node_role"] == "component"
    assert payload["node_type"] == "knowledge_system"
    assert payload["graph_context"]["focus_file_id"] == "file-a"
    assert payload["graph_context"]["support_pages"] == {"file-a": ["2"]}
    assert payload["graph_context"]["support_chunk_ids"] == {"file-a": ["chunk-2"]}
