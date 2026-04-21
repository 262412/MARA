from __future__ import annotations

import html
import json
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


class KnowledgeGraphRenderer:
    _ROLE_LABELS = {
        "knowledge_root": "Conversation Root",
        "knowledge_map": "Knowledge Map",
        "component": "Component",
        "theme": "Theme",
        "subtheme": "Subtheme",
        "knowledge_point": "Knowledge Point",
    }

    _ROLE_ALIASES = {
        "knowledge_system": "component",
        "system_relation": "theme",
        "file_summary": "subtheme",
    }

    _NODE_STYLE_ALIASES = {
        "knowledge_root": "kg-tree-node--root",
        "knowledge_map": "kg-tree-node--root",
        "component": "kg-tree-node--component",
        "theme": "kg-tree-node--theme",
        "subtheme": "kg-tree-node--subtheme",
        "knowledge_point": "kg-tree-node--point",
    }

    _CHILD_SPECS = {
        "knowledge_root": [("components", "component"), ("systems", "component")],
        "knowledge_map": [("components", "component")],
        "component": [("themes", "theme"), ("file_cards", "subtheme")],
        "theme": [("subthemes", "subtheme"), ("file_cards", "subtheme")],
        "subtheme": [("knowledge_points", "knowledge_point")],
    }

    def __init__(self, service):
        self._service = service

    def _escape_attr(self, value: Any) -> str:
        return html.escape(str(value or ""), quote=True)

    def _node_type(self, item: dict[str, Any], fallback: str) -> str:
        raw_type = str(item.get("type", "") or "").strip()
        if raw_type:
            return raw_type
        return fallback

    def _node_role(self, item: dict[str, Any], fallback: str) -> str:
        node_type = self._node_type(item, fallback)
        return self._ROLE_ALIASES.get(node_type, node_type or fallback)

    def _node_label(self, item: dict[str, Any]) -> str:
        return str(item.get("label", "") or "").strip()

    def _node_summary(self, item: dict[str, Any]) -> str:
        summary = str(item.get("summary", "") or "").strip()
        if summary:
            return summary
        return self._node_label(item)

    def _node_related_file_ids(
        self, item: dict[str, Any], focus_file_id: str
    ) -> list[str]:
        related_file_ids = _limit_unique_strings(
            [focus_file_id] + list(item.get("related_file_ids", []) or []),
            12,
        )
        file_id = str(item.get("file_id", "") or "").strip()
        if file_id and file_id not in related_file_ids:
            related_file_ids = _limit_unique_strings(related_file_ids + [file_id], 12)
        return related_file_ids

    def _node_support_pages(self, item: dict[str, Any]) -> dict[str, Any]:
        support_pages = item.get("support_pages", {}) or {}
        if support_pages:
            return support_pages
        return item.get("evidence_pages", {}) or {}

    def _node_support_chunk_ids(self, item: dict[str, Any]) -> dict[str, Any]:
        support_chunk_ids = item.get("support_chunk_ids", {}) or {}
        if support_chunk_ids:
            return support_chunk_ids
        return item.get("evidence_chunk_ids", {}) or {}

    def _focus_matches(
        self, item: dict[str, Any], focus_file_id: str, fallback_type: str = "knowledge_point"
    ) -> bool:
        if not focus_file_id:
            return False
        file_id = str(item.get("file_id", "") or "").strip()
        if file_id and file_id == focus_file_id:
            return True
        if focus_file_id in (item.get("related_file_ids", []) or []):
            return True

        node_type = self._node_type(item, fallback_type)
        for child_key, child_fallback in self._child_specs(node_type):
            for child in list(item.get(child_key, []) or []):
                if not isinstance(child, dict):
                    continue
                if self._focus_matches(child, focus_file_id, child_fallback):
                    return True
        return False

    def _sort_nodes(
        self, nodes: list[dict[str, Any]], focus_file_id: str
    ) -> list[dict[str, Any]]:
        return sorted(
            nodes,
            key=lambda item: (
                0 if self._focus_matches(item, focus_file_id) else 1,
                self._node_label(item).lower(),
                self._node_type(item, "knowledge_point").lower(),
            ),
        )

    def _child_specs(self, node_type: str) -> list[tuple[str, str]]:
        return list(self._CHILD_SPECS.get(node_type, []))

    def _child_identifiers(
        self, item: dict[str, Any], child_key: str
    ) -> list[dict[str, Any] | str]:
        raw_children = list(item.get(child_key, []) or [])
        if raw_children:
            return raw_children
        if child_key == "components":
            return list(item.get("component_ids", []) or item.get("children", []) or [])
        return list(item.get("children", []) or [])

    def _materialize_v2_item(
        self, item: dict[str, Any], graph: dict[str, Any], fallback_type: str
    ) -> dict[str, Any]:
        node_index = graph.get("node_index", {}) or {}
        materialized = dict(item)
        node_type = self._node_type(materialized, fallback_type)

        for child_key, child_fallback in self._child_specs(node_type):
            children: list[dict[str, Any]] = []
            for child in self._child_identifiers(materialized, child_key):
                if isinstance(child, dict):
                    child_item = child
                else:
                    child_item = node_index.get(str(child), {})
                if not isinstance(child_item, dict) or not child_item:
                    continue
                children.append(
                    self._materialize_v2_item(child_item, graph, child_fallback)
                )
            materialized[child_key] = children

        return materialized

    def _graph_maps(self, graph: dict[str, Any]) -> list[dict[str, Any]]:
        maps = list(graph.get("maps", []) or [])
        if maps:
            return [item for item in maps if isinstance(item, dict)]

        components = list(graph.get("components", []) or [])
        if not components:
            return []

        return [
            {
                "id": "map::conversation",
                "type": "knowledge_map",
                "kind": "map",
                "label": "Conversation Knowledge Map",
                "summary": (
                    "Connected mind map built from the current conversation "
                    "sources."
                ),
                "related_file_ids": list(graph.get("source_ids", []) or []),
                "component_ids": [str(item.get("id", "") or "") for item in components],
                "support_pages": graph.get("support_pages", {}) or {},
                "support_chunk_ids": graph.get("support_chunk_ids", {}) or {},
            }
        ]

    def _render_branch(
        self,
        item: dict[str, Any],
        focus_file_id: str,
        fallback_type: str,
        level: int,
    ) -> str:
        node_type = self._node_type(item, fallback_type)
        node_role = self._node_role(item, fallback_type)
        node_label = self._node_label(item) or self._ROLE_LABELS.get(node_role, "Node")
        node_summary = self._node_summary(item)
        related_file_ids = self._node_related_file_ids(item, focus_file_id)
        support_pages = self._node_support_pages(item)
        support_chunk_ids = self._node_support_chunk_ids(item)
        node_id = str(item.get("id", "") or "").strip()
        if not node_id:
            node_id = f"{node_role or 'node'}::{node_label}"
        focus_match = self._focus_matches(item, focus_file_id)

        branch_classes = ["kg-branch", f"kg-branch--{node_role}"]
        if focus_match:
            branch_classes.append("is-focused")

        node_classes = ["kg-tree-node", f"kg-tree-node--{node_role}"]
        node_style_alias = self._NODE_STYLE_ALIASES.get(node_role)
        if node_style_alias and node_style_alias not in node_classes:
            node_classes.append(node_style_alias)
        if node_type in self._ROLE_ALIASES:
            alias_style = self._NODE_STYLE_ALIASES.get(
                self._ROLE_ALIASES.get(node_type, node_type),
                "",
            )
            if alias_style and alias_style not in node_classes:
                node_classes.append(alias_style)
        if focus_match and "is-focused" not in node_classes:
            node_classes.append("is-focused")
        if node_role == "subtheme" and "kg-file-card" not in node_classes:
            node_classes.append("kg-file-card")
        if node_role == "knowledge_point" and "kg-point-card" not in node_classes:
            node_classes.append("kg-point-card")

        node_attrs = {
            "type": "button",
            "class": " ".join(node_classes),
            "data-kg-payload": self.payload_attr(item, focus_file_id),
            "data-kg-node-id": node_id,
            "data-kg-node-type": node_type,
            "data-kg-node-role": node_role,
            "data-kg-node-level": str(level),
            "data-kg-focus-file-id": focus_file_id,
            "data-kg-focus-match": "true" if focus_match else "false",
            "data-kg-related-file-ids": ",".join(related_file_ids),
            "data-kg-support-pages": self._escape_attr(
                json.dumps(support_pages, ensure_ascii=False)
            ),
            "data-kg-support-chunk-ids": self._escape_attr(
                json.dumps(support_chunk_ids, ensure_ascii=False)
            ),
        }
        if str(item.get("file_id", "") or "").strip():
            node_attrs["data-kg-file-card"] = self._escape_attr(item.get("file_id", ""))

        children_html: list[str] = []
        for child_key, child_fallback in self._child_specs(node_type):
            child_nodes = [
                child
                for child in list(item.get(child_key, []) or [])
                if isinstance(child, dict)
            ]
            if not child_nodes:
                continue
            child_nodes = self._sort_nodes(child_nodes, focus_file_id)
            children_html.append(
                "<div class='kg-branch__children-group "
                f"kg-branch__children-group--{self._escape_attr(child_key)}'>"
            )
            for child in child_nodes:
                children_html.append(
                    self._render_branch(child, focus_file_id, child_fallback, level + 1)
                )
            children_html.append("</div>")

        html_parts = [
            f"<section class='{' '.join(branch_classes)}' "
            f"data-kg-branch-level='{level}' "
            f"data-kg-branch-type='{self._escape_attr(node_role)}' "
            f"data-kg-focus-match='{'true' if focus_match else 'false'}'>",
            "<div class='kg-branch__card'>",
            "<button ",
        ]
        html_parts.append(" ".join(f"{key}='{value}'" for key, value in node_attrs.items()))
        html_parts.append(f">{html.escape(node_label)}</button>")
        if node_summary:
            html_parts.append(
                f"<p class='kg-branch__summary'>{html.escape(node_summary)}</p>"
            )
        html_parts.append("</div>")
        if children_html:
            html_parts.append("<div class='kg-branch__children'>")
            html_parts.extend(children_html)
            html_parts.append("</div>")
        html_parts.append("</section>")
        return "".join(html_parts)

    def make_graph_context(
        self, item: dict[str, Any], focus_file_id: str
    ) -> dict[str, Any]:
        related_file_ids = self._node_related_file_ids(item, focus_file_id)
        node_type = self._node_type(item, "knowledge_point")
        node_role = self._node_role(item, "knowledge_point")
        return {
            "label": item.get("label", ""),
            "type": node_type,
            "kind": str(item.get("kind", node_role) or node_role),
            "node_role": node_role,
            "node_id": str(item.get("id", "") or ""),
            "component_id": str(item.get("component_id", "") or ""),
            "map_id": str(item.get("map_id", "") or ""),
            "focus_file_id": focus_file_id,
            "related_file_ids": related_file_ids,
            "support_pages": self._node_support_pages(item),
            "support_chunk_ids": self._node_support_chunk_ids(item),
        }

    def build_suggested_question(self, item: dict[str, Any]) -> str:
        label = str(item.get("label", "") or "this topic")
        node_role = self._node_role(item, "knowledge_point")
        if node_role == "knowledge_root":
            return (
                "Can you summarize the main components, themes, subthemes, and "
                "knowledge points in this conversation?"
            )
        if node_role == "knowledge_map":
            return (
                f"Can you summarize the separate knowledge map '{label}' and explain "
                "how its themes connect?"
            )
        if node_role == "component":
            return (
                f"Can you explain the component '{label}' and the themes it groups?"
            )
        if node_role == "theme":
            return (
                f"Can you explain the theme '{label}' and how it connects the "
                "subthemes below it?"
            )
        if node_role == "subtheme":
            return (
                f"Can you explain the subtheme '{label}' and the evidence it collects?"
            )
        return f"Can you explain this knowledge point: '{label}'?"

    def build_prompt(self, item: dict[str, Any], focus_file_id: str) -> str:
        label = str(item.get("label", "") or "this topic")
        graph_context = self.make_graph_context(item, focus_file_id)
        related_ids = list(graph_context.get("related_file_ids", []) or [])
        node_role = self._node_role(item, "knowledge_point")

        if len(related_ids) > 1:
            relation_clause = (
                " Then add how it connects with related files from the same "
                "conversation."
            )
        else:
            relation_clause = (
                " Then mention whether any cross-file relation is supported."
            )

        if node_role in {"knowledge_root", "knowledge_map"}:
            return (
                f"Please explain '{label}' using component/theme/subtheme/knowledge "
                "point evidence first."
                + relation_clause
            )
        return (
            f"Please explain '{label}' using current-file/current-page evidence first."
            + relation_clause
        )

    def payload_attr(self, item: dict[str, Any], focus_file_id: str) -> str:
        summary = str(item.get("summary", "") or "").strip()
        if not summary:
            summary = str(item.get("label", "") or "")
        prompt = self.build_prompt(item, focus_file_id)
        suggested_question = self.build_suggested_question(item)
        payload = {
            "graph_context": self.make_graph_context(item, focus_file_id),
            "node_label": str(item.get("label", "") or ""),
            "node_type": self._node_type(item, "knowledge_point"),
            "node_role": self._node_role(item, "knowledge_point"),
            "node_id": str(item.get("id", "") or ""),
            "summary": summary,
            "prompt": prompt,
            "suggested_question": suggested_question,
            "fill_question": suggested_question,
        }
        return html.escape(json.dumps(payload, ensure_ascii=False), quote=True)

    def _preview_title(self, maps: list[dict[str, Any]]) -> str:
        return "Conversation Knowledge Map" if len(maps) <= 1 else "Conversation Knowledge Maps"

    def _preview_meta(self, graph: dict[str, Any], maps: list[dict[str, Any]], status: str) -> str:
        if status != "ready":
            return "Knowledge graph is not ready yet."
        if len(maps) > 1:
            return f"Split into {len(maps)} separate maps"
        source_count = len(list(graph.get("source_ids", []) or []))
        if source_count == 1:
            return "Based on 1 source"
        return f"Based on {source_count} sources"

    def _render_preview_card(
        self, graph: dict[str, Any], maps: list[dict[str, Any]], status: str
    ) -> str:
        title = self._preview_title(maps)
        meta = self._preview_meta(graph, maps, status)
        return (
            "<button type='button' class='kg-preview-card' "
            "data-kg-open-viewer='true'>"
            f"<span class='kg-preview-card__title'>{html.escape(title)}</span>"
            f"<span class='kg-preview-card__meta'>{html.escape(meta)}</span>"
            "<span class='kg-preview-card__cta'>Open Graph</span>"
            "</button>"
        )

    def _render_graph_canvas(self, graph: dict[str, Any], focus_file_id: str) -> str:
        maps = self._graph_maps(graph)

        shell_html: list[str] = []
        root_source_ids = list(graph.get("source_ids", []) or [])
        if len(maps) == 1:
            single_root = self._materialize_v2_item(
                {
                    "id": "root::conversation",
                    "type": "knowledge_root",
                    "kind": "root",
                    "label": "Conversation Knowledge Map",
                    "summary": (
                        "Horizontal mind map organized as component, theme, "
                        "subtheme, and knowledge point branches."
                    ),
                    "related_file_ids": root_source_ids,
                    "support_pages": graph.get("support_pages", {}) or {},
                    "support_chunk_ids": graph.get("support_chunk_ids", {}) or {},
                    "component_ids": list(maps[0].get("component_ids", []) or []),
                },
                graph,
                "knowledge_root",
            )
            shell_html.append("<div class='kg-mindmap-root'>")
            shell_html.append(
                self._render_branch(single_root, focus_file_id, "knowledge_root", 0)
            )
            shell_html.append("</div>")
            return "".join(shell_html)

        if not maps:
            legacy_components = list(
                graph.get("components", []) or graph.get("systems", []) or []
            )
            if not legacy_components:
                return self.render_empty_html(
                    "No knowledge graph available yet.",
                    "Upload files from the same topic or knowledge system when possible. "
                    "If some sources are too different, the graph will split them into "
                    "separate maps.",
                )

            root_item = {
                "id": "root::conversation",
                "type": "knowledge_root",
                "kind": "root",
                "label": "Conversation Knowledge Map",
                "summary": (
                    "Horizontal mind map organized as component, theme, subtheme, "
                    "and knowledge point branches."
                ),
                "related_file_ids": list(graph.get("source_ids", []) or []),
                "support_pages": graph.get("support_pages", {}) or {},
                "support_chunk_ids": graph.get("support_chunk_ids", {}) or {},
                "components": legacy_components,
            }
            shell_html.append("<div class='kg-mindmap-root'>")
            shell_html.append(
                self._render_branch(root_item, focus_file_id, "knowledge_root", 0)
            )
            shell_html.append("</div>")
            return "".join(shell_html)

        root_summary = (
            f"These uploads form {len(maps)} separate knowledge maps because they do "
            "not all belong to one connected knowledge system."
        )
        split_root = self._materialize_v2_item(
            {
                "id": "root::conversation",
                "type": "knowledge_root",
                "kind": "root",
                "label": "Conversation Knowledge Maps",
                "summary": root_summary,
                "related_file_ids": root_source_ids,
                "support_pages": graph.get("support_pages", {}) or {},
                "support_chunk_ids": graph.get("support_chunk_ids", {}) or {},
                "components": [],
            },
            graph,
            "knowledge_root",
        )
        shell_html.append("<div class='kg-mindmap-root kg-mindmap-root--split'>")
        shell_html.append(
            self._render_branch(split_root, focus_file_id, "knowledge_root", 0)
        )
        shell_html.append("</div>")
        shell_html.append(
            "<div class='kg-map-split-banner'>"
            f"This conversation was split into {len(maps)} separate maps because "
            "some uploaded sources are only weakly connected."
            "</div>"
        )
        shell_html.append("<div class='kg-map-sections'>")
        for map_item in maps:
            materialized_map = self._materialize_v2_item(
                map_item,
                graph,
                "knowledge_map",
            )
            shell_html.append("<section class='kg-map-section'>")
            shell_html.append(
                self._render_branch(materialized_map, focus_file_id, "knowledge_map", 0)
            )
            shell_html.append("</section>")
        shell_html.append("</div>")
        return "".join(shell_html)

    def render_empty_html(self, message: str, hint: str = "") -> str:
        meta = html.escape(hint) if hint else "Knowledge graph is not ready yet."
        return (
            "<div class='knowledge-graph-shell is-empty' "
            "data-kg-status='empty' data-kg-layout='mindmap' data-kg-schema='v2'>"
            "<div class='kg-preview-card kg-preview-card--disabled' "
            "data-kg-open-viewer='false'>"
            f"<span class='kg-preview-card__title'>{html.escape(message)}</span>"
            f"<span class='kg-preview-card__meta'>{meta}</span>"
            "</div>"
            "</div>"
        )

    def render_graph_html(
        self, graph: dict[str, Any], focus_file_id: str, status: str
    ) -> str:
        maps = self._graph_maps(graph)

        shell_classes = "knowledge-graph-shell"
        if status == "stale":
            shell_classes += " is-stale"
        if len(maps) > 1:
            shell_classes += " is-split"

        shell_html = [
            f"<div class='{shell_classes}' id='knowledge-graph-panel' ",
            f"data-kg-status='{html.escape(status, quote=True)}' ",
            "data-kg-layout='mindmap' data-kg-schema='v2'>",
        ]
        shell_html.append(self._render_preview_card(graph, maps, status))
        shell_html.append("<div class='kg-viewer-overlay' data-kg-viewer-overlay='true' hidden>")
        shell_html.append("<div class='kg-viewer-dialog'>")
        shell_html.append("<div class='kg-viewer-toolbar'>")
        shell_html.append(
            "<button type='button' data-kg-viewer-action='zoom-in'>+</button>"
        )
        shell_html.append(
            "<button type='button' data-kg-viewer-action='zoom-out'>-</button>"
        )
        shell_html.append(
            "<button type='button' data-kg-viewer-action='fit'>Fit</button>"
        )
        shell_html.append(
            "<button type='button' data-kg-viewer-action='reset'>Reset</button>"
        )
        shell_html.append(
            "<button type='button' data-kg-viewer-close='true'>Close</button>"
        )
        shell_html.append("</div>")
        shell_html.append(
            "<div class='kg-viewer-viewport' data-kg-viewer-viewport='true'>"
        )
        shell_html.append(
            "<div class='kg-viewer-stage' data-kg-viewer-stage='true'>"
        )
        shell_html.append(self._render_graph_canvas(graph, focus_file_id))
        shell_html.append("</div>")
        shell_html.append("</div>")
        shell_html.append("</div>")
        shell_html.append("</div>")
        shell_html.append("</div>")
        return "".join(shell_html)
