from __future__ import annotations

import json
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any

from ktem.db.engine import engine
from ktem.llms.manager import llms
from ktem.preview.context import preview_access_for_user
from ktem.preview.service import PreviewService
from sqlalchemy import select
from sqlmodel import Session
from theflow.settings import settings as flowsettings

from kotaemon.base import HumanMessage, SystemMessage

from .knowledge_graph_builder import KnowledgeGraphBuilder
from .knowledge_graph_renderer import KnowledgeGraphRenderer

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


class GlobalKnowledgeGraphService:
    """Conversation-scoped knowledge graph service."""

    EXPECTED_SCHEMA_VERSION = KnowledgeGraphBuilder.SCHEMA_VERSION

    def __init__(self, app, index):
        self._app = app
        self._index = index
        self._lock = threading.Lock()
        self._preview = PreviewService(app, engine=engine)
        self._builder = KnowledgeGraphBuilder(self)
        self._renderer = KnowledgeGraphRenderer(self)

        root_dir = Path(getattr(flowsettings, "KH_APP_DATA_DIR", Path.cwd()))
        self._storage_dir = root_dir / "knowledge_graph" / "conversations"
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _normalize_source_ids(source_ids: list[str] | str | None) -> list[str]:
        if source_ids in (None, ""):
            return []
        if isinstance(source_ids, list):
            values = source_ids
        else:
            value = str(source_ids).strip()
            values = [value] if value else []
        return _limit_unique_strings([str(item or "").strip() for item in values], 256)

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

    @staticmethod
    def _graph_schema_version(graph: dict[str, Any] | None) -> int:
        if not isinstance(graph, dict):
            return 0
        try:
            return int(graph.get("schema_version", 0) or 0)
        except Exception:
            return 0

    def _load_cached_state(self, conversation_id: str) -> dict[str, Any]:
        path = self._get_storage_path(conversation_id)
        if not path.exists():
            return {
                "conversation_id": conversation_id,
                "schema_version": 0,
                "manifest": {},
                "graph": None,
            }
        try:
            with path.open("r", encoding="utf-8") as file_obj:
                data = json.load(file_obj)
        except Exception:
            return {
                "conversation_id": conversation_id,
                "schema_version": 0,
                "manifest": {},
                "graph": None,
            }
        data.setdefault("conversation_id", conversation_id)
        data.setdefault("schema_version", 0)
        data.setdefault("manifest", {})
        data.setdefault("graph", None)
        return data

    def _save_cached_state(self, conversation_id: str, state: dict[str, Any]) -> None:
        path = self._get_storage_path(conversation_id)
        with path.open("w", encoding="utf-8") as file_obj:
            json.dump(state, file_obj, ensure_ascii=False, indent=2)

    def _load_sources(
        self, source_ids: list[str], *, user_id: Any = None
    ) -> dict[str, dict[str, Any]]:
        source_ids = self._normalize_source_ids(source_ids)
        if not source_ids or self._index is None:
            return {}
        sources = self._preview.resolve_sources(
            source_ids,
            access=preview_access_for_user(self._app, user_id),
            strict=True,
        )
        return {
            source.file_id: {
                "id": source.file_id,
                "name": source.name or source.file_id,
                "path": source.stored_path,
                "size": source.size,
                "date_created": str(source.date_created or ""),
            }
            for source in sources
        }

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

    def _make_sentence_candidates(
        self, docs: list[Any]
    ) -> tuple[list[dict[str, Any]], list[str]]:
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

    def _score_candidates(
        self, candidates: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        keyword_counter: Counter[str] = Counter()
        for candidate in candidates:
            keyword_counter.update(candidate.get("keywords", []))

        for candidate in candidates:
            sentence = candidate.get("text", "")
            keywords = candidate.get("keywords", [])
            score = float(sum(keyword_counter[keyword] for keyword in set(keywords)))
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
    def _is_duplicate_point(
        existing_points: list[dict[str, Any]], sentence: str
    ) -> bool:
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
        fenced = re.findall(
            r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", payload, flags=re.IGNORECASE
        )
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
                    label = self._normalize_whitespace(
                        str(point.get("label") or point.get("point") or "")
                    )
                    keywords_raw = point.get("keywords", [])
                    if isinstance(keywords_raw, list):
                        keywords = _limit_unique_strings(
                            [
                                self._normalize_term(str(item or ""))
                                for item in keywords_raw
                            ],
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

    def _generate_outline_with_llm(
        self, file_name: str, candidates: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
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
            evidence_lines.append(
                f"[{index}] page={page_label or 'N/A'} "
                f"chunk={chunk_id or 'N/A'} text={sentence}"
            )

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
            '  "summary": "...",\n'
            '  "knowledge_points": [\n'
            '    {"label": "...", "keywords": ["..."]}\n'
            "  ]\n"
            "}\n"
            "Please produce one summary and 3-6 knowledge points.\n"
            "Evidence:\n" + "\n".join(evidence_lines)
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
            response_text = str(
                getattr(response, "text", "") or getattr(response, "content", "") or ""
            )
        return self._parse_outline_json(response_text)

    def _build_file_graph(self, file_id: str, source: dict[str, Any]) -> dict[str, Any]:
        return self._builder.build_file_graph(file_id, source)

    def _shared_keywords(
        self, left: dict[str, Any], right: dict[str, Any]
    ) -> list[str]:
        return self._builder.shared_keywords(left, right)

    def _group_files_into_systems(
        self, file_graphs: list[dict[str, Any]]
    ) -> list[list[dict[str, Any]]]:
        return self._builder.group_files_into_systems(file_graphs)

    @staticmethod
    def _merge_support_dict(
        target: dict[str, list[str]], source: dict[str, list[str]] | None, limit: int
    ) -> dict[str, list[str]]:
        return KnowledgeGraphBuilder.merge_support_dict(target, source, limit)

    def _build_conversation_graph(
        self, conversation_id: str, sources: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        return self._builder.build_conversation_graph(conversation_id, sources)

    def _make_graph_context(
        self, item: dict[str, Any], focus_file_id: str
    ) -> dict[str, Any]:
        return self._renderer.make_graph_context(item, focus_file_id)

    def _build_suggested_question(self, item: dict[str, Any]) -> str:
        return self._renderer.build_suggested_question(item)

    def _build_prompt(self, item: dict[str, Any], focus_file_id: str) -> str:
        return self._renderer.build_prompt(item, focus_file_id)

    def _payload_attr(self, item: dict[str, Any], focus_file_id: str) -> str:
        return self._renderer.payload_attr(item, focus_file_id)

    def _render_empty_html(self, message: str, hint: str = "") -> str:
        return self._renderer.render_empty_html(message, hint)

    def _render_graph_html(
        self, graph: dict[str, Any], focus_file_id: str, status: str
    ) -> str:
        return self._renderer.render_graph_html(graph, focus_file_id, status)

    def get_graph_view(
        self,
        conversation_id: str,
        graph_source_ids: list[str] | str | None,
        focus_file_id: str = "",
        force_rebuild: bool = False,
        *,
        user_id: Any = None,
    ) -> dict[str, Any]:
        conversation_id = str(conversation_id or "draft")
        source_ids = self._normalize_source_ids(graph_source_ids)

        with self._lock:
            sources = self._load_sources(source_ids, user_id=user_id)
            valid_source_ids = list(sources.keys())
            manifest = {
                file_id: self._make_signature(source)
                for file_id, source in sources.items()
            }
            cached_state = self._load_cached_state(conversation_id)
            cached_manifest = cached_state.get("manifest", {}) or {}
            cached_graph = cached_state.get("graph")
            cached_schema_version = int(
                cached_state.get("schema_version")
                or self._graph_schema_version(cached_graph)
                or 0
            )
            missing_count = max(0, len(source_ids) - len(valid_source_ids))

            if not valid_source_ids:
                html_content = self._render_empty_html(
                    "No graph sources in this conversation yet.",
                    "Upload related sources in this conversation and then "
                    "generate the knowledge graph.",
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

            is_fresh = (
                bool(cached_graph)
                and cached_manifest == manifest
                and cached_schema_version == self.EXPECTED_SCHEMA_VERSION
            )
            graph: dict[str, Any] | None
            schema_outdated = (
                bool(cached_graph)
                and cached_manifest == manifest
                and cached_schema_version != self.EXPECTED_SCHEMA_VERSION
            )
            if force_rebuild:
                graph = self._build_conversation_graph(conversation_id, sources)
                cached_state = {
                    "conversation_id": conversation_id,
                    "schema_version": self.EXPECTED_SCHEMA_VERSION,
                    "manifest": manifest,
                    "graph": graph,
                }
                self._save_cached_state(conversation_id, cached_state)
                status = "ready"
            elif is_fresh:
                graph = cached_graph if isinstance(cached_graph, dict) else None
                status = "ready"
            else:
                graph = cached_graph if isinstance(cached_graph, dict) else None
                status = "stale"

            if not graph:
                html_content = self._render_empty_html(
                    "Knowledge graph is not available yet.",
                    "Generate the graph after your sources finish indexing.",
                )
            else:
                html_content = self._render_graph_html(graph, focus_file_id, status)

            if status == "ready":
                map_count = len(graph.get("maps", []) if graph else []) if graph else 0
                if map_count > 1:
                    status_message = (
                        f"Ready: {len(valid_source_ids)} sources split into "
                        f"{map_count} separate maps because some uploads do not form "
                        "one connected knowledge system."
                    )
                else:
                    status_message = (
                        f"Ready: {len(valid_source_ids)} sources, "
                        f"{len(graph.get('systems', []) if graph else [])} "
                        "knowledge systems."
                    )
            elif status == "stale" and schema_outdated and graph:
                status_message = (
                    "Stale: cached graph uses an older schema. Refresh the "
                    "knowledge graph to rebuild the v2 mind map."
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
                status_message += (
                    f" {missing_count} unavailable source(s) were removed "
                    "from this graph scope."
                )

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
