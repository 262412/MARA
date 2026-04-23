from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


STANDARD_BENCHMARK_ENGINES = (
    "legacy_text_rag",
    "docqa_runtime",
    "direct_paste",
    "oracle_page",
)
LEGACY_ENGINE_ALIASES = {
    "kotaemon-text-rag": "legacy_text_rag",
}
CLI_ENGINE_CHOICES = (*STANDARD_BENCHMARK_ENGINES, *LEGACY_ENGINE_ALIASES)


def normalize_engine_name(engine: str | None) -> str:
    value = str(engine or "legacy_text_rag").strip()
    return LEGACY_ENGINE_ALIASES.get(value, value)


def normalize_scope(scope: str | None) -> str:
    value = str(scope or "document").strip()
    if value == "multi-document":
        return "multi_document"
    return value


@dataclass(slots=True)
class BenchmarkDocument:
    document_id: str
    path: Path
    format_type: str
    modality: str = "text"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["path"] = str(self.path)
        return payload


@dataclass(slots=True)
class BenchmarkExample:
    example_id: str
    document_id: str
    question: str
    answers: list[str]
    document_ids: list[str] = field(default_factory=list)
    scope: str = "document"
    modality: str = "text"
    answer_type: str = "extractive"
    evidence_pages: list[int | str] = field(default_factory=list)
    evidence_sources: list[str] = field(default_factory=list)
    gold_evidence: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ManifestBundle:
    dataset_name: str
    manifest_path: Path
    documents: dict[str, BenchmarkDocument]
    examples: list[BenchmarkExample]
    schema_version: int = 1
    routes: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class BenchmarkConfig:
    suite_name: str
    output_dir: Path
    engine: str = "legacy_text_rag"
    scope: str = "document"
    route: str = "all"
    cost_profile: str | None = None
    reader_mode: str = "default"
    retrieval_mode: str = "hybrid"
    chunk_size: int = 1024
    chunk_overlap: int = 256
    top_k: int = 5
    max_context_length: int = 16000
    embedding_name: str | None = None
    reranker_name: str | None = None
    llm_name: str | None = None
    use_generation: bool = True
    prompt_template: str | None = None

    def __post_init__(self) -> None:
        self.engine = normalize_engine_name(self.engine)
        self.scope = normalize_scope(self.scope)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["output_dir"] = str(self.output_dir)
        return payload
