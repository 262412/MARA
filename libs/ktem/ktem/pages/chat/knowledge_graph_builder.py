from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any


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

    def _build_canonical_graph(
        self,
        conversation_id: str,
        sources: dict[str, dict[str, Any]],
        file_graphs: list[dict[str, Any]],
    ) -> dict[str, Any]:
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

        if not point_records:
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
                        "support_pages": file_graph.get("summary_support_pages", {})
                        or {},
                        "support_chunk_ids": file_graph.get(
                            "summary_support_chunk_ids", {}
                        )
                        or {},
                        "synthetic": True,
                    }
                )

        clusters = self._cluster_points(point_records)
        if not clusters and point_records:
            clusters = [point_records]

        component_nodes: list[dict[str, Any]] = []
        theme_nodes: list[dict[str, Any]] = []
        subtheme_nodes: list[dict[str, Any]] = []
        canonical_points: list[dict[str, Any]] = []
        canonical_edges: list[dict[str, Any]] = []
        node_index: dict[str, dict[str, Any]] = {}

        point_to_component: dict[str, str] = {}
        point_to_theme: dict[str, str] = {}
        point_to_subtheme: dict[str, str] = {}
        point_to_cluster_index: dict[str, int] = {}

        for component_index, cluster_points in enumerate(clusters, start=1):
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

            component_support_pages: dict[str, list[str]] = {}
            component_support_chunk_ids: dict[str, list[str]] = {}
            for point in cluster_points:
                self._merge_support_dict(
                    component_support_pages, point.get("support_pages", {}), 24
                )
                self._merge_support_dict(
                    component_support_chunk_ids, point.get("support_chunk_ids", {}), 36
                )
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
            component_nodes.append(component_node)
            node_index[component_id] = component_node
            self._merge_support_dict(root_support_pages, component_support_pages, 24)
            self._merge_support_dict(
                root_support_chunk_ids, component_support_chunk_ids, 36
            )

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
                point
                for point in cluster_points
                if point["id"] not in assigned_point_ids
            ]
            if remaining_points:
                fallback_keyword = (
                    component_keywords[0] if component_keywords else "general"
                )
                theme_groups.append((fallback_keyword, remaining_points))

            for theme_index, (theme_keyword, theme_points) in enumerate(
                theme_groups, start=1
            ):
                theme_id = f"theme::{component_index}::{theme_index}"
                theme_keywords = self._sorted_unique_keywords(theme_points, limit=4)
                theme_label = theme_keyword
                if theme_label == "__general__":
                    theme_label = (
                        self._service._trim_sentence(
                            theme_points[0].get("label", ""), 84
                        )
                        if theme_points
                        else "General theme"
                    )
                elif len(theme_points) == 1:
                    theme_label = (
                        self._service._trim_sentence(
                            theme_points[0].get("label", ""), 84
                        )
                        or theme_keyword
                    )
                theme_summary = f"Theme around {theme_label} within {component_label}."

                theme_support_pages: dict[str, list[str]] = {}
                theme_support_chunk_ids: dict[str, list[str]] = {}
                for point in theme_points:
                    self._merge_support_dict(
                        theme_support_pages, point.get("support_pages", {}), 24
                    )
                    self._merge_support_dict(
                        theme_support_chunk_ids, point.get("support_chunk_ids", {}), 36
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
                theme_nodes.append(theme_node)
                node_index[theme_id] = theme_node
                component_node["children"].append(theme_id)
                canonical_edges.append(
                    {
                        "source": component_id,
                        "target": theme_id,
                        "type": "component_theme",
                        "related_file_ids": list(
                            theme_node.get("related_file_ids", [])
                        ),
                    }
                )
                self._merge_support_dict(root_support_pages, theme_support_pages, 24)
                self._merge_support_dict(
                    root_support_chunk_ids, theme_support_chunk_ids, 36
                )

                subtheme_groups: dict[
                    tuple[str, str], list[dict[str, Any]]
                ] = defaultdict(list)
                for point in theme_points:
                    signature = self._make_subtheme_signature(point, theme_keyword)
                    subtheme_groups[signature].append(point)

                for subtheme_index, (signature, subtheme_points) in enumerate(
                    sorted(
                        subtheme_groups.items(),
                        key=lambda item: (
                            -len(item[1]),
                            item[1][0].get("label", "").lower(),
                        ),
                    ),
                    start=1,
                ):
                    subtheme_id = (
                        f"subtheme::{component_index}::{theme_index}::{subtheme_index}"
                    )
                    subtheme_keywords = self._sorted_unique_keywords(
                        subtheme_points, limit=4
                    )
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
                    subtheme_support_pages: dict[str, list[str]] = {}
                    subtheme_support_chunk_ids: dict[str, list[str]] = {}
                    for point in subtheme_points:
                        self._merge_support_dict(
                            subtheme_support_pages, point.get("support_pages", {}), 24
                        )
                        self._merge_support_dict(
                            subtheme_support_chunk_ids,
                            point.get("support_chunk_ids", {}),
                            36,
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
                    subtheme_nodes.append(subtheme_node)
                    node_index[subtheme_id] = subtheme_node
                    theme_node["children"].append(subtheme_id)
                    canonical_edges.append(
                        {
                            "source": theme_id,
                            "target": subtheme_id,
                            "type": "theme_subtheme",
                            "related_file_ids": list(
                                subtheme_node.get("related_file_ids", [])
                            ),
                        }
                    )
                    self._merge_support_dict(
                        root_support_pages, subtheme_support_pages, 24
                    )
                    self._merge_support_dict(
                        root_support_chunk_ids, subtheme_support_chunk_ids, 36
                    )

                    for point in subtheme_points:
                        point_to_component[point["id"]] = component_id
                        point_to_theme[point["id"]] = theme_id
                        point_to_subtheme[point["id"]] = subtheme_id
                        point_to_cluster_index[point["id"]] = component_index

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
                        canonical_points.append(point_node)
                        node_index[point_node["id"]] = point_node
                        subtheme_node["children"].append(point_node["id"])
                        canonical_edges.append(
                            {
                                "source": subtheme_id,
                                "target": point_node["id"],
                                "type": "subtheme_point",
                                "related_file_ids": [point["file_id"]],
                            }
                        )
                        self._merge_support_dict(
                            root_support_pages, point.get("support_pages", {}), 24
                        )
                        self._merge_support_dict(
                            root_support_chunk_ids,
                            point.get("support_chunk_ids", {}),
                            36,
                        )

        if not component_nodes:
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

        component_to_legacy_system_id = {
            component["id"]: f"system::{index}"
            for index, component in enumerate(component_nodes, start=1)
        }
        component_to_theme_nodes: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for theme_node in theme_nodes:
            component_to_theme_nodes[str(theme_node.get("component_id", ""))].append(
                theme_node
            )

        component_to_points: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for point_node in canonical_points:
            component_to_points[str(point_node.get("component_id", ""))].append(
                point_node
            )

        file_primary_component: dict[str, str] = {}
        for file_graph in file_graphs:
            file_id = str(file_graph.get("file_id", "") or "")
            candidate_points = [
                point for point in canonical_points if point.get("file_id") == file_id
            ]
            if candidate_points:
                component_counts: Counter[str] = Counter(
                    str(point.get("component_id", "")) for point in candidate_points
                )
                primary_component_id = max(
                    component_counts.items(),
                    key=lambda item: (
                        item[1],
                        -component_nodes.index(
                            next(
                                component
                                for component in component_nodes
                                if component["id"] == item[0]
                            )
                        ),
                    ),
                )[0]
            else:
                primary_component_id = component_nodes[0]["id"]
            file_primary_component[file_id] = primary_component_id

        legacy_systems: list[dict[str, Any]] = []
        legacy_file_cards: list[dict[str, Any]] = []
        legacy_points: list[dict[str, Any]] = []
        legacy_edges: list[dict[str, Any]] = []

        for component_index, component_node in enumerate(component_nodes, start=1):
            component_id = str(component_node["id"])
            legacy_system_id = component_to_legacy_system_id[component_id]
            legacy_themes = []
            for theme_node in component_to_theme_nodes.get(component_id, []):
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
                        "related_file_ids": list(
                            legacy_theme.get("related_file_ids", [])
                        ),
                    }
                )
            legacy_system = {
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
            legacy_systems.append(legacy_system)

        for file_graph in file_graphs:
            file_id = str(file_graph.get("file_id", "") or "")
            primary_component_id = file_primary_component.get(
                file_id, component_nodes[0]["id"]
            )
            legacy_system_id = component_to_legacy_system_id[primary_component_id]
            file_card = {
                "id": f"file::{file_id}",
                "type": "file_summary",
                "kind": "file_summary",
                "system_id": legacy_system_id,
                "component_id": primary_component_id,
                "file_id": file_id,
                "label": file_graph.get("file_name", file_id),
                "summary": file_graph.get("summary", ""),
                "related_file_ids": list(
                    next(
                        component["related_file_ids"]
                        for component in component_nodes
                        if component["id"] == primary_component_id
                    )
                ),
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

        for point_node in canonical_points:
            component_id = str(point_node.get("component_id", ""))
            legacy_system_id = component_to_legacy_system_id.get(
                component_id, "system::1"
            )
            legacy_point = dict(point_node)
            legacy_point["system_id"] = legacy_system_id
            legacy_point["type"] = "knowledge_point"
            legacy_point["kind"] = "knowledge_point"
            legacy_points.append(legacy_point)
            legacy_edges.append(
                {
                    "source": f"file::{point_node.get('file_id', '')}",
                    "target": point_node["id"],
                    "type": "file_point",
                    "related_file_ids": [point_node.get("file_id", "")],
                }
            )

        root_children = [component["id"] for component in component_nodes]
        root_theme_ids = [theme["id"] for theme in theme_nodes]
        root_subtheme_ids = [subtheme["id"] for subtheme in subtheme_nodes]
        root_point_ids = [point["id"] for point in canonical_points]
        system_groups = self.group_files_into_systems(file_graphs)
        if not system_groups:
            system_groups = [list(file_graphs)]

        system_file_sets = [
            {str(graph.get("file_id", "") or "") for graph in grouped_file_graphs}
            for grouped_file_graphs in system_groups
        ]
        component_map_indices: dict[str, int] = {}
        for component in component_nodes:
            component_id = str(component.get("id", "") or "")
            related_file_id_set = {
                str(file_id or "").strip()
                for file_id in component.get("related_file_ids", []) or []
                if str(file_id or "").strip()
            }
            best_index = 0
            best_score = -1
            for index, file_set in enumerate(system_file_sets):
                score = len(related_file_id_set.intersection(file_set))
                if score > best_score:
                    best_score = score
                    best_index = index
            component_map_indices[component_id] = best_index

        maps: list[dict[str, Any]] = []
        map_ids: list[str] = []
        for map_index, grouped_file_graphs in enumerate(system_groups, start=1):
            map_id = f"map::{map_index}"
            related_file_ids = _limit_unique_strings(
                [str(graph.get("file_id", "") or "") for graph in grouped_file_graphs],
                24,
            )
            component_ids = [
                str(component.get("id", "") or "")
                for component in component_nodes
                if component_map_indices.get(str(component.get("id", "") or ""), 0)
                == (map_index - 1)
            ]

            map_support_pages: dict[str, list[str]] = {}
            map_support_chunk_ids: dict[str, list[str]] = {}
            if component_ids:
                for component_id in component_ids:
                    component = next(
                        item
                        for item in component_nodes
                        if item.get("id") == component_id
                    )
                    self._merge_support_dict(
                        map_support_pages, component.get("support_pages", {}), 24
                    )
                    self._merge_support_dict(
                        map_support_chunk_ids,
                        component.get("support_chunk_ids", {}),
                        36,
                    )
            else:
                for file_graph in grouped_file_graphs:
                    self._merge_support_dict(
                        map_support_pages,
                        file_graph.get("summary_support_pages", {}),
                        24,
                    )
                    self._merge_support_dict(
                        map_support_chunk_ids,
                        file_graph.get("summary_support_chunk_ids", {}),
                        36,
                    )

            if len(system_groups) == 1:
                map_label = "Conversation Knowledge Map"
                map_summary = (
                    f"Connected map across {len(related_file_ids)} source(s), "
                    f"{len(component_ids)} component(s), and {len(root_point_ids)} knowledge point(s)."
                )
            elif len(related_file_ids) == 1:
                file_name = str(
                    grouped_file_graphs[0].get("file_name", related_file_ids[0])
                    or related_file_ids[0]
                )
                map_label = f"{file_name} Knowledge Map"
                map_summary = (
                    "Separated into its own map because it does not strongly connect "
                    "to the other uploaded sources."
                )
            else:
                map_label = f"Knowledge System {map_index}"
                map_summary = (
                    f"Separate map for {len(related_file_ids)} related sources that "
                    "share stronger overlap with each other than with the rest of "
                    "this conversation."
                )

            map_node = self._annotate_evidence_aliases(
                {
                    "id": map_id,
                    "type": "knowledge_map",
                    "kind": "map",
                    "schema_version": self.SCHEMA_VERSION,
                    "label": map_label,
                    "summary": map_summary,
                    "related_file_ids": related_file_ids,
                    "component_ids": component_ids,
                    "children": component_ids,
                },
                map_support_pages,
                map_support_chunk_ids,
                24,
                36,
            )
            for component_id in component_ids:
                for component in component_nodes:
                    if component.get("id") == component_id:
                        component["map_id"] = map_id
                for theme in theme_nodes:
                    if theme.get("component_id") == component_id:
                        theme["map_id"] = map_id
                for subtheme in subtheme_nodes:
                    if subtheme.get("component_id") == component_id:
                        subtheme["map_id"] = map_id
                for point in canonical_points:
                    if point.get("component_id") == component_id:
                        point["map_id"] = map_id
            maps.append(map_node)
            map_ids.append(map_id)
            node_index[map_id] = map_node

        root_node_id = "root::conversation"
        root_node = self._annotate_evidence_aliases(
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
        node_index[root_node_id] = root_node

        for component in component_nodes:
            node_index[component["id"]] = component
        for theme in theme_nodes:
            node_index[theme["id"]] = theme
        for subtheme in subtheme_nodes:
            node_index[subtheme["id"]] = subtheme
        for point in canonical_points:
            node_index[point["id"]] = point

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
        docs = self._service._load_file_docs(file_id)
        candidates, pages_seen = self._service._make_sentence_candidates(docs)
        candidates, top_keywords = self._service._score_candidates(candidates)

        llm_outline = self._service._generate_outline_with_llm(
            source.get("name", file_id), candidates[:16]
        )

        if llm_outline and llm_outline.get("knowledge_points"):
            summary_text = self._service._trim_sentence(
                llm_outline.get("summary", ""), 132
            )
            if not summary_text and candidates:
                summary_text = self._service._trim_sentence(
                    candidates[0].get("text", ""), 132
                )
            summary_candidate = (
                candidates[0] if candidates else {"page_label": "", "doc_id": ""}
            )

            knowledge_points: list[dict[str, Any]] = []
            for point in llm_outline.get("knowledge_points", []):
                label = self._service._trim_sentence(
                    str(point.get("label", "") or ""), 110
                )
                if not label or self._service._is_duplicate_point(
                    knowledge_points, label
                ):
                    continue
                match = (
                    candidates[len(knowledge_points)]
                    if len(candidates) > len(knowledge_points)
                    else summary_candidate
                )
                support_pages = _limit_unique_strings([match.get("page_label", "")], 8)
                support_chunk_ids = _limit_unique_strings([match.get("doc_id", "")], 8)
                knowledge_points.append(
                    {
                        "id": f"point::{file_id}::{len(knowledge_points) + 1}",
                        "type": "knowledge_point",
                        "file_id": file_id,
                        "label": label,
                        "keywords": _limit_unique_strings(
                            list(point.get("keywords", []))
                            + self._service._extract_keywords(label, limit=6),
                            6,
                        ),
                        "related_file_ids": [file_id],
                        "support_pages": {file_id: support_pages},
                        "support_chunk_ids": {file_id: support_chunk_ids},
                        "evidence_pages": {file_id: list(support_pages)},
                        "evidence_chunk_ids": {file_id: list(support_chunk_ids)},
                    }
                )
                if len(knowledge_points) >= 6:
                    break
            if not knowledge_points:
                llm_outline = None

        if not llm_outline:
            if candidates:
                summary_candidate = candidates[0]
                summary_text = self._service._trim_sentence(
                    summary_candidate.get("text", ""), 132
                )
            else:
                summary_text = (
                    f"{source.get('name', file_id)} contains indexed content "
                    "for this conversation."
                )
                summary_candidate = {"page_label": "", "doc_id": ""}

            knowledge_points = []
            for candidate in candidates:
                label = self._service._trim_sentence(candidate.get("text", ""), 110)
                if not label or self._service._is_duplicate_point(
                    knowledge_points, label
                ):
                    continue
                support_pages = _limit_unique_strings(
                    [candidate.get("page_label", "")], 8
                )
                support_chunk_ids = _limit_unique_strings(
                    [candidate.get("doc_id", "")], 8
                )
                knowledge_points.append(
                    {
                        "id": f"point::{file_id}::{len(knowledge_points) + 1}",
                        "type": "knowledge_point",
                        "file_id": file_id,
                        "label": label,
                        "keywords": _limit_unique_strings(
                            candidate.get("keywords", []), 6
                        ),
                        "related_file_ids": [file_id],
                        "support_pages": {file_id: support_pages},
                        "support_chunk_ids": {file_id: support_chunk_ids},
                        "evidence_pages": {file_id: list(support_pages)},
                        "evidence_chunk_ids": {file_id: list(support_chunk_ids)},
                    }
                )
                if len(knowledge_points) >= 6:
                    break
            if not knowledge_points:
                knowledge_points.append(
                    {
                        "id": f"point::{file_id}::1",
                        "type": "knowledge_point",
                        "file_id": file_id,
                        "label": self._service._trim_sentence(summary_text, 110),
                        "keywords": top_keywords[:4],
                        "related_file_ids": [file_id],
                        "support_pages": {
                            file_id: _limit_unique_strings(
                                [summary_candidate.get("page_label", "")], 8
                            )
                        },
                        "support_chunk_ids": {
                            file_id: _limit_unique_strings(
                                [summary_candidate.get("doc_id", "")], 8
                            )
                        },
                        "evidence_pages": {
                            file_id: _limit_unique_strings(
                                [summary_candidate.get("page_label", "")], 8
                            )
                        },
                        "evidence_chunk_ids": {
                            file_id: _limit_unique_strings(
                                [summary_candidate.get("doc_id", "")], 8
                            )
                        },
                    }
                )

        summary_pages = _limit_unique_strings(
            [summary_candidate.get("page_label", "")] + pages_seen,
            12,
        )
        summary_chunks = _limit_unique_strings(
            [summary_candidate.get("doc_id", "")], 12
        )

        return {
            "file_id": file_id,
            "file_name": source.get("name", file_id),
            "signature": self._service._make_signature(source),
            "summary": summary_text,
            "pages": pages_seen,
            "top_keywords": top_keywords,
            "summary_support_pages": {file_id: summary_pages},
            "summary_support_chunk_ids": {file_id: summary_chunks},
            "support_pages": {file_id: summary_pages},
            "support_chunk_ids": {file_id: summary_chunks},
            "evidence_pages": {file_id: list(summary_pages)},
            "evidence_chunk_ids": {file_id: list(summary_chunks)},
            "knowledge_points": knowledge_points,
        }

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
