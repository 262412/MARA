from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .answer_modes import normalize_benchmark_answer_mode

STANDARD_BENCHMARK_ENGINES = (
    "legacy_text_rag",
    "benchmark_direct_answer",
    "docqa_runtime",
    "direct_paste",
    "oracle_page",
)
LEGACY_ENGINE_ALIASES = {
    "kotaemon-text-rag": "legacy_text_rag",
}
CLI_ENGINE_CHOICES = (*STANDARD_BENCHMARK_ENGINES, *LEGACY_ENGINE_ALIASES)
BENCHMARK_PROMPT_POLICIES = ("benchmark_v1", "gold_answer_v1", "raw")
BENCHMARK_PROMPT_PROFILES = (
    "auto",
    "concise_grounded_qa",
    "citation_grounded_qa",
    "guardrail_grounded_qa",
    "visual_grounded_qa",
)


def normalize_engine_name(engine: str | None) -> str:
    value = str(engine or "legacy_text_rag").strip()
    return LEGACY_ENGINE_ALIASES.get(value, value)


def normalize_scope(scope: str | None) -> str:
    value = str(scope or "document").strip()
    if value == "multi-document":
        return "multi_document"
    return value


def normalize_benchmark_prompt_policy(policy: str | None) -> str:
    value = str(policy or "benchmark_v1").strip().lower()
    if value not in BENCHMARK_PROMPT_POLICIES:
        choices = "', '".join(BENCHMARK_PROMPT_POLICIES)
        raise ValueError(f"benchmark_prompt_policy must be one of '{choices}'.")
    return value


def normalize_benchmark_prompt_profile(profile: str | None) -> str:
    value = str(profile or "auto").strip().lower()
    if value not in BENCHMARK_PROMPT_PROFILES:
        choices = "', '".join(BENCHMARK_PROMPT_PROFILES)
        raise ValueError(f"benchmark_prompt_profile must be one of '{choices}'.")
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
    expected_formats: list[str] = field(default_factory=list)
    expected_guardrails: dict[str, Any] = field(default_factory=dict)
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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BenchmarkConfig:
    suite_name: str
    output_dir: Path
    engine: str = "legacy_text_rag"
    scope: str = "document"
    route: str = "all"
    cost_profile: str | None = None
    cache_mode: str = "warm"
    reader_mode: str = "default"
    retrieval_mode: str = "hybrid"
    chunk_size: int = 1024
    chunk_overlap: int = 256
    top_k: int = 5
    max_context_length: int = 16000
    embedding_name: str | None = None
    reranker_name: str | None = None
    llm_name: str | None = None
    docqa_citation_mode: str | None = None
    reasoning_type: str | None = None
    agent_mode: str | None = None
    task_type: str | None = None
    artifact_type: str | None = None
    controller_mode: str | None = None
    route_policy: str | None = None
    planner_backend: str | None = None
    planner_model: str | None = None
    allowed_routes: list[str] | None = None
    verification_mode: str | None = None
    verification_domain: str | None = None
    graph_mode: str | None = None
    visual_retriever_backend: str | None = None
    visual_generator_backend: str | None = None
    generator_backend: str | None = None
    artifact_detail: str = "compact"
    limit: int | None = None
    sample_seed: int | None = None
    shard_index: int | None = None
    num_shards: int | None = None
    use_generation: bool = True
    benchmark_prompt_policy: str = "benchmark_v1"
    benchmark_prompt_profile: str = "auto"
    benchmark_answer_mode: str = "scoring_adapter_v1"
    benchmark_no_think: bool = False
    route_timeout_seconds: float | None = None
    backend_health_json: Path | None = None
    prompt_template: str | None = None
    external_evaluators: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.engine = normalize_engine_name(self.engine)
        self.scope = normalize_scope(self.scope)
        self.cache_mode = normalize_cache_mode(self.cache_mode)
        self.artifact_detail = normalize_artifact_detail(self.artifact_detail)
        self.benchmark_prompt_policy = normalize_benchmark_prompt_policy(
            self.benchmark_prompt_policy
        )
        self.benchmark_prompt_profile = normalize_benchmark_prompt_profile(
            self.benchmark_prompt_profile
        )
        self.benchmark_answer_mode = normalize_benchmark_answer_mode(
            self.benchmark_answer_mode
        )
        self.route_timeout_seconds = normalize_route_timeout_seconds(
            self.route_timeout_seconds
        )
        self.backend_health_json = normalize_optional_path(self.backend_health_json)
        from .sampling import validate_sampling_options

        validate_sampling_options(
            limit=self.limit,
            shard_index=self.shard_index,
            num_shards=self.num_shards,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["output_dir"] = str(self.output_dir)
        if self.backend_health_json is not None:
            payload["backend_health_json"] = str(self.backend_health_json)
        return payload


def normalize_cache_mode(cache_mode: str | None) -> str:
    value = str(cache_mode or "warm").strip().lower()
    aliases = {
        "enabled": "warm",
        "on": "warm",
        "reuse": "warm",
        "disabled": "bypass",
        "disable": "bypass",
        "off": "bypass",
        "none": "bypass",
    }
    value = aliases.get(value, value)
    if value not in {"warm", "cold", "bypass"}:
        raise ValueError("cache_mode must be one of 'warm', 'cold', or 'bypass'.")
    return value


def normalize_artifact_detail(artifact_detail: str | None) -> str:
    value = str(artifact_detail or "compact").strip().lower()
    if value not in {"compact", "full"}:
        raise ValueError("artifact_detail must be one of 'compact' or 'full'.")
    return value


def normalize_route_timeout_seconds(value: float | str | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    seconds = float(value)
    if seconds <= 0:
        return None
    return seconds


def normalize_optional_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    text = str(value).strip()
    return Path(text) if text else None
