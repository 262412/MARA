from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from ._runtime_utils import _serialize_value


@dataclass
class DocQARequest:
    prompt: str
    controller_question: str = ""
    retrieval_query: str = ""
    dataset_family: str = ""
    conversation_id: str = ""
    selected_file_ids: Optional[list[str]] = None
    selected_inputs: Optional[dict[int, Any]] = None
    qa_scope: str = "auto"
    active_file_id: str = ""
    active_file_name: str = ""
    page_number: Optional[int] = None
    selected_text: str = ""
    graph_context: dict[str, Any] = field(default_factory=dict)
    graph_source_ids: Optional[list[str]] = None
    settings: Optional[dict[str, Any]] = None
    state: Optional[dict[str, Any]] = None
    history: Optional[list[tuple[str, str]]] = None
    max_context_length: Optional[int] = None
    reasoning_type: Optional[str] = None
    task_type: Optional[str] = None
    agent_mode: Optional[str] = None
    artifact_type: Optional[str] = None
    note_ids: Optional[list[str]] = None
    controller_mode: Optional[str] = None
    route_policy: Optional[str] = None
    planner_backend: Optional[str] = None
    planner_model: Optional[str] = None
    allowed_routes: Optional[list[str]] = None
    verification_mode: Optional[str] = None
    verification_domain: Optional[str] = None
    graph_mode: Optional[str] = None
    visual_retriever_backend: Optional[str] = None
    visual_generator_backend: Optional[str] = None
    page_image_records: Optional[list[dict[str, Any]]] = None
    element_index_records: Optional[list[dict[str, Any]]] = None
    llm: Optional[str] = None
    use_mindmap: bool | str | None = None
    use_citation: Optional[str] = None
    language: Optional[str] = None
    command_state: Optional[str] = None
    route_timeout_seconds: Optional[float] = None
    route_deadline_monotonic: Optional[float] = None
    user_id: Any = None
    origin: str = "cli"


@dataclass
class DocQAResponse:
    conversation_id: str
    answer: str
    references_html: str
    references_text: str
    mindmap_html: str
    plot: Any
    messages: list[tuple[str, str]]
    retrieval_messages: list[str]
    plot_history: list[Any]
    state: dict[str, Any]
    selected_file_ids: list[str]
    selected_mapping: dict[str, Any]
    graph_source_ids: list[str]
    active_file_id: str
    active_file_name: str
    qa_scope: str
    page_number: Optional[int]
    selected_text: str
    graph_context: dict[str, Any]
    reasoning_id: str
    settings: dict[str, Any]
    stream_events: list[dict[str, Any]]
    graph_cache: Optional[dict[str, Any]] = None
    agent_trace: list[dict[str, Any]] = field(default_factory=list)
    evidence_metadata: dict[str, Any] = field(default_factory=dict)
    controller_decision: dict[str, Any] = field(default_factory=dict)
    route_decision: dict[str, Any] = field(default_factory=dict)
    retrieve_decision: dict[str, Any] = field(default_factory=dict)
    verify_decision: dict[str, Any] = field(default_factory=dict)
    guardrail_decision: dict[str, Any] = field(default_factory=dict)
    controller_trace: list[dict[str, Any]] = field(default_factory=list)
    evidence_bundle: dict[str, Any] = field(default_factory=dict)
    workflow_plan: dict[str, Any] = field(default_factory=dict)
    backend_metadata: dict[str, Any] = field(default_factory=dict)
    artifact: Any = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DocQATurnUpdate:
    event: dict[str, Any] = field(default_factory=dict)
    answer: str = ""
    references_html: str = ""
    mindmap_html: str = ""
    plot: Any = None
    state: dict[str, Any] = field(default_factory=dict)
    stream_events: list[dict[str, Any]] = field(default_factory=list)
    response: Optional[DocQAResponse] = None

    @property
    def is_final(self) -> bool:
        return self.response is not None


@dataclass
class DocQASession:
    conversation_id: str
    name: str
    user_id: Any
    is_public: bool
    data_source: dict[str, Any]
    messages: list[tuple[str, str]]
    retrieval_messages: list[str]
    plot_history: list[Any]
    state: dict[str, Any]
    selected_mapping: dict[str, Any]
    graph_source_ids: list[str]
    origin: str
    date_created: Any
    date_updated: Any


@dataclass
class DocQASessionSummary:
    conversation_id: str
    name: str
    message_count: int
    graph_source_count: int
    origin: str
    is_public: bool
    date_created: Any
    date_updated: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "name": self.name,
            "message_count": self.message_count,
            "graph_source_count": self.graph_source_count,
            "origin": self.origin,
            "is_public": self.is_public,
            "date_created": _serialize_value(self.date_created),
            "date_updated": _serialize_value(self.date_updated),
        }


@dataclass
class DocQAFileRecord:
    file_id: str
    name: str
    size: int
    tokens: int
    loader: str
    path: str
    date_created: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "name": self.name,
            "size": self.size,
            "tokens": self.tokens,
            "loader": self.loader,
            "path": self.path,
            "date_created": _serialize_value(self.date_created),
        }


@dataclass
class DocQAIndexResult:
    successes: list[dict[str, Any]]
    failures: list[dict[str, Any]]
    debug_messages: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "successes": self.successes,
            "failures": self.failures,
            "debug_messages": self.debug_messages,
        }


@dataclass
class DocQADoctorResult:
    ok: bool
    app_name: str
    default_user_id: Any
    index_name: str
    index_id: int | None
    llm_default: str
    embedding_default: str
    file_count: int
    session_count: int
    graph_cache_dir: str
    issues: list[str]
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "app_name": self.app_name,
            "default_user_id": self.default_user_id,
            "index_name": self.index_name,
            "index_id": self.index_id,
            "llm_default": self.llm_default,
            "embedding_default": self.embedding_default,
            "file_count": self.file_count,
            "session_count": self.session_count,
            "graph_cache_dir": self.graph_cache_dir,
            "issues": self.issues,
            "warnings": self.warnings,
        }


@dataclass
class _PreparedPipeline:
    pipeline: Any
    reasoning_state: dict[str, Any]
    selected_file_ids: list[str]
    active_file_id: str
    active_file_name: str
    qa_scope: str
    page_number: Optional[int]
    selected_text: str
    graph_context: dict[str, Any]
    settings: dict[str, Any]
    reasoning_id: str
