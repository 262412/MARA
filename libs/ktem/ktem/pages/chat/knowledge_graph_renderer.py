from __future__ import annotations

import html
import json
from collections import defaultdict
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
    def __init__(self, service):
        self._service = service

    def make_graph_context(
        self, item: dict[str, Any], focus_file_id: str
    ) -> dict[str, Any]:
        related_file_ids = _limit_unique_strings(
            [focus_file_id] + list(item.get("related_file_ids", []) or []),
            12,
        )
        return {
            "label": item.get("label", ""),
            "type": item.get("type", ""),
            "focus_file_id": focus_file_id,
            "related_file_ids": related_file_ids,
            "support_pages": item.get("support_pages", {}),
            "support_chunk_ids": item.get("support_chunk_ids", {}),
        }

    def build_suggested_question(self, item: dict[str, Any]) -> str:
        label = str(item.get("label", "") or "this topic")
        item_type = str(item.get("type", "") or "")
        if item_type == "knowledge_root":
            return (
                "Can you summarize the major knowledge systems in this "
                "conversation and explain how they differ?"
            )
        if item_type == "knowledge_system":
            return (
                f"Can you explain the knowledge system '{label}' and how it "
                "connects across uploaded files?"
            )
        if item_type == "file_summary":
            return (
                f"Can you explain the role of '{label}' and its most important "
                "ideas in the selected file?"
            )
        if item_type == "system_relation":
            return (
                f"Can you explain why '{label}' is a shared theme across these files?"
            )
        return f"Can you explain this knowledge point: '{label}'?"

    def build_prompt(self, item: dict[str, Any], focus_file_id: str) -> str:
        label = str(item.get("label", "") or "this topic")
        graph_context = self.make_graph_context(item, focus_file_id)
        related_ids = list(graph_context.get("related_file_ids", []) or [])

        if len(related_ids) > 1:
            relation_clause = (
                " Then add how it connects with related files from the same "
                "conversation."
            )
        else:
            relation_clause = (
                " Then mention whether any cross-file relation is supported."
            )

        return (
            f"Please explain '{label}' using current-file/current-page evidence first."
            + relation_clause
        )

    def payload_attr(self, item: dict[str, Any], focus_file_id: str) -> str:
        summary = str(item.get("summary", "") or "")
        if not summary:
            summary = str(item.get("label", "") or "")
        prompt = self.build_prompt(item, focus_file_id)
        payload = {
            "graph_context": self.make_graph_context(item, focus_file_id),
            "node_label": str(item.get("label", "") or ""),
            "node_type": str(item.get("type", "") or ""),
            "summary": summary,
            "prompt": prompt,
            "suggested_question": prompt,
        }
        return html.escape(json.dumps(payload, ensure_ascii=False), quote=True)

    def render_empty_html(self, message: str, hint: str = "") -> str:
        hint_html = f"<p class='kg-empty__hint'>{html.escape(hint)}</p>" if hint else ""
        return (
            "<div class='knowledge-graph-shell is-empty'>"
            "<div class='kg-empty'>"
            f"<h4>{html.escape(message)}</h4>"
            f"{hint_html}"
            "</div>"
            "</div>"
        )

    def render_graph_html(
        self, graph: dict[str, Any], focus_file_id: str, status: str
    ) -> str:
        systems = list(graph.get("systems", []) or [])
        file_cards = list(graph.get("file_cards", []) or [])
        knowledge_points = list(graph.get("knowledge_points", []) or [])

        if not systems:
            return self.render_empty_html(
                "No knowledge graph available yet.",
                "Generate a graph after uploading related sources to this "
                "conversation.",
            )

        file_cards_by_system: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for file_card in file_cards:
            file_cards_by_system[str(file_card.get("system_id", ""))].append(file_card)

        points_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for point in knowledge_points:
            points_by_file[str(point.get("file_id", ""))].append(point)

        systems.sort(
            key=lambda item: (
                0 if focus_file_id in (item.get("related_file_ids", []) or []) else 1,
                str(item.get("label", "")),
            )
        )

        root_item = {
            "id": "root::conversation",
            "type": "knowledge_root",
            "label": "Conversation Knowledge Tree",
            "summary": (
                f"{len(file_cards)} file node(s), "
                f"{len(knowledge_points)} knowledge point(s), "
                f"{len(systems)} system(s)."
            ),
            "related_file_ids": list(graph.get("source_ids", []) or []),
            "support_pages": graph.get("support_pages", {}) or {},
            "support_chunk_ids": graph.get("support_chunk_ids", {}) or {},
        }

        system_html_parts: list[str] = []
        for system in systems:
            system_id = str(system.get("id", "") or "")
            file_group = file_cards_by_system.get(system_id, [])
            file_group.sort(
                key=lambda item: (
                    0 if item.get("file_id") == focus_file_id else 1,
                    str(item.get("label", "")).lower(),
                )
            )
            is_focus_system = bool(
                focus_file_id
                and focus_file_id in (system.get("related_file_ids", []) or [])
            )
            system_classes = (
                "kg-tree-item kg-tree-item--system kg-system is-focused"
                if is_focus_system
                else "kg-tree-item kg-tree-item--system kg-system"
            )
            system_html_parts.append(f"<li class='{system_classes}'>")
            system_html_parts.append(
                "<button type='button' "
                "class='kg-tree-node kg-tree-node--system kg-pill "
                "kg-system__title' "
                f'data-kg-payload="{self.payload_attr(system, focus_file_id)}">'
                f"{html.escape(str(system.get('label', 'Knowledge system')))}"
                "</button>"
            )
            system_html_parts.append(
                "<p class='kg-tree-item__meta kg-system__summary'>"
                f"{html.escape(str(system.get('summary', '') or ''))}"
                "</p>"
            )

            themes = list(system.get("themes", []) or [])
            if themes:
                system_html_parts.append("<div class='kg-tree-item__keywords'>")
                for theme in themes:
                    system_html_parts.append(
                        "<button type='button' "
                        "class='kg-tree-node kg-tree-node--theme "
                        "kg-theme-node' "
                        f'data-kg-payload="{self.payload_attr(theme, focus_file_id)}">'
                        f"{html.escape(str(theme.get('label', '') or 'theme'))}"
                        "</button>"
                    )
                system_html_parts.append("</div>")

            system_html_parts.append(
                "<ul class='kg-tree-list kg-tree-list--files kg-system__files'>"
            )
            for file_card in file_group:
                file_id = str(file_card.get("file_id", "") or "")
                safe_file_id = html.escape(file_id, quote=True)
                is_focused_file = bool(focus_file_id and file_id == focus_file_id)
                file_classes = (
                    "kg-tree-item kg-tree-item--file kg-file-card is-focused"
                    if is_focused_file
                    else "kg-tree-item kg-tree-item--file kg-file-card"
                )
                system_html_parts.append(
                    f"<li class='{file_classes}' data-kg-file-card='{safe_file_id}'>"
                )
                system_html_parts.append(
                    "<button type='button' "
                    "class='kg-tree-node kg-tree-node--file "
                    "kg-file-card__title' "
                    f'data-kg-payload="{self.payload_attr(file_card, focus_file_id)}">'
                    f"{html.escape(str(file_card.get('label', file_id) or file_id))}"
                    "</button>"
                )
                system_html_parts.append(
                    "<p class='kg-tree-item__meta kg-file-card__summary'>"
                    f"{html.escape(str(file_card.get('summary', '') or ''))}"
                    "</p>"
                )

                file_points = list(points_by_file.get(file_id, []))
                collapsed_points: list[dict[str, Any]] = []
                visible_points = file_points
                if not is_focused_file and len(file_group) > 1:
                    visible_points = file_points[:2]
                    collapsed_points = file_points[2:]

                if visible_points or collapsed_points:
                    system_html_parts.append(
                        "<ul class='kg-tree-list kg-tree-list--points kg-point-list'>"
                    )
                    for point in visible_points:
                        point_payload = self.payload_attr(point, focus_file_id)
                        point_label = html.escape(
                            str(point.get("label", "") or "Knowledge point")
                        )
                        system_html_parts.append(
                            "<li class='kg-tree-item kg-tree-item--point'>"
                            "<button type='button' "
                            "class='kg-tree-node kg-tree-node--point "
                            "kg-point-card' "
                            f'data-kg-payload="{point_payload}">'
                            f"{point_label}"
                            "</button>"
                            "</li>"
                        )

                    for point in collapsed_points:
                        point_payload = self.payload_attr(point, focus_file_id)
                        point_label = html.escape(
                            str(point.get("label", "") or "Knowledge point")
                        )
                        system_html_parts.append(
                            "<li class='kg-tree-item kg-tree-item--point "
                            "kg-point-item is-collapsed-point'>"
                            "<button type='button' "
                            "class='kg-tree-node kg-tree-node--point "
                            "kg-point-card' "
                            f'data-kg-payload="{point_payload}">'
                            f"{point_label}"
                            "</button>"
                            "</li>"
                        )

                    if collapsed_points:
                        more_label = f"+{len(collapsed_points)} more point(s)"
                        less_label = "Show less"
                        system_html_parts.append(
                            "<li class='kg-tree-item kg-tree-item--more'>"
                            "<button type='button' "
                            "class='kg-point-more kg-point-more--toggle' "
                            f"data-kg-toggle-points='{safe_file_id}' "
                            "data-kg-more-label='"
                            f"{html.escape(more_label, quote=True)}' "
                            "data-kg-less-label='"
                            f"{html.escape(less_label, quote=True)}' "
                            "aria-expanded='false'>"
                            f"{html.escape(more_label)}"
                            "</button>"
                            "</li>"
                        )
                    system_html_parts.append("</ul>")
                system_html_parts.append("</li>")
            system_html_parts.append("</ul>")
            system_html_parts.append("</li>")

        shell_classes = "knowledge-graph-shell"
        if status == "stale":
            shell_classes += " is-stale"

        return (
            f"<div class='{shell_classes}' id='knowledge-graph-panel' "
            f"data-kg-status='{html.escape(status, quote=True)}'>"
            + "<div class='kg-tree-root'>"
            + "<button type='button' class='kg-tree-node kg-tree-node--root' "
            + f'data-kg-payload="{self.payload_attr(root_item, focus_file_id)}">'
            + html.escape(str(root_item.get("label", "Conversation Knowledge Tree")))
            + "</button>"
            + "<p class='kg-tree-root__meta'>"
            + html.escape(str(root_item.get("summary", "") or ""))
            + "</p>"
            + "</div>"
            + "<ul class='kg-tree-list kg-tree-list--systems'>"
            + "".join(system_html_parts)
            + "</ul>"
            + "</div>"
        )
