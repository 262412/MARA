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


class SessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str
    sessions: list[SessionSummary]


class SidecarError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    details: Any | None
    retryable: bool
    request_id: str
