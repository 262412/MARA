from __future__ import annotations

from typing import Any, Callable

LimitStrings = Callable[[list[str], int], list[str]]


def build_knowledge_maps(
    builder: Any,
    file_graphs: list[dict[str, Any]],
    component_nodes: list[dict[str, Any]],
    theme_nodes: list[dict[str, Any]],
    subtheme_nodes: list[dict[str, Any]],
    canonical_points: list[dict[str, Any]],
    root_point_ids: list[str],
    node_index: dict[str, dict[str, Any]],
    limit_unique_strings: LimitStrings | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    limit_unique_strings = limit_unique_strings or _limit_unique_strings
    system_groups = builder.group_files_into_systems(file_graphs)
    if not system_groups:
        system_groups = [list(file_graphs)]

    system_file_sets = _system_file_sets(system_groups)
    component_map_indices = _assign_component_map_indices(
        component_nodes, system_file_sets
    )
    maps: list[dict[str, Any]] = []
    map_ids: list[str] = []
    for map_index, grouped_file_graphs in enumerate(system_groups, start=1):
        map_node = _build_map_node(
            builder,
            grouped_file_graphs,
            component_nodes,
            component_map_indices,
            map_index,
            len(system_groups),
            root_point_ids,
            limit_unique_strings,
        )
        map_id = str(map_node["id"])
        _tag_map_members(
            map_id,
            list(map_node.get("component_ids", [])),
            component_nodes,
            theme_nodes,
            subtheme_nodes,
            canonical_points,
        )
        maps.append(map_node)
        map_ids.append(map_id)
        node_index[map_id] = map_node
    return maps, map_ids


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


def _system_file_sets(
    system_groups: list[list[dict[str, Any]]],
) -> list[set[str]]:
    return [
        {str(graph.get("file_id", "") or "") for graph in grouped_file_graphs}
        for grouped_file_graphs in system_groups
    ]


def _assign_component_map_indices(
    component_nodes: list[dict[str, Any]],
    system_file_sets: list[set[str]],
) -> dict[str, int]:
    component_map_indices: dict[str, int] = {}
    for component in component_nodes:
        component_id = str(component.get("id", "") or "")
        related_file_id_set = {
            str(file_id or "").strip()
            for file_id in component.get("related_file_ids", []) or []
            if str(file_id or "").strip()
        }
        component_map_indices[component_id] = _best_system_index(
            related_file_id_set, system_file_sets
        )
    return component_map_indices


def _best_system_index(
    related_file_id_set: set[str], system_file_sets: list[set[str]]
) -> int:
    best_index = 0
    best_score = -1
    for index, file_set in enumerate(system_file_sets):
        score = len(related_file_id_set.intersection(file_set))
        if score > best_score:
            best_score = score
            best_index = index
    return best_index


def _build_map_node(
    builder: Any,
    grouped_file_graphs: list[dict[str, Any]],
    component_nodes: list[dict[str, Any]],
    component_map_indices: dict[str, int],
    map_index: int,
    system_group_count: int,
    root_point_ids: list[str],
    limit_unique_strings: LimitStrings,
) -> dict[str, Any]:
    map_id = f"map::{map_index}"
    related_file_ids = limit_unique_strings(
        [str(graph.get("file_id", "") or "") for graph in grouped_file_graphs], 24
    )
    component_ids = _component_ids_for_map(
        component_nodes, component_map_indices, map_index
    )
    support_pages, support_chunk_ids = _map_support(
        builder, grouped_file_graphs, component_nodes, component_ids
    )
    map_label, map_summary = _map_label_and_summary(
        grouped_file_graphs,
        related_file_ids,
        component_ids,
        root_point_ids,
        map_index,
        system_group_count,
    )
    return builder._annotate_evidence_aliases(
        {
            "id": map_id,
            "type": "knowledge_map",
            "kind": "map",
            "schema_version": builder.SCHEMA_VERSION,
            "label": map_label,
            "summary": map_summary,
            "related_file_ids": related_file_ids,
            "component_ids": component_ids,
            "children": component_ids,
        },
        support_pages,
        support_chunk_ids,
        24,
        36,
    )


def _component_ids_for_map(
    component_nodes: list[dict[str, Any]],
    component_map_indices: dict[str, int],
    map_index: int,
) -> list[str]:
    return [
        str(component.get("id", "") or "")
        for component in component_nodes
        if component_map_indices.get(str(component.get("id", "") or ""), 0)
        == (map_index - 1)
    ]


def _map_support(
    builder: Any,
    grouped_file_graphs: list[dict[str, Any]],
    component_nodes: list[dict[str, Any]],
    component_ids: list[str],
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    support_pages: dict[str, list[str]] = {}
    support_chunk_ids: dict[str, list[str]] = {}
    if component_ids:
        component_by_id = {str(item.get("id", "")): item for item in component_nodes}
        for component_id in component_ids:
            component = component_by_id[component_id]
            builder._merge_support_dict(
                support_pages, component.get("support_pages", {}), 24
            )
            builder._merge_support_dict(
                support_chunk_ids, component.get("support_chunk_ids", {}), 36
            )
        return support_pages, support_chunk_ids

    for file_graph in grouped_file_graphs:
        builder._merge_support_dict(
            support_pages, file_graph.get("summary_support_pages", {}), 24
        )
        builder._merge_support_dict(
            support_chunk_ids, file_graph.get("summary_support_chunk_ids", {}), 36
        )
    return support_pages, support_chunk_ids


def _map_label_and_summary(
    grouped_file_graphs: list[dict[str, Any]],
    related_file_ids: list[str],
    component_ids: list[str],
    root_point_ids: list[str],
    map_index: int,
    system_group_count: int,
) -> tuple[str, str]:
    if system_group_count == 1:
        return (
            "Conversation Knowledge Map",
            f"Connected map across {len(related_file_ids)} source(s), "
            f"{len(component_ids)} component(s), and "
            f"{len(root_point_ids)} knowledge point(s).",
        )
    if len(related_file_ids) == 1:
        file_name = str(
            grouped_file_graphs[0].get("file_name", related_file_ids[0])
            or related_file_ids[0]
        )
        return (
            f"{file_name} Knowledge Map",
            "Separated into its own map because it does not strongly connect "
            "to the other uploaded sources.",
        )
    return (
        f"Knowledge System {map_index}",
        f"Separate map for {len(related_file_ids)} related sources that "
        "share stronger overlap with each other than with the rest of "
        "this conversation.",
    )


def _tag_map_members(
    map_id: str,
    component_ids: list[str],
    component_nodes: list[dict[str, Any]],
    theme_nodes: list[dict[str, Any]],
    subtheme_nodes: list[dict[str, Any]],
    canonical_points: list[dict[str, Any]],
) -> None:
    for component_id in component_ids:
        _tag_items_by_id(component_nodes, "id", component_id, map_id)
        _tag_items_by_id(theme_nodes, "component_id", component_id, map_id)
        _tag_items_by_id(subtheme_nodes, "component_id", component_id, map_id)
        _tag_items_by_id(canonical_points, "component_id", component_id, map_id)


def _tag_items_by_id(
    items: list[dict[str, Any]], key: str, expected_value: str, map_id: str
) -> None:
    for item in items:
        if item.get(key) == expected_value:
            item["map_id"] = map_id
