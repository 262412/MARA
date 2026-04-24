from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from kotaemon.indices.elements import document_to_element


@dataclass
class RetrievedElementTrace:
    """Trace record for one retrieved document element."""

    doc_id: str | None
    rank: int
    score: float | None = None
    source_id: str | None = None
    file_name: str | None = None
    page_number: int | None = None
    page_label: str | None = None
    element_id: str | None = None
    element_type: str | None = None
    bbox: tuple[float, ...] | None = None
    query_modality: str | None = None
    retrieval_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    retrieval_metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_document(
        cls,
        document: Any,
        *,
        rank: int,
        query_modality: str | None = None,
        retrieval_path: Any = None,
    ) -> "RetrievedElementTrace":
        metadata = dict(getattr(document, "metadata", None) or {})
        retrieval_metadata = dict(getattr(document, "retrieval_metadata", None) or {})
        element = document_to_element(_document_with_element_type_alias(document))

        element_type = (
            _string_or_none(_metadata_first(metadata, "element_type", "type"))
            or element.element_type
        )
        modality = (
            _string_or_none(
                _metadata_first(retrieval_metadata, "query_modality", "modality")
            )
            or query_modality
        )
        path = _normalize_path(
            _metadata_first(retrieval_metadata, "retrieval_path", "path")
            or retrieval_path
        )

        return cls(
            doc_id=_doc_id(document),
            rank=rank,
            score=_score(document),
            source_id=element.source_id,
            file_name=element.file_name,
            page_number=element.page_number,
            page_label=element.page_label,
            element_id=element.element_id,
            element_type=element_type,
            bbox=element.bbox,
            query_modality=modality,
            retrieval_path=path,
            metadata=metadata,
            retrieval_metadata=retrieval_metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "rank": self.rank,
            "score": self.score,
            "source_id": self.source_id,
            "file_name": self.file_name,
            "page_number": self.page_number,
            "page_label": self.page_label,
            "element_id": self.element_id,
            "element_type": self.element_type,
            "bbox": list(self.bbox) if self.bbox is not None else None,
            "query_modality": self.query_modality,
            "retrieval_path": list(self.retrieval_path),
            "metadata": _safe_value(self.metadata),
            "retrieval_metadata": _safe_value(self.retrieval_metadata),
        }


@dataclass
class RetrievalCostStats:
    """Latency, token, and cost counters for retrieval/runtime reporting."""

    retrieval_latency_ms: float = 0.0
    rerank_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    embedding_tokens: int = 0
    total_cost: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_latency_ms(self) -> float:
        return self.retrieval_latency_ms + self.rerank_latency_ms + self.llm_latency_ms

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens + self.embedding_tokens

    def add(self, other: "RetrievalCostStats") -> "RetrievalCostStats":
        self.retrieval_latency_ms += other.retrieval_latency_ms
        self.rerank_latency_ms += other.rerank_latency_ms
        self.llm_latency_ms += other.llm_latency_ms
        self.prompt_tokens += other.prompt_tokens
        self.completion_tokens += other.completion_tokens
        self.embedding_tokens += other.embedding_tokens
        self.total_cost += other.total_cost
        for key, value in other.metadata.items():
            self.metadata.setdefault(key, value)
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "retrieval_latency_ms": float(self.retrieval_latency_ms),
            "rerank_latency_ms": float(self.rerank_latency_ms),
            "llm_latency_ms": float(self.llm_latency_ms),
            "total_latency_ms": float(self.total_latency_ms),
            "prompt_tokens": int(self.prompt_tokens),
            "completion_tokens": int(self.completion_tokens),
            "embedding_tokens": int(self.embedding_tokens),
            "total_tokens": int(self.total_tokens),
            "total_cost": float(self.total_cost),
            "metadata": _safe_value(self.metadata),
        }


@dataclass
class RetrievalTrace:
    """Trace bundle for a retrieval run."""

    query: str | None = None
    elements: list[RetrievedElementTrace] = field(default_factory=list)
    cost: RetrievalCostStats = field(default_factory=RetrievalCostStats)
    query_modality: str | None = None
    retrieval_path: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_retrieved_docs(
        cls,
        documents: list[Any],
        *,
        query: str | None = None,
        query_modality: str | None = None,
        retrieval_path: Any = None,
        cost: RetrievalCostStats | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> "RetrievalTrace":
        path = _normalize_path(retrieval_path)
        elements = [
            RetrievedElementTrace.from_document(
                document,
                rank=index + 1,
                query_modality=query_modality,
                retrieval_path=path,
            )
            for index, document in enumerate(documents)
        ]
        return cls(
            query=query,
            elements=elements,
            cost=cost or RetrievalCostStats(),
            query_modality=query_modality,
            retrieval_path=path,
            metadata=dict(metadata or {}),
        )

    @property
    def multi_document_summary(self) -> dict[str, Any]:
        return _build_multi_document_summary(self.elements)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "query_modality": self.query_modality,
            "retrieval_path": list(self.retrieval_path),
            "elements": [element.to_dict() for element in self.elements],
            "multi_document_summary": self.multi_document_summary,
            "cost": self.cost.to_dict(),
            "metadata": _safe_value(self.metadata),
        }


def _build_multi_document_summary(
    elements: list[RetrievedElementTrace],
) -> dict[str, Any]:
    source_groups: dict[str, dict[str, Any]] = {}
    file_groups: dict[str, dict[str, Any]] = {}

    for element in elements:
        source_key = element.source_id or element.file_name or "<unknown>"
        source_group = source_groups.setdefault(
            source_key,
            {
                "source_id": element.source_id,
                "file_name": element.file_name,
                "doc_ids": set(),
                "hit_count": 0,
                "element_count": 0,
                "top_rank": element.rank,
            },
        )
        _update_group(source_group, element)

        file_key = element.file_name or element.source_id or "<unknown>"
        file_group = file_groups.setdefault(
            file_key,
            {
                "file_name": element.file_name,
                "source_ids": set(),
                "doc_ids": set(),
                "hit_count": 0,
                "element_count": 0,
                "top_rank": element.rank,
            },
        )
        _update_group(file_group, element)
        if element.source_id is not None:
            file_group["source_ids"].add(element.source_id)

    sources = {key: _public_source_group(group) for key, group in source_groups.items()}
    files = {key: _public_file_group(group) for key, group in file_groups.items()}
    return {
        "total_sources": len(sources),
        "total_files": len(files),
        "sources": sources,
        "files": files,
    }


def _update_group(
    group: dict[str, Any],
    element: RetrievedElementTrace,
) -> None:
    if element.doc_id is not None:
        group["doc_ids"].add(element.doc_id)
    group["hit_count"] = (
        len(group["doc_ids"]) if group["doc_ids"] else group["hit_count"] + 1
    )
    group["element_count"] += 1
    group["top_rank"] = min(group["top_rank"], element.rank)


def _public_source_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": group["source_id"],
        "file_name": group["file_name"],
        "hit_count": group["hit_count"],
        "element_count": group["element_count"],
        "top_rank": group["top_rank"],
    }


def _public_file_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_name": group["file_name"],
        "source_ids": sorted(group["source_ids"]),
        "hit_count": group["hit_count"],
        "element_count": group["element_count"],
        "top_rank": group["top_rank"],
    }


def _document_with_element_type_alias(document: Any) -> Any:
    metadata = dict(getattr(document, "metadata", None) or {})
    if "type" not in metadata and "element_type" in metadata:
        try:
            copied = document.copy(deep=True)
        except AttributeError:
            return document
        copied.metadata = {**metadata, "type": metadata["element_type"]}
        return copied
    return document


def _doc_id(document: Any) -> str | None:
    return _string_or_none(
        getattr(document, "doc_id", None)
        or getattr(document, "id_", None)
        or getattr(document, "id", None)
    )


def _score(document: Any) -> float | None:
    value = getattr(document, "score", None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_path(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,) if value else ()
    try:
        return tuple(
            item
            for item in (_string_or_none(part) for part in value)
            if item is not None
        )
    except TypeError:
        item = _string_or_none(value)
        return (item,) if item is not None else ()


def _metadata_first(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _safe_value(item) for key, item in value.items()}
    return f"<{type(value).__name__}>"
