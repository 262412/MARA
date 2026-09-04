from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RuntimeHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str
    protocol: int
    version: str
    capabilities: list[str]
    model_settings_revision: str | None
    request_id: str


class DoctorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool
    app_name: str
    default_user_id: str
    index_name: str
    index_id: int | None
    llm_default: str
    embedding_default: str
    file_count: int
    session_count: int
    graph_cache_dir: str
    issues: list[str]
    warnings: list[str]
    indexing_ready: bool
    indexing_issue_code: str | None
    indexing_message: str
    indexing_action: Literal[
        "none",
        "configure_embedding",
        "repair_installation",
        "check_connection",
        "check_source_permissions",
        "choose_source_again",
        "retry",
        "free_storage",
        "contact_support",
    ]
    indexing_retryable: bool
    query_ready: bool
    query_issue_code: str | None
    query_message: str
    query_action: Literal[
        "none",
        "configure_llm",
        "configure_credentials",
        "check_model_access",
        "repair_installation",
        "check_connection",
        "close_extra_instance",
        "check_data_permissions",
        "free_storage",
        "repair_state",
        "retry",
    ]
    query_retryable: bool
    query_persistence_ready: bool
    query_persistence_issue_code: str | None
    query_persistence_message: str
    query_persistence_action: Literal[
        "none",
        "close_extra_instance",
        "check_data_permissions",
        "free_storage",
        "repair_state",
        "retry",
    ]
    query_persistence_retryable: bool
    query_provider: str
    query_model: str
    embedding_provider: str
    embedding_model: str
    settings_revision: str = Field(max_length=128)
    sidecar_pid: int = Field(gt=0)
    route_fingerprint: str = Field(max_length=64)
    request_id: str


class DoctorResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    doctor: DoctorPayload


class FileRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_id: str
    name: str
    size: int
    tokens: int
    loader: str
    date_created: str | None


class FileListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    files: list[FileRecord]


class ImportCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supported_extensions: list[str] = Field(min_length=1, max_length=64)

    @field_validator("supported_extensions")
    @classmethod
    def validate_extensions(cls, extensions: list[str]) -> list[str]:
        if any(
            not re.fullmatch(r"\.[a-z0-9]{1,16}", extension) for extension in extensions
        ):
            raise ValueError("Import extensions must use a stable suffix format.")
        if len(set(extensions)) != len(extensions):
            raise ValueError("Import extensions must be unique.")
        return extensions


class ImportCapabilitiesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    import_capabilities: ImportCapabilities


class IndexTaskFailure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    code: str
    message: str
    retryable: bool


class IndexTaskError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool


class IndexTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    status: Literal["queued", "running", "partial", "success", "failed", "cancelled"]
    stage: str
    completed_files: int
    total_files: int
    file_names: list[str]
    success_count: int
    failure_count: int
    failures: list[IndexTaskFailure]
    error: IndexTaskError | None
    retryable: bool
    created_at: str
    updated_at: str
    version: int


class IndexTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    task: IndexTask


class LatestIndexTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    task: IndexTask | None


class IndexTaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paths: list[str] = Field(min_length=1, max_length=64)
    reindex: bool = False

    @field_validator("paths")
    @classmethod
    def validate_paths(cls, paths: list[str]) -> list[str]:
        normalized: list[str] = []
        for value in paths:
            if not value or "\x00" in value or len(value) > 32_768:
                raise ValueError("Each import path must be a valid local path.")
            path = Path(value).expanduser()
            if not path.is_absolute():
                raise ValueError("Each import path must be absolute.")
            normalized.append(str(path))
        return normalized


class QueryCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    citation_id: str = Field(min_length=1, max_length=256)
    file_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    file_name: str = Field(min_length=1, max_length=1024)
    page_label: str | None = Field(default=None, max_length=128)
    element_id: str | None = Field(default=None, max_length=128)
    quote: str | None = Field(default=None, max_length=4000)


class QueryPersistenceDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation: Literal["write_temp", "flush", "atomic_replace", "load", "unknown"]
    errno: int | None
    winerror: int | None
    retry_count: int = Field(ge=0, le=100)
    post_failure_probe: Literal[
        "not_run",
        "ready",
        "write_blocked",
        "replace_blocked",
        "flush_blocked",
    ]
    smoke_mode: bool
    fingerprint: str = Field(pattern=r"^qpf-[0-9a-f]{16}$")


class QueryTaskError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    retryable: bool
    provider_request_id: str | None = Field(default=None, max_length=200)
    diagnostic: str | None = Field(default=None, max_length=512)
    persistence: QueryPersistenceDiagnostic | None = None


class QueryTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    retry_of_task_id: str | None
    conversation_id: str
    prompt: str = Field(max_length=20_000)
    selected_file_ids: list[str] = Field(min_length=1, max_length=64)
    qa_scope: Literal["document", "multi_document"]
    route_provider: str = Field(max_length=128)
    route_model: str = Field(max_length=256)
    settings_revision: str = Field(max_length=128)
    sidecar_pid: int = Field(gt=0)
    route_fingerprint: str = Field(max_length=64)
    status: Literal["queued", "running", "success", "failed", "cancelled"]
    stage: str
    answer: str = Field(max_length=1_000_000)
    answer_saved: bool
    citations: list[QueryCitation] = Field(max_length=10_000)
    terminal_semantic_commit: dict[str, Any]
    terminal_outcome: Literal[
        "",
        "answered",
        "safe_abstention",
        "execution_failed",
        "timeout",
        "cancelled",
    ]
    terminal_outcome_reason: str = Field(max_length=1024)
    error: QueryTaskError | None
    retryable: bool
    created_at: str
    updated_at: str
    version: int


class QueryTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    task: QueryTask


class LatestQueryTaskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    task: QueryTask | None


class QueryTaskCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str = Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+$",
    )
    prompt: str = Field(min_length=1, max_length=20_000)
    selected_file_ids: list[str] = Field(min_length=1, max_length=64)

    @field_validator("prompt", mode="before")
    @classmethod
    def strip_prompt(cls, prompt: Any) -> Any:
        return prompt.strip() if isinstance(prompt, str) else prompt

    @field_validator("selected_file_ids")
    @classmethod
    def validate_selected_file_ids(cls, file_ids: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value) for value in file_ids):
            raise ValueError("File identifiers must use the stable identifier format.")
        if len(set(file_ids)) != len(file_ids):
            raise ValueError("File identifiers must be unique.")
        return file_ids


class FileDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    deleted_file_ids: list[str]


class FileBatchDeleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    file_ids: list[str] = Field(min_length=1, max_length=1000)

    @field_validator("file_ids")
    @classmethod
    def validate_file_ids(cls, file_ids: list[str]) -> list[str]:
        if any(not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value) for value in file_ids):
            raise ValueError("File identifiers must use the stable identifier format.")
        if len(set(file_ids)) != len(file_ids):
            raise ValueError("File identifiers must be unique.")
        return file_ids


class SessionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    name: str
    message_count: int
    graph_source_count: int
    origin: str
    is_public: bool
    date_created: str | None
    date_updated: str | None


class SessionMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(max_length=1_000_000)


class SessionDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: str
    name: str
    messages: list[SessionMessage] = Field(max_length=10_000)
    graph_source_ids: list[str] = Field(max_length=10_000)
    origin: str
    is_public: bool
    date_created: str | None
    date_updated: str | None


class SessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    sessions: list[SessionSummary]


class SessionDetailResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    session: SessionDetail


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SessionRenameRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)

    @field_validator("name", mode="before")
    @classmethod
    def strip_name(cls, name: Any) -> Any:
        return name.strip() if isinstance(name, str) else name


class SessionDeleteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    deleted_conversation_id: str


class SidecarError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Any | None
    retryable: bool
    request_id: str
