from __future__ import annotations

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
    def __init__(self, service):
        self._service = service

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
            "knowledge_points": knowledge_points,
        }

    def shared_keywords(
        self, left: dict[str, Any], right: dict[str, Any]
    ) -> list[str]:
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

    def build_conversation_graph(
        self, conversation_id: str, sources: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        file_graphs = [
            self._service._build_file_graph(file_id, source)
            for file_id, source in sources.items()
        ]

        systems: list[dict[str, Any]] = []
        file_cards: list[dict[str, Any]] = []
        knowledge_points: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        support_pages: dict[str, list[str]] = {}
        support_chunk_ids: dict[str, list[str]] = {}

        for system_index, grouped_file_graphs in enumerate(
            self._service._group_files_into_systems(file_graphs), start=1
        ):
            system_id = f"system::{system_index}"
            related_file_ids = [graph["file_id"] for graph in grouped_file_graphs]
            shared_keywords = _limit_unique_strings(
                [
                    keyword
                    for graph in grouped_file_graphs
                    for keyword in graph.get("top_keywords", [])
                ],
                6,
            )
            system_support_pages = {
                file_id: graph.get("summary_support_pages", {}).get(file_id, [])
                for graph in grouped_file_graphs
                for file_id in [graph["file_id"]]
            }
            system_support_chunk_ids = {
                file_id: graph.get("summary_support_chunk_ids", {}).get(file_id, [])
                for graph in grouped_file_graphs
                for file_id in [graph["file_id"]]
            }

            themes: list[dict[str, Any]] = []
            if len(grouped_file_graphs) > 1:
                for idx, keyword in enumerate(shared_keywords[:4], start=1):
                    theme = {
                        "id": f"theme::{system_index}::{idx}",
                        "type": "system_relation",
                        "label": keyword,
                        "summary": f"Shared theme '{keyword}' across "
                        f"{len(related_file_ids)} files.",
                        "related_file_ids": related_file_ids,
                        "support_pages": system_support_pages,
                        "support_chunk_ids": system_support_chunk_ids,
                    }
                    themes.append(theme)
                    edges.append(
                        {
                            "source": system_id,
                            "target": theme["id"],
                            "type": "system_theme",
                            "related_file_ids": related_file_ids,
                        }
                    )

            if len(grouped_file_graphs) == 1:
                file_name = grouped_file_graphs[0].get(
                    "file_name", grouped_file_graphs[0]["file_id"]
                )
                label = f"{file_name} system"
                summary = f"Centered on {file_name} and its core ideas."
            else:
                label = "Shared knowledge system"
                summary = (
                    f"Connects {len(grouped_file_graphs)} sources through "
                    f"{', '.join(shared_keywords[:3])}."
                    if shared_keywords
                    else f"Connects {len(grouped_file_graphs)} uploaded sources."
                )

            systems.append(
                {
                    "id": system_id,
                    "type": "knowledge_system",
                    "label": label,
                    "summary": summary,
                    "related_file_ids": related_file_ids,
                    "shared_keywords": shared_keywords,
                    "support_pages": system_support_pages,
                    "support_chunk_ids": system_support_chunk_ids,
                    "themes": themes,
                }
            )

            for graph in grouped_file_graphs:
                file_id = graph["file_id"]
                file_card = {
                    "id": f"file::{file_id}",
                    "type": "file_summary",
                    "system_id": system_id,
                    "file_id": file_id,
                    "label": graph.get("file_name", file_id),
                    "summary": graph.get("summary", ""),
                    "related_file_ids": related_file_ids,
                    "support_pages": graph.get("summary_support_pages", {}),
                    "support_chunk_ids": graph.get("summary_support_chunk_ids", {}),
                    "top_keywords": graph.get("top_keywords", [])[:6],
                }
                file_cards.append(file_card)
                edges.append(
                    {
                        "source": system_id,
                        "target": file_card["id"],
                        "type": "system_file",
                        "related_file_ids": related_file_ids,
                    }
                )

                for point in graph.get("knowledge_points", []):
                    point = dict(point)
                    point["system_id"] = system_id
                    point["related_file_ids"] = related_file_ids
                    knowledge_points.append(point)
                    edges.append(
                        {
                            "source": file_card["id"],
                            "target": point["id"],
                            "type": "file_point",
                            "related_file_ids": related_file_ids,
                        }
                    )

                self._service._merge_support_dict(
                    support_pages, graph.get("summary_support_pages", {}), 24
                )
                self._service._merge_support_dict(
                    support_chunk_ids, graph.get("summary_support_chunk_ids", {}), 36
                )
                for point in graph.get("knowledge_points", []):
                    self._service._merge_support_dict(
                        support_pages, point.get("support_pages", {}), 24
                    )
                    self._service._merge_support_dict(
                        support_chunk_ids, point.get("support_chunk_ids", {}), 36
                    )

        return {
            "conversation_id": conversation_id,
            "source_ids": list(sources.keys()),
            "systems": systems,
            "file_cards": file_cards,
            "knowledge_points": knowledge_points,
            "edges": edges,
            "support_pages": support_pages,
            "support_chunk_ids": support_chunk_ids,
        }
