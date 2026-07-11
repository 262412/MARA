from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ktem.db.engine import engine
from ktem.preview.context import preview_access_for_user
from ktem.preview.service import PreviewService
from sqlalchemy import select
from sqlmodel import Session
from theflow.settings import settings as flowsettings

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
    def __init__(self, app, index):
        self._app = app
        self._index = index
        self._preview = PreviewService(app, engine=engine)

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

    def _build_nodes_and_edges(
        self, source_ids: list[str], *, user_id: Any = None
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        sources = self._load_sources(source_ids, user_id=user_id)
        if not sources:
            return {"nodes": [], "edges": [], "clusters": {}}, {}

        keyword_files: defaultdict[str, set[str]] = defaultdict(set)
        file_keywords: dict[str, list[str]] = {}
        evidence_by_keyword: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for file_id, source in sources.items():
            docs = self._load_file_docs(file_id)
            text_chunks: list[str] = []
            for doc in docs:
                content = str(
                    getattr(doc, "text", "") or getattr(doc, "content", "") or ""
                )
                if content:
                    text_chunks.append(content)
            combined_text = "\n".join(text_chunks)
            keywords = self._extract_keywords(combined_text, limit=8)
            file_keywords[file_id] = keywords
            for keyword in keywords:
                normalized = self._normalize_term(keyword)
                if not normalized:
                    continue
                keyword_files[normalized].add(file_id)
                display = keyword
                for sentence in self._split_sentences(combined_text):
                    sentence_norm = sentence.lower()
                    if keyword.lower() in sentence_norm:
                        evidence_by_keyword[normalized].append(
                            {
                                "file_id": file_id,
                                "file_name": source.get("name", file_id),
                                "sentence": self._trim_sentence(sentence),
                                "keyword": display,
                            }
                        )
                        if len(evidence_by_keyword[normalized]) >= 5:
                            break

        file_nodes: list[dict[str, Any]] = [
            {
                "id": file_id,
                "type": "file",
                "label": source.get("name", file_id),
                "metadata": source,
            }
            for file_id, source in sources.items()
        ]

        keyword_nodes: list[dict[str, Any]] = []
        for keyword, file_ids in keyword_files.items():
            keyword_nodes.append(
                {
                    "id": f"kw:{keyword}",
                    "type": "keyword",
                    "label": keyword,
                    "metadata": {
                        "file_ids": sorted(file_ids),
                        "evidence": evidence_by_keyword.get(keyword, [])[:5],
                    },
                }
            )

        edges: list[dict[str, Any]] = []
        for file_id, keywords in file_keywords.items():
            for keyword in keywords:
                normalized = self._normalize_term(keyword)
                if not normalized:
                    continue
                edges.append(
                    {
                        "source": file_id,
                        "target": f"kw:{normalized}",
                        "type": "mentions",
                    }
                )

        uf = _UnionFind([node["id"] for node in keyword_nodes])
        keyword_ids = list(keyword_files.keys())
        for index, left in enumerate(keyword_ids):
            left_files = keyword_files[left]
            for right in keyword_ids[index + 1 :]:
                right_files = keyword_files[right]
                if left_files.intersection(right_files):
                    uf.union(f"kw:{left}", f"kw:{right}")

        clusters: defaultdict[str, list[str]] = defaultdict(list)
        for keyword in keyword_ids:
            node_id = f"kw:{keyword}"
            clusters[uf.find(node_id)].append(node_id)

        graph = {
            "nodes": file_nodes + keyword_nodes,
            "edges": edges,
            "clusters": dict(clusters),
        }
        manifest = {
            file_id: self._make_signature(source) for file_id, source in sources.items()
        }
        return graph, manifest

    def build_graph(
        self,
        conversation_id: str,
        source_ids: list[str] | str | None,
        *,
        user_id: Any = None,
    ) -> dict[str, Any]:
        source_ids = self._normalize_source_ids(source_ids)
        cached_state = self._load_cached_state(conversation_id)
        graph, manifest = self._build_nodes_and_edges(source_ids, user_id=user_id)
        cached_state["conversation_id"] = conversation_id
        cached_state["manifest"] = manifest
        cached_state["graph"] = graph
        self._save_cached_state(conversation_id, cached_state)
        return cached_state
