from __future__ import annotations

import os
import threading
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QueryTaskState:
    task_id: str
    idempotency_key: str
    conversation_id: str
    prompt: str
    selected_file_ids: list[str]
    turn_id: str = ""
    route_provider: str = ""
    route_model: str = ""
    settings_revision: str = ""
    sidecar_pid: int = field(default_factory=os.getpid)
    route_fingerprint: str = ""
    retry_of_task_id: str | None = None
    status: str = "queued"
    stage: str = "queued"
    answer: str = ""
    answer_saved: bool = True
    citations: list[dict[str, Any]] = field(default_factory=list)
    terminal_semantic_commit: dict[str, Any] = field(default_factory=dict)
    terminal_outcome: str = ""
    terminal_outcome_reason: str = ""
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    version: int = 1
    cancel_requested: bool = False
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    error: dict[str, Any] | None = None


def task_snapshot(task: QueryTaskState) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "retry_of_task_id": task.retry_of_task_id,
        "conversation_id": task.conversation_id,
        "prompt": task.prompt,
        "selected_file_ids": list(task.selected_file_ids),
        "qa_scope": (
            "document" if len(task.selected_file_ids) == 1 else "multi_document"
        ),
        "route_provider": task.route_provider,
        "route_model": task.route_model,
        "settings_revision": task.settings_revision,
        "sidecar_pid": task.sidecar_pid,
        "route_fingerprint": task.route_fingerprint,
        "status": task.status,
        "stage": task.stage,
        "answer": task.answer,
        "answer_saved": task.answer_saved,
        "citations": [dict(item) for item in task.citations],
        "terminal_semantic_commit": deepcopy(task.terminal_semantic_commit),
        "terminal_outcome": task.terminal_outcome,
        "terminal_outcome_reason": task.terminal_outcome_reason,
        "error": dict(task.error) if task.error else None,
        "retryable": bool(
            task.error.get("retryable")
            if task.error is not None
            else task.status == "cancelled"
        ),
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "version": task.version,
    }


def task_to_dict(task: QueryTaskState) -> dict[str, Any]:
    return {
        "task_id": task.task_id,
        "idempotency_key": task.idempotency_key,
        "retry_of_task_id": task.retry_of_task_id,
        "conversation_id": task.conversation_id,
        "prompt": task.prompt,
        "selected_file_ids": list(task.selected_file_ids),
        "turn_id": task.turn_id,
        "route_provider": task.route_provider,
        "route_model": task.route_model,
        "settings_revision": task.settings_revision,
        "sidecar_pid": task.sidecar_pid,
        "route_fingerprint": task.route_fingerprint,
        "status": task.status,
        "stage": task.stage,
        "answer": task.answer,
        "answer_saved": task.answer_saved,
        "citations": [dict(item) for item in task.citations],
        "terminal_semantic_commit": deepcopy(task.terminal_semantic_commit),
        "terminal_outcome": task.terminal_outcome,
        "terminal_outcome_reason": task.terminal_outcome_reason,
        "created_at": task.created_at,
        "updated_at": task.updated_at,
        "version": task.version,
        "cancel_requested": task.cancel_requested,
        "error": task.error,
    }


def task_from_dict(item: dict[str, Any]) -> QueryTaskState:
    return QueryTaskState(
        task_id=str(item["task_id"]),
        idempotency_key=str(item["idempotency_key"]),
        retry_of_task_id=(
            str(item["retry_of_task_id"]) if item.get("retry_of_task_id") else None
        ),
        conversation_id=str(item["conversation_id"]),
        prompt=str(item["prompt"]),
        selected_file_ids=[str(value) for value in item.get("selected_file_ids", [])],
        turn_id=str(item.get("turn_id") or item["task_id"]),
        route_provider=str(item.get("route_provider", "")),
        route_model=str(item.get("route_model", "")),
        settings_revision=str(item.get("settings_revision", "")),
        sidecar_pid=int(item.get("sidecar_pid") or os.getpid()),
        route_fingerprint=str(item.get("route_fingerprint", "")),
        status=str(item.get("status", "failed")),
        stage=str(item.get("stage", "interrupted")),
        answer=str(item.get("answer", "")),
        answer_saved=_saved_answer_state(item),
        citations=[
            dict(value)
            for value in item.get("citations", [])
            if isinstance(value, dict)
        ],
        terminal_semantic_commit=_terminal_commit(item),
        terminal_outcome=str(item.get("terminal_outcome") or ""),
        terminal_outcome_reason=str(item.get("terminal_outcome_reason") or ""),
        created_at=str(item.get("created_at", now())),
        updated_at=str(item.get("updated_at", now())),
        version=int(item.get("version", 1)),
        cancel_requested=bool(item.get("cancel_requested", False)),
        error=item.get("error"),
    )


def _saved_answer_state(item: dict[str, Any]) -> bool:
    value = item.get("answer_saved", True)
    if not isinstance(value, bool):
        raise TypeError("Query task answer_saved must be a boolean.")
    return value


def _terminal_commit(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("terminal_semantic_commit")
    return deepcopy(value) if isinstance(value, dict) else {}
