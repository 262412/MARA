from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .knowledge_graph_file_builder import build_file_graph as build_file_knowledge_graph
from .knowledge_graph_hierarchy_builder import (
    build_canonical_hierarchy as build_canonical_hierarchy_nodes,
)
from .knowledge_graph_legacy_builder import (
    build_legacy_graph_artifacts as build_legacy_graph_artifacts_data,
)
from .knowledge_graph_map_builder import (
    build_knowledge_maps as build_knowledge_map_nodes,
)


def _limit_unique_strings(values: list[str], limit: int) -> list[str]:
    seen = set()
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)
        if len(output) >= limit:
            break
    return output


class _UnionFind:
    def __init__(self, values: list[str]):
        self.parent = {value: value for value in values}

    def find(self, value: str) -> str:
        parent = self.parent.get(value, value)
        if parent != value:
            parent = self.find(parent)
            self.parent[value] = parent
        return parent

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root != right_root:
            self.parent[right_root] = left_root


class KnowledgeGraphBuilder:
    SCHEMA_VERSION = 2

    def __init__(self, service):
        self._service = service

    @staticmethod
    def _build_support_bundle(
        support_pages: dict[str, list[str]] | None,
        support_chunk_ids: dict[str, list[str]] | None,
        page_limit: int,
        chunk_limit: int,
    ) -> dict[str, dict[str, list[str]]]:
        pages = {
            str(file_id or "").strip(): _limit_unique_strings(
                list(values or []), page_limit
            )
            for file_id, values in (support_pages or {}).items()
            if str(file_id or "").strip()
        }
        chunks = {
            str(file_id or "").strip(): _limit_unique_strings(
                list(values or []), chunk_limit
            )
            for file_id, values in (support_chunk_ids or {}).items()
            if str(file_id or "").strip()
        }
        return {
            "support_pages": pages,
            "support_chunk_ids": chunks,
            "evidence_pages": {
                file_id: list(values) for file_id, values in pages.items()
            },
            "evidence_chunk_ids": {
                file_id: list(values) for file_id, values in chunks.items()
            },
        }

    def _annotate_evidence_aliases(
        self,
        node: dict[str, Any],
        support_pages: dict[str, list[str]] | None,
        support_chunk_ids: dict[str, list[str]] | None,
        page_limit: int = 24,
        chunk_limit: int = 36,
    ) -> dict[str, Any]:
        node.update(
            self._build_support_bundle(
                support_pages, support_chunk_ids, page_limit, chunk_limit
            )
        )
        return node

    @staticmethod
    def _sorted_unique_keywords(
        points: list[dict[str, Any]], limit: int = 8
    ) -> list[str]:
        counter: Counter[str] = Counter()
        display_names: dict[str, str] = {}
        for point in points:
            for keyword in point.get("keywords", []):
                normalized = str(keyword or "").strip().lower()
                if not normalized:
                    continue
                counter[normalized] += 1
                display_names.setdefault(normalized, str(keyword or "").strip())
        ordered = []
        for keyword, _ in counter.most_common(limit):
            ordered.append(display_names.get(keyword, keyword))
        return _limit_unique_strings(ordered, limit)

    def _cluster_points(
        self, point_records: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        if not point_records:
            return []

        union_find = _UnionFind([point["id"] for point in point_records])
        keyword_sets = {
            point["id"]: {
                str(keyword or "").strip().lower()
                for keyword in point.get("keywords", [])
                if str(keyword or "").strip()
            }
            for point in point_records
        }

        for index, left_point in enumerate(point_records):
            left_keywords = keyword_sets.get(left_point["id"], set())
            for right_point in point_records[index + 1 :]:
                shared = left_keywords.intersection(
                    keyword_sets.get(right_point["id"], set())
                )
                if shared:
                    union_find.union(left_point["id"], right_point["id"])

        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for point in point_records:
            grouped[union_find.find(point["id"])].append(point)

        ordered_clusters = list(grouped.values())
        for cluster in ordered_clusters:
            cluster.sort(
                key=lambda item: (
                    -len(item.get("keywords", [])),
                    str(item.get("label", "")).lower(),
                )
            )
        ordered_clusters.sort(
            key=lambda cluster: (
                -len(cluster),
                str(cluster[0].get("label", "")).lower(),
            )
        )
        return ordered_clusters

    def _make_subtheme_signature(
        self, point: dict[str, Any], theme_keyword: str
    ) -> tuple[str, str]:
        normalized_keywords = [
            self._service._normalize_term(keyword)
            for keyword in point.get("keywords", [])
        ]
        normalized_keywords = [keyword for keyword in normalized_keywords if keyword]
        if len(normalized_keywords) >= 2:
            return normalized_keywords[0], normalized_keywords[1]
        if normalized_keywords:
            label_prefix = self._service._normalize_term(
                " ".join(str(point.get("label", "") or "").split()[:4])
            )
            return normalized_keywords[0], label_prefix or theme_keyword
        label_prefix = self._service._normalize_term(
            " ".join(str(point.get("label", "") or "").split()[:4])
        )
        return theme_keyword, label_prefix or theme_keyword

    def _collect_canonical_point_records(
        self, file_graphs: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], dict[str, list[str]], dict[str, list[str]]]:
        root_support_pages: dict[str, list[str]] = {}
        root_support_chunk_ids: dict[str, list[str]] = {}
        point_records: list[dict[str, Any]] = []

        for file_graph in file_graphs:
            file_id = str(file_graph.get("file_id", "") or "")
            file_name = str(file_graph.get("file_name", file_id) or file_id)
            file_keywords = list(file_graph.get("top_keywords", []) or [])
            for index, point in enumerate(
                file_graph.get("knowledge_points", []) or [], start=1
            ):
                point_id = str(point.get("id", "") or f"point::{file_id}::{index}")
                label = str(point.get("label", "") or "").strip()
                keywords = _limit_unique_strings(
                    list(point.get("keywords", []) or []) + file_keywords[:2],
                    8,
                )
                point_records.append(
                    {
                        "id": point_id,
                        "file_id": file_id,
                        "file_name": file_name,
                        "label": label,
                        "keywords": keywords,
                        "summary": label,
                        "support_pages": point.get("support_pages", {}) or {},
                        "support_chunk_ids": point.get("support_chunk_ids", {}) or {},
                    }
                )

            self._merge_support_dict(
                root_support_pages, file_graph.get("summary_support_pages", {}), 24
            )
            self._merge_support_dict(
                root_support_chunk_ids,
                file_graph.get("summary_support_chunk_ids", {}),
                36,
            )

        return point_records, root_support_pages, root_support_chunk_ids

    def _append_synthetic_point_records(
        self,
        point_records: list[dict[str, Any]],
        file_graphs: list[dict[str, Any]],
    ) -> None:
        for file_graph in file_graphs:
            file_id = str(file_graph.get("file_id", "") or "")
            file_name = str(file_graph.get("file_name", file_id) or file_id)
            synthetic_label = self._service._trim_sentence(
                str(file_graph.get("summary", "") or file_name), 110
            )
            synthetic_keywords = _limit_unique_strings(
                list(file_graph.get("top_keywords", []) or [])
                + self._service._extract_keywords(synthetic_label, limit=4),
                6,
            )
            point_records.append(
                {
                    "id": f"point::{file_id}::summary",
                    "file_id": file_id,
                    "file_name": file_name,
                    "label": synthetic_label,
                    "keywords": synthetic_keywords,
                    "summary": synthetic_label,
                    "support_pages": file_graph.get("summary_support_pages", {}) or {},
                    "support_chunk_ids": file_graph.get("summary_support_chunk_ids", {})
                    or {},
                    "synthetic": True,
                }
            )

    def _collect_item_support(
        self, items: list[dict[str, Any]]
    ) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
        support_pages: dict[str, list[str]] = {}
        support_chunk_ids: dict[str, list[str]] = {}
        for item in items:
            self._merge_support_dict(support_pages, item.get("support_pages", {}), 24)
            self._merge_support_dict(
                support_chunk_ids, item.get("support_chunk_ids", {}), 36
            )
        return support_pages, support_chunk_ids

    def _build_component_node(
        self, component_index: int, cluster_points: list[dict[str, Any]]
    ) -> tuple[dict[str, Any], dict[str, list[str]], dict[str, list[str]]]:
        component_id = f"component::{component_index}"
        component_keywords = self._sorted_unique_keywords(cluster_points, limit=6)
        related_file_ids = _limit_unique_strings(
            [point["file_id"] for point in cluster_points], 24
        )
        representative_point = cluster_points[0]
        component_label = self._service._trim_sentence(
            representative_point.get("label", ""), 96
        )
        if not component_label:
            component_label = (
                " / ".join(component_keywords[:2])
                if component_keywords
                else "Conversation component"
            )
        component_summary = (
            f"Theme cluster centered on {component_label} across "
            f"{len(related_file_ids)} source(s)."
        )

        (
            component_support_pages,
            component_support_chunk_ids,
        ) = self._collect_item_support(cluster_points)
        component_node = self._annotate_evidence_aliases(
            {
                "id": component_id,
                "type": "component",
                "kind": "component",
                "schema_version": self.SCHEMA_VERSION,
                "label": component_label,
                "summary": component_summary,
                "related_file_ids": related_file_ids,
                "keywords": component_keywords,
                "children": [],
            },
            component_support_pages,
            component_support_chunk_ids,
        )
        return component_node, component_support_pages, component_support_chunk_ids

    def _build_theme_groups(
        self,
        cluster_points: list[dict[str, Any]],
        component_keywords: list[str],
    ) -> list[tuple[str, list[dict[str, Any]]]]:
        keyword_to_points: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for point in cluster_points:
            normalized_keywords = [
                self._service._normalize_term(keyword)
                for keyword in point.get("keywords", [])
            ]
            normalized_keywords = [
                keyword for keyword in normalized_keywords if keyword
            ]
            primary_keyword = normalized_keywords[0] if normalized_keywords else ""
            if primary_keyword:
                keyword_to_points[primary_keyword].append(point)
            else:
                keyword_to_points["__general__"].append(point)

        ordered_theme_keys = _limit_unique_strings(
            [keyword for keyword in component_keywords if keyword], 4
        )
        if (
            "__general__" in keyword_to_points
            and "__general__" not in ordered_theme_keys
        ):
            ordered_theme_keys.append("__general__")

        assigned_point_ids: set[str] = set()
        theme_groups: list[tuple[str, list[dict[str, Any]]]] = []
        for keyword in ordered_theme_keys:
            group_points = [
                point
                for point in keyword_to_points.get(keyword, [])
                if point["id"] not in assigned_point_ids
            ]
            if group_points:
                theme_groups.append((keyword, group_points))
                assigned_point_ids.update(point["id"] for point in group_points)

        remaining_points = [
            point for point in cluster_points if point["id"] not in assigned_point_ids
        ]
        if remaining_points:
            fallback_keyword = (
                component_keywords[0] if component_keywords else "general"
            )
            theme_groups.append((fallback_keyword, remaining_points))

        return theme_groups

    def _build_theme_node(
        self,
        component_index: int,
        theme_index: int,
        theme_keyword: str,
        theme_points: list[dict[str, Any]],
        component_id: str,
        component_label: str,
    ) -> tuple[str, dict[str, Any], dict[str, list[str]], dict[str, list[str]]]:
        theme_id = f"theme::{component_index}::{theme_index}"
        theme_keywords = self._sorted_unique_keywords(theme_points, limit=4)
        theme_label = theme_keyword
        if theme_label == "__general__":
            theme_label = (
                self._service._trim_sentence(theme_points[0].get("label", ""), 84)
                if theme_points
                else "General theme"
            )
        elif len(theme_points) == 1:
            theme_label = (
                self._service._trim_sentence(theme_points[0].get("label", ""), 84)
                or theme_keyword
            )
        theme_summary = f"Theme around {theme_label} within {component_label}."

        theme_support_pages, theme_support_chunk_ids = self._collect_item_support(
            theme_points
        )
        theme_node = self._annotate_evidence_aliases(
            {
                "id": theme_id,
                "type": "theme",
                "kind": "theme",
                "schema_version": self.SCHEMA_VERSION,
                "label": theme_label,
                "summary": theme_summary,
                "related_file_ids": _limit_unique_strings(
                    [point["file_id"] for point in theme_points], 24
                ),
                "keywords": theme_keywords,
                "component_id": component_id,
                "children": [],
                "parent_id": component_id,
            },
            theme_support_pages,
            theme_support_chunk_ids,
        )
        return theme_id, theme_node, theme_support_pages, theme_support_chunk_ids

    def _sorted_subtheme_groups(
        self, theme_points: list[dict[str, Any]], theme_keyword: str
    ) -> list[tuple[tuple[str, str], list[dict[str, Any]]]]:
        subtheme_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for point in theme_points:
            signature = self._make_subtheme_signature(point, theme_keyword)
            subtheme_groups[signature].append(point)
        return sorted(
            subtheme_groups.items(),
            key=lambda item: (
                -len(item[1]),
                item[1][0].get("label", "").lower(),
            ),
        )

    def _build_subtheme_node(
        self,
        component_index: int,
        theme_index: int,
        subtheme_index: int,
        signature: tuple[str, str],
        subtheme_points: list[dict[str, Any]],
        component_id: str,
        theme_id: str,
        theme_label: str,
    ) -> tuple[str, dict[str, Any], dict[str, list[str]], dict[str, list[str]]]:
        subtheme_id = f"subtheme::{component_index}::{theme_index}::{subtheme_index}"
        subtheme_keywords = self._sorted_unique_keywords(subtheme_points, limit=4)
        subtheme_label = (
            self._service._trim_sentence(
                max(
                    (point.get("label", "") for point in subtheme_points),
                    key=len,
                    default="",
                ),
                84,
            )
            or " / ".join([value for value in signature if value])
            or theme_label
        )
        subtheme_summary = (
            f"Subtheme connecting {len(subtheme_points)} knowledge point(s) "
            f"under {theme_label}."
        )
        subtheme_support_pages, subtheme_support_chunk_ids = self._collect_item_support(
            subtheme_points
        )
        subtheme_node = self._annotate_evidence_aliases(
            {
                "id": subtheme_id,
                "type": "subtheme",
                "kind": "subtheme",
                "schema_version": self.SCHEMA_VERSION,
                "label": subtheme_label,
                "summary": subtheme_summary,
                "related_file_ids": _limit_unique_strings(
                    [point["file_id"] for point in subtheme_points], 24
                ),
                "keywords": subtheme_keywords,
                "component_id": component_id,
                "theme_id": theme_id,
                "children": [],
                "parent_id": theme_id,
            },
            subtheme_support_pages,
            subtheme_support_chunk_ids,
        )
        return (
            subtheme_id,
            subtheme_node,
            subtheme_support_pages,
            subtheme_support_chunk_ids,
        )

    def _build_canonical_point_node(
        self,
        point: dict[str, Any],
        component_id: str,
        theme_id: str,
        subtheme_id: str,
        component_index: int,
    ) -> dict[str, Any]:
        point_node = dict(point)
        point_node.update(
            {
                "type": "knowledge_point",
                "kind": "knowledge_point",
                "schema_version": self.SCHEMA_VERSION,
                "component_id": component_id,
                "theme_id": theme_id,
                "subtheme_id": subtheme_id,
                "parent_id": subtheme_id,
                "children": [],
                "related_file_ids": [point["file_id"]],
                "file_id": point["file_id"],
                "system_id": f"system::{component_index}",
            }
        )
        self._annotate_evidence_aliases(
            point_node,
            point.get("support_pages", {}),
            point.get("support_chunk_ids", {}),
            8,
            8,
        )
        return point_node

    def _build_canonical_hierarchy(
        self,
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
        return build_canonical_hierarchy_nodes(
            self, clusters, root_support_pages, root_support_chunk_ids
        )

    def _build_empty_canonical_graph(
        self,
        conversation_id: str,
        sources: dict[str, dict[str, Any]],
        node_index: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        empty_root_support = self._build_support_bundle({}, {}, 24, 36)
        root_node_id = "root::conversation"
        root_node = {
            "id": root_node_id,
            "type": "knowledge_root",
            "kind": "root",
            "schema_version": self.SCHEMA_VERSION,
            "label": "Conversation Knowledge Map",
            "summary": "No thematic structure could be derived yet.",
            "related_file_ids": list(sources.keys()),
            "children": [],
            "component_ids": [],
            "theme_ids": [],
            "subtheme_ids": [],
            "point_ids": [],
            **empty_root_support,
        }
        node_index[root_node_id] = root_node
        legacy_graph: dict[str, list[dict[str, Any]]] = {
            "systems": [],
            "file_cards": [],
            "knowledge_points": [],
            "legacy_edges": [],
        }
        return {
            "schema_version": self.SCHEMA_VERSION,
            "conversation_id": conversation_id,
            "source_ids": list(sources.keys()),
            "root": root_node,
            "maps": [],
            "components": [],
            "themes": [],
            "subthemes": [],
            "knowledge_points": [],
            "edges": [],
            "node_index": node_index,
            "support_pages": {},
            "support_chunk_ids": {},
            "evidence_pages": {},
            "evidence_chunk_ids": {},
            "split_reason": "",
            **legacy_graph,
        }

    def _build_legacy_graph_artifacts(
        self,
        file_graphs: list[dict[str, Any]],
        component_nodes: list[dict[str, Any]],
        theme_nodes: list[dict[str, Any]],
        canonical_points: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        return build_legacy_graph_artifacts_data(
            file_graphs, component_nodes, theme_nodes, canonical_points
        )

    def _build_knowledge_maps(
        self,
        file_graphs: list[dict[str, Any]],
        component_nodes: list[dict[str, Any]],
        theme_nodes: list[dict[str, Any]],
        subtheme_nodes: list[dict[str, Any]],
        canonical_points: list[dict[str, Any]],
        root_point_ids: list[str],
        node_index: dict[str, dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        return build_knowledge_map_nodes(
            self,
            file_graphs,
            component_nodes,
            theme_nodes,
            subtheme_nodes,
            canonical_points,
            root_point_ids,
            node_index,
            _limit_unique_strings,
        )

    def _build_root_node(
        self,
        sources: dict[str, dict[str, Any]],
        component_nodes: list[dict[str, Any]],
        theme_nodes: list[dict[str, Any]],
        subtheme_nodes: list[dict[str, Any]],
        canonical_points: list[dict[str, Any]],
        maps: list[dict[str, Any]],
        map_ids: list[str],
        root_support_pages: dict[str, list[str]],
        root_support_chunk_ids: dict[str, list[str]],
    ) -> dict[str, Any]:
        root_children = [component["id"] for component in component_nodes]
        root_theme_ids = [theme["id"] for theme in theme_nodes]
        root_subtheme_ids = [subtheme["id"] for subtheme in subtheme_nodes]
        root_point_ids = [point["id"] for point in canonical_points]
        root_node_id = "root::conversation"
        return self._annotate_evidence_aliases(
            {
                "id": root_node_id,
                "type": "knowledge_root",
                "kind": "root",
                "schema_version": self.SCHEMA_VERSION,
                "label": "Conversation Knowledge Map",
                "summary": (
                    f"{len(component_nodes)} component(s), "
                    f"{len(theme_nodes)} theme(s), "
                    f"{len(subtheme_nodes)} subtheme(s), "
                    f"{len(canonical_points)} knowledge point(s) across "
                    f"{len(maps)} map(s)."
                ),
                "related_file_ids": list(sources.keys()),
                "children": root_children,
                "map_ids": map_ids,
                "component_ids": root_children,
                "theme_ids": root_theme_ids,
                "subtheme_ids": root_subtheme_ids,
                "point_ids": root_point_ids,
            },
            root_support_pages,
            root_support_chunk_ids,
            24,
            36,
        )

    @staticmethod
    def _index_canonical_nodes(
        node_index: dict[str, dict[str, Any]],
        component_nodes: list[dict[str, Any]],
        theme_nodes: list[dict[str, Any]],
        subtheme_nodes: list[dict[str, Any]],
        canonical_points: list[dict[str, Any]],
    ) -> None:
        for component in component_nodes:
            node_index[component["id"]] = component
        for theme in theme_nodes:
            node_index[theme["id"]] = theme
        for subtheme in subtheme_nodes:
            node_index[subtheme["id"]] = subtheme
        for point in canonical_points:
            node_index[point["id"]] = point

    def _build_canonical_graph(
        self,
        conversation_id: str,
        sources: dict[str, dict[str, Any]],
        file_graphs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        (
            point_records,
            root_support_pages,
            root_support_chunk_ids,
        ) = self._collect_canonical_point_records(file_graphs)
        if not point_records:
            self._append_synthetic_point_records(point_records, file_graphs)

        clusters = self._cluster_points(point_records)
        if not clusters and point_records:
            clusters = [point_records]

        (
            component_nodes,
            theme_nodes,
            subtheme_nodes,
            canonical_points,
            canonical_edges,
            node_index,
        ) = self._build_canonical_hierarchy(
            clusters, root_support_pages, root_support_chunk_ids
        )

        if not component_nodes:
            return self._build_empty_canonical_graph(
                conversation_id, sources, node_index
            )

        (
            legacy_systems,
            legacy_file_cards,
            legacy_edges,
        ) = self._build_legacy_graph_artifacts(
            file_graphs, component_nodes, theme_nodes, canonical_points
        )

        root_point_ids = [point["id"] for point in canonical_points]
        maps, map_ids = self._build_knowledge_maps(
            file_graphs,
            component_nodes,
            theme_nodes,
            subtheme_nodes,
            canonical_points,
            root_point_ids,
            node_index,
        )
        root_node_id = "root::conversation"
        root_node = self._build_root_node(
            sources,
            component_nodes,
            theme_nodes,
            subtheme_nodes,
            canonical_points,
            maps,
            map_ids,
            root_support_pages,
            root_support_chunk_ids,
        )
        node_index[root_node_id] = root_node

        self._index_canonical_nodes(
            node_index,
            component_nodes,
            theme_nodes,
            subtheme_nodes,
            canonical_points,
        )

        return {
            "schema_version": self.SCHEMA_VERSION,
            "conversation_id": conversation_id,
            "source_ids": list(sources.keys()),
            "root": root_node,
            "maps": maps,
            "components": component_nodes,
            "themes": theme_nodes,
            "subthemes": subtheme_nodes,
            "knowledge_points": canonical_points,
            "edges": canonical_edges,
            "legacy_edges": legacy_edges,
            "node_index": node_index,
            "support_pages": root_node.get("support_pages", {}),
            "support_chunk_ids": root_node.get("support_chunk_ids", {}),
            "evidence_pages": root_node.get("evidence_pages", {}),
            "evidence_chunk_ids": root_node.get("evidence_chunk_ids", {}),
            "systems": legacy_systems,
            "file_cards": legacy_file_cards,
            "split_reason": "weakly_connected_sources" if len(maps) > 1 else "",
        }

    def build_file_graph(self, file_id: str, source: dict[str, Any]) -> dict[str, Any]:
        return build_file_knowledge_graph(self._service, file_id, source)

    def shared_keywords(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        right_keywords = set(right.get("top_keywords", []))
        shared = [
            keyword
            for keyword in left.get("top_keywords", [])
            if keyword in right_keywords
        ]
        return _limit_unique_strings(shared, 6)

    def group_files_into_systems(
        self, file_graphs: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        file_ids = [graph["file_id"] for graph in file_graphs]
        union_find = _UnionFind(file_ids)
        graph_map = {graph["file_id"]: graph for graph in file_graphs}

        for index, left_id in enumerate(file_ids):
            for right_id in file_ids[index + 1 :]:
                shared = self._service._shared_keywords(
                    graph_map[left_id], graph_map[right_id]
                )
                if len(shared) >= 2:
                    union_find.union(left_id, right_id)

        grouped_ids: dict[str, list[str]] = defaultdict(list)
        for file_id in file_ids:
            grouped_ids[union_find.find(file_id)].append(file_id)

        ordered_systems: list[list[dict[str, Any]]] = []
        for cluster_ids in grouped_ids.values():
            cluster_graphs = [graph_map[file_id] for file_id in cluster_ids]
            cluster_graphs.sort(
                key=lambda item: item.get("file_name", item["file_id"]).lower()
            )
            ordered_systems.append(cluster_graphs)

        ordered_systems.sort(
            key=lambda cluster: (
                -len(cluster),
                cluster[0].get("file_name", cluster[0]["file_id"]).lower(),
            )
        )
        return ordered_systems

    @staticmethod
    def merge_support_dict(
        target: dict[str, list[str]], source: dict[str, list[str]] | None, limit: int
    ) -> dict[str, list[str]]:
        for file_id, values in (source or {}).items():
            key = str(file_id or "").strip()
            if not key:
                continue
            target[key] = _limit_unique_strings(
                target.get(key, []) + list(values or []), limit
            )
        return target

    @staticmethod
    def _merge_support_dict(
        target: dict[str, list[str]], source: dict[str, list[str]] | None, limit: int
    ) -> dict[str, list[str]]:
        return KnowledgeGraphBuilder.merge_support_dict(target, source, limit)

    def build_conversation_graph(
        self, conversation_id: str, sources: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        file_graphs = [
            self._service._build_file_graph(file_id, source)
            for file_id, source in sources.items()
        ]
        return self._build_canonical_graph(conversation_id, sources, file_graphs)
