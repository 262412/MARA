from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


def build_legacy_graph_artifacts(
    file_graphs: list[dict[str, Any]],
    component_nodes: list[dict[str, Any]],
    theme_nodes: list[dict[str, Any]],
    canonical_points: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    component_to_legacy_system_id = {
        component["id"]: f"system::{index}"
        for index, component in enumerate(component_nodes, start=1)
    }
    component_to_theme_nodes = _group_by_component(theme_nodes)
    component_by_id = {str(component["id"]): component for component in component_nodes}
    component_order = {
        str(component["id"]): index for index, component in enumerate(component_nodes)
    }
    file_primary_component = _primary_components_by_file(
        file_graphs, canonical_points, component_nodes, component_order
    )

    legacy_systems, legacy_edges = _build_legacy_systems(
        component_nodes, component_to_theme_nodes, component_to_legacy_system_id
    )
    legacy_file_cards = _build_legacy_file_cards(
        file_graphs,
        component_nodes,
        component_by_id,
        component_to_legacy_system_id,
        file_primary_component,
        legacy_edges,
    )
    _append_legacy_point_edges(
        canonical_points,
        component_to_legacy_system_id,
        legacy_edges,
    )
    return legacy_systems, legacy_file_cards, legacy_edges


def _group_by_component(
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in items:
        grouped[str(item.get("component_id", ""))].append(item)
    return grouped


def _primary_components_by_file(
    file_graphs: list[dict[str, Any]],
    canonical_points: list[dict[str, Any]],
    component_nodes: list[dict[str, Any]],
    component_order: dict[str, int],
) -> dict[str, str]:
    primary_components: dict[str, str] = {}
    fallback_component_id = component_nodes[0]["id"]
    for file_graph in file_graphs:
        file_id = str(file_graph.get("file_id", "") or "")
        candidate_points = [
            point for point in canonical_points if point.get("file_id") == file_id
        ]
        if candidate_points:
            primary_components[file_id] = _select_primary_component(
                candidate_points, component_order
            )
        else:
            primary_components[file_id] = fallback_component_id
    return primary_components


def _select_primary_component(
    candidate_points: list[dict[str, Any]], component_order: dict[str, int]
) -> str:
    component_counts: Counter[str] = Counter(
        str(point.get("component_id", "")) for point in candidate_points
    )
    return max(
        component_counts.items(),
        key=lambda item: (item[1], -component_order.get(item[0], 10**9)),
    )[0]


def _build_legacy_systems(
    component_nodes: list[dict[str, Any]],
    component_to_theme_nodes: dict[str, list[dict[str, Any]]],
    component_to_legacy_system_id: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    legacy_systems: list[dict[str, Any]] = []
    legacy_edges: list[dict[str, Any]] = []
    for component_node in component_nodes:
        component_id = str(component_node["id"])
        legacy_system_id = component_to_legacy_system_id[component_id]
        legacy_themes = _legacy_themes_for_component(
            component_id,
            legacy_system_id,
            component_to_theme_nodes.get(component_id, []),
            legacy_edges,
        )
        legacy_systems.append(
            {
                "id": legacy_system_id,
                "type": "knowledge_system",
                "kind": "system",
                "component_id": component_id,
                "label": component_node.get("label", ""),
                "summary": component_node.get("summary", ""),
                "related_file_ids": list(component_node.get("related_file_ids", [])),
                "shared_keywords": list(component_node.get("keywords", [])),
                "support_pages": component_node.get("support_pages", {}),
                "support_chunk_ids": component_node.get("support_chunk_ids", {}),
                "themes": legacy_themes,
            }
        )
    return legacy_systems, legacy_edges


def _legacy_themes_for_component(
    component_id: str,
    legacy_system_id: str,
    theme_nodes: list[dict[str, Any]],
    legacy_edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    legacy_themes = []
    for theme_node in theme_nodes:
        legacy_theme = {
            "id": str(theme_node["id"]),
            "type": "system_relation",
            "label": theme_node.get("label", ""),
            "summary": theme_node.get("summary", ""),
            "related_file_ids": list(theme_node.get("related_file_ids", [])),
            "support_pages": theme_node.get("support_pages", {}),
            "support_chunk_ids": theme_node.get("support_chunk_ids", {}),
            "component_id": component_id,
        }
        legacy_themes.append(legacy_theme)
        legacy_edges.append(
            {
                "source": legacy_system_id,
                "target": legacy_theme["id"],
                "type": "system_theme",
                "related_file_ids": list(legacy_theme.get("related_file_ids", [])),
            }
        )
    return legacy_themes


def _build_legacy_file_cards(
    file_graphs: list[dict[str, Any]],
    component_nodes: list[dict[str, Any]],
    component_by_id: dict[str, dict[str, Any]],
    component_to_legacy_system_id: dict[str, str],
    file_primary_component: dict[str, str],
    legacy_edges: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    legacy_file_cards = []
    fallback_component_id = component_nodes[0]["id"]
    for file_graph in file_graphs:
        file_id = str(file_graph.get("file_id", "") or "")
        primary_component_id = file_primary_component.get(
            file_id, fallback_component_id
        )
        legacy_system_id = component_to_legacy_system_id[primary_component_id]
        component = component_by_id[primary_component_id]
        file_card = {
            "id": f"file::{file_id}",
            "type": "file_summary",
            "kind": "file_summary",
            "system_id": legacy_system_id,
            "component_id": primary_component_id,
            "file_id": file_id,
            "label": file_graph.get("file_name", file_id),
            "summary": file_graph.get("summary", ""),
            "related_file_ids": list(component.get("related_file_ids", [])),
            "support_pages": file_graph.get("summary_support_pages", {}),
            "support_chunk_ids": file_graph.get("summary_support_chunk_ids", {}),
            "top_keywords": list(file_graph.get("top_keywords", []) or [])[:6],
        }
        legacy_file_cards.append(file_card)
        legacy_edges.append(
            {
                "source": legacy_system_id,
                "target": file_card["id"],
                "type": "system_file",
                "related_file_ids": list(file_card.get("related_file_ids", [])),
            }
        )
    return legacy_file_cards


def _append_legacy_point_edges(
    canonical_points: list[dict[str, Any]],
    component_to_legacy_system_id: dict[str, str],
    legacy_edges: list[dict[str, Any]],
) -> None:
    for point_node in canonical_points:
        component_id = str(point_node.get("component_id", ""))
        legacy_system_id = component_to_legacy_system_id.get(component_id, "system::1")
        legacy_point = dict(point_node)
        legacy_point["system_id"] = legacy_system_id
        legacy_point["type"] = "knowledge_point"
        legacy_point["kind"] = "knowledge_point"
        legacy_edges.append(
            {
                "source": f"file::{legacy_point.get('file_id', '')}",
                "target": legacy_point["id"],
                "type": "file_point",
                "related_file_ids": [legacy_point.get("file_id", "")],
            }
        )
