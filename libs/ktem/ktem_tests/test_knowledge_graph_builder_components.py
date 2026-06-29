from ktem.pages.chat.knowledge_graph_hierarchy_builder import build_canonical_hierarchy
from ktem.pages.chat.knowledge_graph_legacy_builder import build_legacy_graph_artifacts
from ktem.pages.chat.knowledge_graph_map_builder import build_knowledge_maps
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


def _point(point_id, file_id, label, keywords):
    return {
        "id": point_id,
        "file_id": file_id,
        "file_name": f"{file_id}.pdf",
        "label": label,
        "keywords": keywords,
        "summary": label,
        "support_pages": {file_id: ["1"]},
        "support_chunk_ids": {file_id: [f"{file_id}-chunk"]},
    }


def _file_graph(file_id, file_name, keywords):
    return {
        "file_id": file_id,
        "file_name": file_name,
        "summary": f"Summary for {file_name}",
        "summary_support_pages": {file_id: ["1"]},
        "summary_support_chunk_ids": {file_id: [f"{file_id}-summary"]},
        "top_keywords": keywords,
        "knowledge_points": [],
    }


def test_phase4b_canonical_hierarchy_builder_preserves_node_shape(
    monkeypatch, tmp_path
):
    service = _make_service(monkeypatch, tmp_path)
    root_support_pages: dict[str, list[str]] = {}
    root_support_chunk_ids: dict[str, list[str]] = {}

    (
        component_nodes,
        theme_nodes,
        subtheme_nodes,
        canonical_points,
        canonical_edges,
        node_index,
    ) = build_canonical_hierarchy(
        service._builder,
        [
            [
                _point("point::file-a::1", "file-a", "Alpha retrieval", ["rag"]),
                _point("point::file-b::1", "file-b", "Beta citation", ["rag"]),
            ]
        ],
        root_support_pages,
        root_support_chunk_ids,
    )

    assert [component["id"] for component in component_nodes] == ["component::1"]
    assert theme_nodes[0]["component_id"] == "component::1"
    assert subtheme_nodes[0]["theme_id"] == theme_nodes[0]["id"]
    assert {point["file_id"] for point in canonical_points} == {"file-a", "file-b"}
    assert {edge["type"] for edge in canonical_edges} >= {
        "component_theme",
        "theme_subtheme",
        "subtheme_point",
    }
    assert node_index["component::1"] is component_nodes[0]
    assert root_support_pages["file-a"] == ["1"]
    assert root_support_chunk_ids["file-b"] == ["file-b-chunk"]


def test_phase4b_legacy_builder_preserves_compatibility_artifacts():
    component_nodes = [
        {
            "id": "component::1",
            "label": "Retrieval",
            "summary": "Retrieval component",
            "related_file_ids": ["file-a", "file-b"],
            "keywords": ["rag"],
            "support_pages": {"file-a": ["1"]},
            "support_chunk_ids": {"file-a": ["file-a-chunk"]},
        }
    ]
    theme_nodes = [
        {
            "id": "theme::1::1",
            "component_id": "component::1",
            "label": "RAG",
            "summary": "RAG theme",
            "related_file_ids": ["file-a"],
            "support_pages": {"file-a": ["1"]},
            "support_chunk_ids": {"file-a": ["file-a-chunk"]},
        }
    ]
    canonical_points = [
        {
            "id": "point::file-a::1",
            "component_id": "component::1",
            "file_id": "file-a",
            "label": "Alpha point",
        }
    ]
    file_graphs = [_file_graph("file-a", "Alpha.pdf", ["rag"])]

    legacy_systems, legacy_file_cards, legacy_edges = build_legacy_graph_artifacts(
        file_graphs, component_nodes, theme_nodes, canonical_points
    )

    assert legacy_systems[0]["id"] == "system::1"
    assert legacy_systems[0]["themes"][0]["id"] == "theme::1::1"
    assert legacy_file_cards[0]["system_id"] == "system::1"
    assert legacy_file_cards[0]["component_id"] == "component::1"
    assert [edge["type"] for edge in legacy_edges] == [
        "system_theme",
        "system_file",
        "file_point",
    ]


def test_phase4b_map_builder_assigns_components_and_support(monkeypatch, tmp_path):
    service = _make_service(monkeypatch, tmp_path)
    file_graphs = [
        _file_graph("file-a", "Alpha.pdf", ["rag", "retrieval"]),
        _file_graph("file-b", "Beta.pdf", ["rag", "retrieval"]),
    ]
    component_nodes = [
        {
            "id": "component::1",
            "related_file_ids": ["file-a", "file-b"],
            "support_pages": {"file-a": ["1"]},
            "support_chunk_ids": {"file-b": ["file-b-chunk"]},
        }
    ]
    theme_nodes = [{"id": "theme::1::1", "component_id": "component::1"}]
    subtheme_nodes = [{"id": "subtheme::1::1::1", "component_id": "component::1"}]
    canonical_points = [{"id": "point::file-a::1", "component_id": "component::1"}]
    node_index: dict[str, dict] = {}

    maps, map_ids = build_knowledge_maps(
        service._builder,
        file_graphs,
        component_nodes,
        theme_nodes,
        subtheme_nodes,
        canonical_points,
        ["point::file-a::1"],
        node_index,
    )

    assert map_ids == ["map::1"]
    assert maps[0]["component_ids"] == ["component::1"]
    assert maps[0]["support_pages"] == {"file-a": ["1"]}
    assert component_nodes[0]["map_id"] == "map::1"
    assert theme_nodes[0]["map_id"] == "map::1"
    assert subtheme_nodes[0]["map_id"] == "map::1"
    assert canonical_points[0]["map_id"] == "map::1"
    assert node_index["map::1"] is maps[0]
