from __future__ import annotations

import html
import json
import re
import threading
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ktem.llms.manager import llms
from kotaemon.base import HumanMessage, SystemMessage
from sqlalchemy import select
from sqlmodel import Session
from theflow.settings import settings as flowsettings

from ktem.db.engine import engine


_EN_STOPWORDS = {
    "about",
    "after",
    "also",
    "among",
    "been",
    "being",
    "between",
    "both",
    "can",
    "does",
    "each",
    "from",
    "have",
    "into",
    "more",
    "most",
    "other",
    "over",
    "such",
    "than",
    "that",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "using",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
}

_TOKEN_PATTERN = re.compile(r"[A-Za-z][A-Za-z0-9_\-/]{2,}|[\u4e00-\u9fff]{2,}")
_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?;])\s+|\n+")


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


class GlobalKnowledgeGraphService:
    """Conversation-scoped knowledge graph service."""

    def __init__(self, app, index):
        self._app = app
        self._index = index
        self._lock = threading.Lock()

        root_dir = Path(getattr(flowsettings, "KH_APP_DATA_DIR", Path.cwd()))
        self._storage_dir = root_dir / "knowledge_graph" / "conversations"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_source_ids(source_ids: list[str] | str | None) -> list[str]:
        if source_ids in (None, ""):
            return []
        if not isinstance(source_ids, list):
            source_ids = [source_ids]
        return _limit_unique_strings([str(item or "").strip() for item in source_ids], 256)

    @staticmethod
    def _normalize_whitespace(value: str) -> str:
        return " ".join(str(value or "").split()).strip()

    @staticmethod
    def _normalize_term(term: str) -> str:
        text = " ".join(str(term or "").split()).strip()
        if not text:
            return ""
        if re.search(r"[A-Za-z]", text):
            text = text.lower()
            if text.endswith("s") and len(text) > 4:
                text = text[:-1]
        return text

    def _extract_keywords(self, text: str, limit: int = 8) -> list[str]:
        counter: Counter[str] = Counter()
        display_names: dict[str, str] = {}
        for token in _TOKEN_PATTERN.findall(str(text or "")):
            normalized = self._normalize_term(token)
            if not normalized:
                continue
            if re.search(r"[A-Za-z]", normalized):
                if len(normalized) < 4 or normalized in _EN_STOPWORDS:
                    continue
            display_names.setdefault(normalized, token)
            counter[normalized] += 1

        results = []
        for normalized, _ in counter.most_common(limit * 2):
            results.append(display_names.get(normalized, normalized))
            if len(results) >= limit:
                break
        return results

    def _get_storage_path(self, conversation_id: str) -> Path:
        conversation_key = str(conversation_id or "draft")
        safe_key = re.sub(r"[^A-Za-z0-9_\-]", "_", conversation_key)
        return self._storage_dir / f"{safe_key}.json"

    def _load_cached_state(self, conversation_id: str) -> dict[str, Any]:
        path = self._get_storage_path(conversation_id)
        if not path.exists():
            return {"conversation_id": conversation_id, "manifest": {}, "graph": None}
        try:
            with path.open("r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
        except Exception:
            return {"conversation_id": conversation_id, "manifest": {}, "graph": None}
        data.setdefault("conversation_id", conversation_id)
        data.setdefault("manifest", {})
        data.setdefault("graph", None)
        return data

    def _save_cached_state(self, conversation_id: str, state: dict[str, Any]) -> None:
        path = self._get_storage_path(conversation_id)
        with path.open("w", encoding="utf-8") as file_obj:
            json.dump(state, file_obj, ensure_ascii=False, indent=2)

    def _load_sources(self, source_ids: list[str]) -> dict[str, dict[str, Any]]:
        source_ids = self._normalize_source_ids(source_ids)
        if not source_ids or self._index is None:
            return {}

        source_table = self._index._resources["Source"]
        with Session(engine) as session:
            rows = session.execute(
                select(source_table).where(source_table.id.in_(source_ids))
            ).all()

        sources_by_id: dict[str, dict[str, Any]] = {}
        for (row,) in rows:
            file_id = str(getattr(row, "id", "") or "")
            if not file_id:
                continue
            sources_by_id[file_id] = {
                "id": file_id,
                "name": str(getattr(row, "name", "") or file_id),
                "path": str(getattr(row, "path", "") or ""),
                "size": int(getattr(row, "size", 0) or 0),
                "date_created": str(getattr(row, "date_created", "") or ""),
            }

        ordered_sources: dict[str, dict[str, Any]] = {}
        for source_id in source_ids:
            if source_id in sources_by_id:
                ordered_sources[source_id] = sources_by_id[source_id]
        return ordered_sources

    @staticmethod
    def _make_signature(source: dict[str, Any]) -> str:
        return "|".join(
            [
                str(source.get("id", "")),
                str(source.get("name", "")),
                str(source.get("path", "")),
                str(source.get("size", 0)),
                str(source.get("date_created", "")),
            ]
        )

    def _load_file_docs(self, file_id: str) -> list[Any]:
        if self._index is None:
            return []
        index_table = self._index._resources["Index"]
        docstore = self._index._resources["DocStore"]
        with Session(engine) as session:
            stmt = select(index_table.target_id).where(
                index_table.source_id == file_id,
                index_table.relation_type == "document",
            )
            doc_ids = [row[0] for row in session.execute(stmt).all()]
        if not doc_ids:
            return []
        docs = docstore.get(doc_ids)
        if docs is None:
            return []
        if not isinstance(docs, list):
            docs = [docs]
        return [doc for doc in docs if doc]

    def _split_sentences(self, text: str) -> list[str]:
        cleaned = self._normalize_whitespace(text)
        if not cleaned:
            return []
        pieces = _SENTENCE_SPLIT_PATTERN.split(cleaned)
        sentences = []
        for piece in pieces:
            sentence = self._normalize_whitespace(piece)
            if len(sentence) < 16:
                continue
            sentences.append(sentence)
        if not sentences and cleaned:
            sentences.append(cleaned)
        return sentences

    @staticmethod
    def _trim_sentence(text: str, limit: int = 120) -> str:
        normalized = " ".join(str(text or "").split()).strip()
        if len(normalized) <= limit:
            return normalized
        trimmed = normalized[: limit - 1].rstrip(" ,.;:")
        return f"{trimmed}..."

    def _make_sentence_candidates(self, docs: list[Any]) -> tuple[list[dict[str, Any]], list[str]]:
        candidates: list[dict[str, Any]] = []
        pages_seen: list[str] = []
        for doc in docs:
            metadata = getattr(doc, "metadata", {}) or {}
            doc_type = str(metadata.get("type", "text") or "text")
            if doc_type not in {"text", "table"}:
                continue

            page_label = str(metadata.get("page_label", "") or "")
            doc_id = str(getattr(doc, "doc_id", "") or "")
            doc_text = str(getattr(doc, "text", "") or "").strip()
            if page_label:
                pages_seen.append(page_label)

            for sentence in self._split_sentences(doc_text):
                keywords = [
                    self._normalize_term(keyword)
                    for keyword in self._extract_keywords(sentence, limit=6)
                ]
                keywords = [keyword for keyword in keywords if keyword]
                candidates.append(
                    {
                        "text": sentence,
                        "page_label": page_label,
                        "doc_id": doc_id,
                        "keywords": keywords,
                    }
                )
        return candidates, _limit_unique_strings(pages_seen, 24)

    @staticmethod
    def _sentence_length_multiplier(length: int) -> float:
        if 24 <= length <= 150:
            return 1.0
        if 16 <= length <= 220:
            return 0.82
        return 0.55

    def _score_candidates(self, candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
        keyword_counter: Counter[str] = Counter()
        for candidate in candidates:
            keyword_counter.update(candidate.get("keywords", []))

        for candidate in candidates:
            sentence = candidate.get("text", "")
            keywords = candidate.get("keywords", [])
            score = sum(keyword_counter[keyword] for keyword in set(keywords))
            score += len(set(keywords)) * 0.6
            score *= self._sentence_length_multiplier(len(sentence))
            candidate["score"] = score

        candidates.sort(
            key=lambda item: (
                -float(item.get("score", 0.0) or 0.0),
                len(str(item.get("text", "") or "")),
            )
        )
        top_keywords = []
        for keyword, _ in keyword_counter.most_common(10):
            if not keyword:
                continue
            top_keywords.append(keyword)
            if len(top_keywords) >= 8:
                break
        return candidates, top_keywords

    @staticmethod
    def _is_duplicate_point(existing_points: list[dict[str, Any]], sentence: str) -> bool:
        sentence_norm = sentence.lower()
        for point in existing_points:
            label = str(point.get("label", "") or "").lower()
            if not label:
                continue
            if sentence_norm == label:
                return True
            if sentence_norm in label or label in sentence_norm:
                return True
        return False

    @staticmethod
    def _extract_first_json_object(text: str) -> str:
        content = str(text or "")
        start = content.find("{")
        if start < 0:
            return ""
        depth = 0
        in_string = False
        escape = False
        for index in range(start, len(content)):
            char = content[index]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    in_string = False
                continue
            if char == '"':
                in_string = True
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return content[start : index + 1]
        return ""

    def _parse_outline_json(self, raw_text: str) -> dict[str, Any] | None:
        payload = str(raw_text or "").strip()
        if not payload:
            return None

        candidates = [payload]
        fenced = re.findall(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", payload, flags=re.IGNORECASE)
        candidates.extend(fenced)
        first_object = self._extract_first_json_object(payload)
        if first_object:
            candidates.append(first_object)

        parsed_obj: dict[str, Any] | None = None
        for candidate in candidates:
            try:
                parsed = json.loads(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                parsed_obj = parsed
                break

        if not parsed_obj:
            return None

        summary = self._normalize_whitespace(str(parsed_obj.get("summary", "") or ""))
        if not summary:
            return None

        points_raw = parsed_obj.get("knowledge_points")
        if points_raw is None:
            points_raw = parsed_obj.get("points")

        normalized_points: list[dict[str, Any]] = []
        if isinstance(points_raw, list):
            for point in points_raw:
                label = ""
                keywords: list[str] = []
                if isinstance(point, str):
                    label = self._normalize_whitespace(point)
                elif isinstance(point, dict):
                    label = self._normalize_whitespace(str(point.get("label") or point.get("point") or ""))
                    keywords_raw = point.get("keywords", [])
                    if isinstance(keywords_raw, list):
                        keywords = _limit_unique_strings(
                            [self._normalize_term(str(item or "")) for item in keywords_raw],
                            6,
                        )
                        keywords = [item for item in keywords if item]
                if not label:
                    continue
                normalized_points.append({"label": label, "keywords": keywords})
                if len(normalized_points) >= 6:
                    break

        return {
            "summary": summary,
            "knowledge_points": normalized_points,
        }

    def _generate_outline_with_llm(self, file_name: str, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None
        try:
            model = llms.get_default()
        except Exception:
            return None

        evidence_lines = []
        for index, candidate in enumerate(candidates[:16], start=1):
            sentence = self._trim_sentence(str(candidate.get("text", "") or ""), 220)
            if not sentence:
                continue
            page_label = str(candidate.get("page_label", "") or "")
            chunk_id = str(candidate.get("doc_id", "") or "")
            evidence_lines.append(f"[{index}] page={page_label or 'N/A'} chunk={chunk_id or 'N/A'} text={sentence}")

        if not evidence_lines:
            return None

        system_prompt = (
            "You are a precise document analyst. "
            "Use only the provided evidence and return strict JSON only."
        )
        user_prompt = (
            f"Document: {file_name}\n"
            "Output JSON schema:\n"
            "{\n"
            "  \"summary\": \"...\",\n"
            "  \"knowledge_points\": [\n"
            "    {\"label\": \"...\", \"keywords\": [\"...\"]}\n"
            "  ]\n"
            "}\n"
            "Please produce one summary and 3-6 knowledge points.\n"
            "Evidence:\n"
            + "\n".join(evidence_lines)
        )
        try:
            response = model(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt),
                ]
            )
        except Exception:
            return None

        response_text = ""
        if isinstance(response, str):
            response_text = response
        else:
            response_text = str(getattr(response, "text", "") or getattr(response, "content", "") or "")
        return self._parse_outline_json(response_text)

    def _build_file_graph(self, file_id: str, source: dict[str, Any]) -> dict[str, Any]:
        docs = self._load_file_docs(file_id)
        candidates, pages_seen = self._make_sentence_candidates(docs)
        candidates, top_keywords = self._score_candidates(candidates)

        llm_outline = self._generate_outline_with_llm(source.get("name", file_id), candidates[:16])

        if llm_outline and llm_outline.get("knowledge_points"):
            summary_text = self._trim_sentence(llm_outline.get("summary", ""), 132)
            if not summary_text and candidates:
                summary_text = self._trim_sentence(candidates[0].get("text", ""), 132)
            summary_candidate = candidates[0] if candidates else {"page_label": "", "doc_id": ""}

            knowledge_points: list[dict[str, Any]] = []
            for point in llm_outline.get("knowledge_points", []):
                label = self._trim_sentence(str(point.get("label", "") or ""), 110)
                if not label or self._is_duplicate_point(knowledge_points, label):
                    continue
                match = candidates[len(knowledge_points)] if len(candidates) > len(knowledge_points) else summary_candidate
                support_pages = _limit_unique_strings([match.get("page_label", "")], 8)
                support_chunk_ids = _limit_unique_strings([match.get("doc_id", "")], 8)
                knowledge_points.append(
                    {
                        "id": f"point::{file_id}::{len(knowledge_points) + 1}",
                        "type": "knowledge_point",
                        "file_id": file_id,
                        "label": label,
                        "keywords": _limit_unique_strings(
                            list(point.get("keywords", [])) + self._extract_keywords(label, limit=6),
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
                summary_text = self._trim_sentence(summary_candidate.get("text", ""), 132)
            else:
                summary_text = f"{source.get('name', file_id)} contains indexed content for this conversation."
                summary_candidate = {"page_label": "", "doc_id": ""}

            knowledge_points = []
            for candidate in candidates:
                label = self._trim_sentence(candidate.get("text", ""), 110)
                if not label or self._is_duplicate_point(knowledge_points, label):
                    continue
                support_pages = _limit_unique_strings([candidate.get("page_label", "")], 8)
                support_chunk_ids = _limit_unique_strings([candidate.get("doc_id", "")], 8)
                knowledge_points.append(
                    {
                        "id": f"point::{file_id}::{len(knowledge_points) + 1}",
                        "type": "knowledge_point",
                        "file_id": file_id,
                        "label": label,
                        "keywords": _limit_unique_strings(candidate.get("keywords", []), 6),
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
                        "label": self._trim_sentence(summary_text, 110),
                        "keywords": top_keywords[:4],
                        "related_file_ids": [file_id],
                        "support_pages": {file_id: _limit_unique_strings([summary_candidate.get("page_label", "")], 8)},
                        "support_chunk_ids": {file_id: _limit_unique_strings([summary_candidate.get("doc_id", "")], 8)},
                    }
                )

        summary_pages = _limit_unique_strings(
            [summary_candidate.get("page_label", "")] + pages_seen,
            12,
        )
        summary_chunks = _limit_unique_strings([summary_candidate.get("doc_id", "")], 12)

        return {
            "file_id": file_id,
            "file_name": source.get("name", file_id),
            "signature": self._make_signature(source),
            "summary": summary_text,
            "pages": pages_seen,
            "top_keywords": top_keywords,
            "summary_support_pages": {file_id: summary_pages},
            "summary_support_chunk_ids": {file_id: summary_chunks},
            "knowledge_points": knowledge_points,
        }

    def _shared_keywords(self, left: dict[str, Any], right: dict[str, Any]) -> list[str]:
        right_keywords = set(right.get("top_keywords", []))
        shared = [keyword for keyword in left.get("top_keywords", []) if keyword in right_keywords]
        return _limit_unique_strings(shared, 6)

    def _group_files_into_systems(self, file_graphs: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        file_ids = [graph["file_id"] for graph in file_graphs]
        union_find = _UnionFind(file_ids)
        graph_map = {graph["file_id"]: graph for graph in file_graphs}

        for index, left_id in enumerate(file_ids):
            for right_id in file_ids[index + 1 :]:
                shared = self._shared_keywords(graph_map[left_id], graph_map[right_id])
                if len(shared) >= 2:
                    union_find.union(left_id, right_id)

        grouped_ids: dict[str, list[str]] = defaultdict(list)
        for file_id in file_ids:
            grouped_ids[union_find.find(file_id)].append(file_id)

        ordered_systems: list[list[dict[str, Any]]] = []
        for cluster_ids in grouped_ids.values():
            cluster_graphs = [graph_map[file_id] for file_id in cluster_ids]
            cluster_graphs.sort(key=lambda item: item.get("file_name", item["file_id"]).lower())
            ordered_systems.append(cluster_graphs)

        ordered_systems.sort(
            key=lambda cluster: (
                -len(cluster),
                cluster[0].get("file_name", cluster[0]["file_id"]).lower(),
            )
        )
        return ordered_systems

    @staticmethod
    def _merge_support_dict(target: dict[str, list[str]], source: dict[str, list[str]] | None, limit: int) -> dict[str, list[str]]:
        for file_id, values in (source or {}).items():
            key = str(file_id or "").strip()
            if not key:
                continue
            target[key] = _limit_unique_strings(target.get(key, []) + list(values or []), limit)
        return target

    def _build_conversation_graph(self, conversation_id: str, sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
        file_graphs = [
            self._build_file_graph(file_id, source)
            for file_id, source in sources.items()
        ]

        systems: list[dict[str, Any]] = []
        file_cards: list[dict[str, Any]] = []
        knowledge_points: list[dict[str, Any]] = []
        edges: list[dict[str, Any]] = []
        support_pages: dict[str, list[str]] = {}
        support_chunk_ids: dict[str, list[str]] = {}

        for system_index, grouped_file_graphs in enumerate(self._group_files_into_systems(file_graphs), start=1):
            system_id = f"system::{system_index}"
            related_file_ids = [graph["file_id"] for graph in grouped_file_graphs]
            shared_keywords = _limit_unique_strings(
                [keyword for graph in grouped_file_graphs for keyword in graph.get("top_keywords", [])],
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
                        "summary": (
                            f"Shared theme '{keyword}' across {len(related_file_ids)} files."
                        ),
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
                file_name = grouped_file_graphs[0].get("file_name", grouped_file_graphs[0]["file_id"])
                label = f"{file_name} system"
                summary = f"Centered on {file_name} and its core ideas."
            else:
                label = "Shared knowledge system"
                summary = (
                    f"Connects {len(grouped_file_graphs)} sources through {', '.join(shared_keywords[:3])}."
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

                self._merge_support_dict(support_pages, graph.get("summary_support_pages", {}), 24)
                self._merge_support_dict(support_chunk_ids, graph.get("summary_support_chunk_ids", {}), 36)
                for point in graph.get("knowledge_points", []):
                    self._merge_support_dict(support_pages, point.get("support_pages", {}), 24)
                    self._merge_support_dict(support_chunk_ids, point.get("support_chunk_ids", {}), 36)

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

    def _make_graph_context(self, item: dict[str, Any], focus_file_id: str) -> dict[str, Any]:
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

    def _build_suggested_question(self, item: dict[str, Any]) -> str:
        label = str(item.get("label", "") or "this topic")
        item_type = str(item.get("type", "") or "")
        if item_type == "knowledge_root":
            return "Can you summarize the major knowledge systems in this conversation and explain how they differ?"
        if item_type == "knowledge_system":
            return f"Can you explain the knowledge system '{label}' and how it connects across uploaded files?"
        if item_type == "file_summary":
            return f"Can you explain the role of '{label}' and its most important ideas in the selected file?"
        if item_type == "system_relation":
            return f"Can you explain why '{label}' is a shared theme across these files?"
        return f"Can you explain this knowledge point: '{label}'?"

    def _build_prompt(self, item: dict[str, Any], focus_file_id: str) -> str:
        label = str(item.get("label", "") or "this topic")
        graph_context = self._make_graph_context(item, focus_file_id)
        related_ids = list(graph_context.get("related_file_ids", []) or [])

        if len(related_ids) > 1:
            relation_clause = (
                " Then add how it connects with related files from the same conversation."
            )
        else:
            relation_clause = " Then mention whether any cross-file relation is supported."

        return (
            f"Please explain '{label}' using current-file/current-page evidence first."
            + relation_clause
        )

    def _payload_attr(self, item: dict[str, Any], focus_file_id: str) -> str:
        summary = str(item.get("summary", "") or "")
        if not summary:
            summary = str(item.get("label", "") or "")
        prompt = self._build_prompt(item, focus_file_id)
        payload = {
            "graph_context": self._make_graph_context(item, focus_file_id),
            "node_label": str(item.get("label", "") or ""),
            "node_type": str(item.get("type", "") or ""),
            "summary": summary,
            "prompt": prompt,
            "suggested_question": prompt,
        }
        return html.escape(json.dumps(payload, ensure_ascii=False), quote=True)

    def _render_empty_html(self, message: str, hint: str = "") -> str:
        hint_html = f"<p class='kg-empty__hint'>{html.escape(hint)}</p>" if hint else ""
        return (
            "<div class='knowledge-graph-shell is-empty'>"
            "<div class='kg-empty'>"
            f"<h4>{html.escape(message)}</h4>"
            f"{hint_html}"
            "</div>"
            "</div>"
        )

    def _render_graph_html(self, graph: dict[str, Any], focus_file_id: str, status: str) -> str:
        systems = list(graph.get("systems", []) or [])
        file_cards = list(graph.get("file_cards", []) or [])
        knowledge_points = list(graph.get("knowledge_points", []) or [])

        if not systems:
            return self._render_empty_html(
                "No knowledge graph available yet.",
                "Generate a graph after uploading related sources to this conversation.",
            )

        file_cards_by_system: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for file_card in file_cards:
            file_cards_by_system[str(file_card.get("system_id", ""))].append(file_card)

        points_by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for point in knowledge_points:
            points_by_file[str(point.get("file_id", ""))].append(point)

        systems.sort(key=lambda item: (0 if focus_file_id in (item.get("related_file_ids", []) or []) else 1, str(item.get("label", ""))))

        root_item = {
            "id": "root::conversation",
            "type": "knowledge_root",
            "label": "Conversation Knowledge Tree",
            "summary": (
                f"{len(file_cards)} file node(s), {len(knowledge_points)} knowledge point(s), {len(systems)} system(s)."
            ),
            "related_file_ids": list(graph.get("source_ids", []) or []),
            "support_pages": graph.get("support_pages", {}) or {},
            "support_chunk_ids": graph.get("support_chunk_ids", {}) or {},
        }

        system_html_parts: list[str] = []
        for system in systems:
            system_id = str(system.get("id", "") or "")
            file_group = file_cards_by_system.get(system_id, [])
            file_group.sort(key=lambda item: (0 if item.get("file_id") == focus_file_id else 1, str(item.get("label", "")).lower()))
            is_focus_system = bool(focus_file_id and focus_file_id in (system.get("related_file_ids", []) or []))
            system_classes = (
                "kg-tree-item kg-tree-item--system kg-system is-focused"
                if is_focus_system
                else "kg-tree-item kg-tree-item--system kg-system"
            )
            system_html_parts.append(f"<li class='{system_classes}'>")
            system_html_parts.append(
                "<button type='button' class='kg-tree-node kg-tree-node--system kg-pill kg-system__title' "
                f"data-kg-payload=\"{self._payload_attr(system, focus_file_id)}\">"
                f"{html.escape(str(system.get('label', 'Knowledge system')))}"
                "</button>"
            )
            system_html_parts.append(
                f"<p class='kg-tree-item__meta kg-system__summary'>{html.escape(str(system.get('summary', '') or ''))}</p>"
            )

            themes = list(system.get("themes", []) or [])
            if themes:
                system_html_parts.append("<div class='kg-tree-item__keywords'>")
                for theme in themes:
                    system_html_parts.append(
                        "<button type='button' class='kg-tree-node kg-tree-node--theme kg-theme-node' "
                        f"data-kg-payload=\"{self._payload_attr(theme, focus_file_id)}\">"
                        f"{html.escape(str(theme.get('label', '') or 'theme'))}"
                        "</button>"
                    )
                system_html_parts.append("</div>")

            system_html_parts.append("<ul class='kg-tree-list kg-tree-list--files kg-system__files'>")
            for file_card in file_group:
                file_id = str(file_card.get("file_id", "") or "")
                safe_file_id = html.escape(file_id, quote=True)
                is_focused_file = bool(focus_file_id and file_id == focus_file_id)
                file_classes = (
                    "kg-tree-item kg-tree-item--file kg-file-card is-focused"
                    if is_focused_file
                    else "kg-tree-item kg-tree-item--file kg-file-card"
                )
                system_html_parts.append(f"<li class='{file_classes}' data-kg-file-card='{safe_file_id}'>")
                system_html_parts.append(
                    "<button type='button' class='kg-tree-node kg-tree-node--file kg-file-card__title' "
                    f"data-kg-payload=\"{self._payload_attr(file_card, focus_file_id)}\">"
                    f"{html.escape(str(file_card.get('label', file_id) or file_id))}"
                    "</button>"
                )
                system_html_parts.append(
                    f"<p class='kg-tree-item__meta kg-file-card__summary'>{html.escape(str(file_card.get('summary', '') or ''))}</p>"
                )

                file_points = list(points_by_file.get(file_id, []))
                collapsed_points: list[dict[str, Any]] = []
                visible_points = file_points
                if not is_focused_file and len(file_group) > 1:
                    visible_points = file_points[:2]
                    collapsed_points = file_points[2:]

                if visible_points or collapsed_points:
                    system_html_parts.append("<ul class='kg-tree-list kg-tree-list--points kg-point-list'>")
                    for point in visible_points:
                        system_html_parts.append(
                            "<li class='kg-tree-item kg-tree-item--point'>"
                            "<button type='button' class='kg-tree-node kg-tree-node--point kg-point-card' "
                            f"data-kg-payload=\"{self._payload_attr(point, focus_file_id)}\">"
                            f"{html.escape(str(point.get('label', '') or 'Knowledge point'))}"
                            "</button>"
                            "</li>"
                        )

                    for point in collapsed_points:
                        system_html_parts.append(
                            "<li class='kg-tree-item kg-tree-item--point kg-point-item is-collapsed-point'>"
                            "<button type='button' class='kg-tree-node kg-tree-node--point kg-point-card' "
                            f"data-kg-payload=\"{self._payload_attr(point, focus_file_id)}\">"
                            f"{html.escape(str(point.get('label', '') or 'Knowledge point'))}"
                            "</button>"
                            "</li>"
                        )

                    if collapsed_points:
                        more_label = f"+{len(collapsed_points)} more point(s)"
                        less_label = "Show less"
                        system_html_parts.append(
                            "<li class='kg-tree-item kg-tree-item--more'>"
                            "<button type='button' class='kg-point-more kg-point-more--toggle' "
                            f"data-kg-toggle-points='{safe_file_id}' "
                            f"data-kg-more-label='{html.escape(more_label, quote=True)}' "
                            f"data-kg-less-label='{html.escape(less_label, quote=True)}' "
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
            f"<div class='{shell_classes}' id='knowledge-graph-panel' data-kg-status='{html.escape(status, quote=True)}'>"
            + "<div class='kg-tree-root'>"
            + "<button type='button' class='kg-tree-node kg-tree-node--root' "
            + f"data-kg-payload=\"{self._payload_attr(root_item, focus_file_id)}\">"
            + html.escape(str(root_item.get("label", "Conversation Knowledge Tree")))
            + "</button>"
            + f"<p class='kg-tree-root__meta'>{html.escape(str(root_item.get('summary', '') or ''))}</p>"
            + "</div>"
            + "<ul class='kg-tree-list kg-tree-list--systems'>"
            + "".join(system_html_parts)
            + "</ul>"
            + "</div>"
        )

    def get_graph_view(
        self,
        conversation_id: str,
        graph_source_ids: list[str] | str | None,
        focus_file_id: str = "",
        force_rebuild: bool = False,
    ) -> dict[str, Any]:
        conversation_id = str(conversation_id or "draft")
        source_ids = self._normalize_source_ids(graph_source_ids)

        with self._lock:
            sources = self._load_sources(source_ids)
            valid_source_ids = list(sources.keys())
            manifest = {file_id: self._make_signature(source) for file_id, source in sources.items()}
            cached_state = self._load_cached_state(conversation_id)
            cached_manifest = cached_state.get("manifest", {}) or {}
            cached_graph = cached_state.get("graph")
            missing_count = max(0, len(source_ids) - len(valid_source_ids))

            if not valid_source_ids:
                html_content = self._render_empty_html(
                    "No graph sources in this conversation yet.",
                    "Upload related sources in this conversation and then generate the knowledge graph.",
                )
                return {
                    "html": html_content,
                    "graph": None,
                    "status": "empty",
                    "status_message": "No graph available yet.",
                    "focus_file_id": focus_file_id,
                    "graph_source_ids": valid_source_ids,
                    "manifest": manifest,
                    "support_pages": {},
                    "support_chunk_ids": {},
                }

            is_fresh = bool(cached_graph) and cached_manifest == manifest
            if force_rebuild:
                graph = self._build_conversation_graph(conversation_id, sources)
                cached_state = {
                    "conversation_id": conversation_id,
                    "manifest": manifest,
                    "graph": graph,
                }
                self._save_cached_state(conversation_id, cached_state)
                status = "ready"
            elif is_fresh:
                graph = cached_graph
                status = "ready"
            else:
                graph = cached_graph if cached_graph else None
                status = "stale"

            if not graph:
                html_content = self._render_empty_html(
                    "Knowledge graph is not available yet.",
                    "Generate the graph after your sources finish indexing.",
                )
            else:
                html_content = self._render_graph_html(graph, focus_file_id, status)

            if status == "ready":
                status_message = (
                    f"Ready: {len(valid_source_ids)} sources, "
                    f"{len(graph.get('systems', []) if graph else [])} knowledge systems."
                )
            elif status == "stale" and graph:
                status_message = (
                    "Stale: source changes were detected. Refresh the knowledge graph "
                    "to include the latest conversation sources."
                )
            elif status == "stale":
                status_message = (
                    "Stale: knowledge graph has not been generated yet. "
                    "Click Generate / Refresh Knowledge Graph."
                )
            elif status == "empty":
                status_message = "No graph available yet."
            else:
                status_message = "Knowledge graph status unknown."

            if missing_count:
                status_message += f" {missing_count} unavailable source(s) were removed from this graph scope."

            root_support_pages = graph.get("support_pages", {}) if graph else {}
            root_support_chunk_ids = graph.get("support_chunk_ids", {}) if graph else {}

            return {
                "html": html_content,
                "graph": graph,
                "status": status,
                "status_message": status_message,
                "focus_file_id": focus_file_id,
                "graph_source_ids": valid_source_ids,
                "manifest": manifest,
                "support_pages": root_support_pages,
                "support_chunk_ids": root_support_chunk_ids,
            }
