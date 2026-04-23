from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


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
    engine: str = "kotaemon-text-rag"
    scope: str = "document"
    route: str = "hybrid"
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

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["output_dir"] = str(self.output_dir)
        return payload
