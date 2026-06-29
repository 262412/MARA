from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CanonicalHierarchy:
    component_nodes: list[dict[str, Any]] = field(default_factory=list)
    theme_nodes: list[dict[str, Any]] = field(default_factory=list)
    subtheme_nodes: list[dict[str, Any]] = field(default_factory=list)
    canonical_points: list[dict[str, Any]] = field(default_factory=list)
    canonical_edges: list[dict[str, Any]] = field(default_factory=list)
    node_index: dict[str, dict[str, Any]] = field(default_factory=dict)

    def as_tuple(
        self,
    ) -> tuple[
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        list[dict[str, Any]],
        dict[str, dict[str, Any]],
    ]:
        return (
            self.component_nodes,
            self.theme_nodes,
            self.subtheme_nodes,
            self.canonical_points,
            self.canonical_edges,
            self.node_index,
        )

    def add_node(self, node: dict[str, Any], target: list[dict[str, Any]]) -> None:
        target.append(node)
        self.node_index[str(node["id"])] = node

    def add_edge(self, source: str, target: str, edge_type: str, node: dict) -> None:
        self.canonical_edges.append(
            {
                "source": source,
                "target": target,
                "type": edge_type,
                "related_file_ids": list(node.get("related_file_ids", [])),
            }
        )


def build_canonical_hierarchy(
    builder: Any,
    clusters: list[list[dict[str, Any]]],
    root_support_pages: dict[str, list[str]],
    root_support_chunk_ids: dict[str, list[str]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
]:
    hierarchy = CanonicalHierarchy()
    for component_index, cluster_points in enumerate(clusters, start=1):
        _add_component_branch(
            builder,
            hierarchy,
            component_index,
            cluster_points,
            root_support_pages,
            root_support_chunk_ids,
        )
    return hierarchy.as_tuple()


def _add_component_branch(
    builder: Any,
    hierarchy: CanonicalHierarchy,
    component_index: int,
    cluster_points: list[dict[str, Any]],
    root_support_pages: dict[str, list[str]],
    root_support_chunk_ids: dict[str, list[str]],
) -> None:
    component_node, support_pages, support_chunk_ids = builder._build_component_node(
        component_index, cluster_points
    )
    component_id = str(component_node["id"])
    hierarchy.add_node(component_node, hierarchy.component_nodes)
    builder._merge_support_dict(root_support_pages, support_pages, 24)
    builder._merge_support_dict(root_support_chunk_ids, support_chunk_ids, 36)

    theme_groups = builder._build_theme_groups(
        cluster_points, list(component_node.get("keywords", []))
    )
    component_label = str(component_node.get("label", ""))
    for theme_index, (theme_keyword, theme_points) in enumerate(theme_groups, start=1):
        _add_theme_branch(
            builder,
            hierarchy,
            component_index,
            theme_index,
            theme_keyword,
            theme_points,
            component_id,
            component_label,
            root_support_pages,
            root_support_chunk_ids,
        )


def _add_theme_branch(
    builder: Any,
    hierarchy: CanonicalHierarchy,
    component_index: int,
    theme_index: int,
    theme_keyword: str,
    theme_points: list[dict[str, Any]],
    component_id: str,
    component_label: str,
    root_support_pages: dict[str, list[str]],
    root_support_chunk_ids: dict[str, list[str]],
) -> None:
    theme_id, theme_node, support_pages, support_chunk_ids = builder._build_theme_node(
        component_index,
        theme_index,
        theme_keyword,
        theme_points,
        component_id,
        component_label,
    )
    hierarchy.add_node(theme_node, hierarchy.theme_nodes)
    hierarchy.node_index[component_id]["children"].append(theme_id)
    hierarchy.add_edge(component_id, theme_id, "component_theme", theme_node)
    builder._merge_support_dict(root_support_pages, support_pages, 24)
    builder._merge_support_dict(root_support_chunk_ids, support_chunk_ids, 36)

    for subtheme_index, (signature, subtheme_points) in enumerate(
        builder._sorted_subtheme_groups(theme_points, theme_keyword),
        start=1,
    ):
        _add_subtheme_branch(
            builder,
            hierarchy,
            component_index,
            theme_index,
            subtheme_index,
            signature,
            subtheme_points,
            component_id,
            theme_id,
            str(theme_node.get("label", "")),
            root_support_pages,
            root_support_chunk_ids,
        )


def _add_subtheme_branch(
    builder: Any,
    hierarchy: CanonicalHierarchy,
    component_index: int,
    theme_index: int,
    subtheme_index: int,
    signature: tuple[str, str],
    subtheme_points: list[dict[str, Any]],
    component_id: str,
    theme_id: str,
    theme_label: str,
    root_support_pages: dict[str, list[str]],
    root_support_chunk_ids: dict[str, list[str]],
) -> None:
    (
        subtheme_id,
        subtheme_node,
        support_pages,
        support_chunk_ids,
    ) = builder._build_subtheme_node(
        component_index,
        theme_index,
        subtheme_index,
        signature,
        subtheme_points,
        component_id,
        theme_id,
        theme_label,
    )
    hierarchy.add_node(subtheme_node, hierarchy.subtheme_nodes)
    hierarchy.node_index[theme_id]["children"].append(subtheme_id)
    hierarchy.add_edge(theme_id, subtheme_id, "theme_subtheme", subtheme_node)
    builder._merge_support_dict(root_support_pages, support_pages, 24)
    builder._merge_support_dict(root_support_chunk_ids, support_chunk_ids, 36)

    for point in subtheme_points:
        _add_point_node(
            builder,
            hierarchy,
            point,
            component_id,
            theme_id,
            subtheme_id,
            component_index,
            root_support_pages,
            root_support_chunk_ids,
        )


def _add_point_node(
    builder: Any,
    hierarchy: CanonicalHierarchy,
    point: dict[str, Any],
    component_id: str,
    theme_id: str,
    subtheme_id: str,
    component_index: int,
    root_support_pages: dict[str, list[str]],
    root_support_chunk_ids: dict[str, list[str]],
) -> None:
    point_node = builder._build_canonical_point_node(
        point, component_id, theme_id, subtheme_id, component_index
    )
    hierarchy.add_node(point_node, hierarchy.canonical_points)
    hierarchy.node_index[subtheme_id]["children"].append(point_node["id"])
    hierarchy.add_edge(subtheme_id, point_node["id"], "subtheme_point", point_node)
    builder._merge_support_dict(root_support_pages, point.get("support_pages", {}), 24)
    builder._merge_support_dict(
        root_support_chunk_ids, point.get("support_chunk_ids", {}), 36
    )
