from __future__ import annotations

import asyncio
import re
import threading
from collections.abc import AsyncIterator
from typing import Annotated, Any
from uuid import uuid4

from fastapi import FastAPI, Header, Request
from fastapi.responses import StreamingResponse

from .api_errors import SidecarApiError
from .application import DesktopFileNotFoundError, DesktopMutationError
from .contracts import (
    FileBatchDeleteRequest,
    FileDeleteResponse,
    IndexTask,
    IndexTaskCreateRequest,
    IndexTaskResponse,
    LatestIndexTaskResponse,
)
from .index_tasks import TERMINAL_STATUSES, IndexTaskManager

IdempotencyKey = Annotated[
    str,
    Header(
        alias="Idempotency-Key",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9._-]+$",
    ),
]


def register_gate3_routes(app: FastAPI, dependencies: list[Any]) -> None:
    app.state.file_delete_results = {}
    app.state.file_delete_lock = threading.Lock()
    _register_index_task_commands(app, dependencies)
    _register_index_task_queries(app, dependencies)
    _register_file_delete(app, dependencies)


def _register_index_task_commands(app: FastAPI, dependencies: list[Any]) -> None:
    @app.post(
        "/v1/index-tasks",
        response_model=IndexTaskResponse,
        status_code=202,
        dependencies=dependencies,
    )
    def create_index_task(
        request: Request,
        payload: IndexTaskCreateRequest,
        idempotency_key: IdempotencyKey,
    ) -> IndexTaskResponse:
        task = _task_manager(request).create_task(
            payload.paths,
            reindex=payload.reindex,
            idempotency_key=idempotency_key,
        )
        return _task_response(request, task)

    @app.post(
        "/v1/index-tasks/{task_id}/retry",
        response_model=IndexTaskResponse,
        status_code=202,
        dependencies=dependencies,
    )
    def retry_index_task(
        request: Request,
        task_id: str,
        idempotency_key: IdempotencyKey,
    ) -> IndexTaskResponse:
        task = _task_manager(request).retry_task(
            validated_identifier(task_id),
            idempotency_key=idempotency_key,
        )
        return _task_response(request, task)

    @app.post(
        "/v1/index-tasks/{task_id}/cancel",
        response_model=IndexTaskResponse,
        dependencies=dependencies,
    )
    def cancel_index_task(request: Request, task_id: str) -> IndexTaskResponse:
        task = _task_manager(request).cancel_task(validated_identifier(task_id))
        return _task_response(request, task)


def _register_index_task_queries(app: FastAPI, dependencies: list[Any]) -> None:
    @app.get(
        "/v1/index-tasks/latest",
        response_model=LatestIndexTaskResponse,
        dependencies=dependencies,
    )
    def get_latest_index_task(request: Request) -> LatestIndexTaskResponse:
        task = _task_manager(request).get_latest_task()
        return LatestIndexTaskResponse(
            request_id=_request_id(request),
            task=IndexTask(**task) if task is not None else None,
        )

    @app.get(
        "/v1/index-tasks/{task_id}",
        response_model=IndexTaskResponse,
        dependencies=dependencies,
    )
    def get_index_task(request: Request, task_id: str) -> IndexTaskResponse:
        task = _task_manager(request).get_task(validated_identifier(task_id))
        return _task_response(request, task)

    @app.get(
        "/v1/index-tasks/{task_id}/events",
        dependencies=dependencies,
    )
    async def index_task_events(request: Request, task_id: str) -> StreamingResponse:
        manager = _task_manager(request)
        normalized_task_id = validated_identifier(task_id)
        initial = manager.get_task(normalized_task_id)
        events = _stream_task_events(request, manager, normalized_task_id, initial)
        return StreamingResponse(events, media_type="text/event-stream")


def _register_file_delete(app: FastAPI, dependencies: list[Any]) -> None:
    @app.delete(
        "/v1/files/{file_id}",
        response_model=FileDeleteResponse,
        dependencies=dependencies,
    )
    def delete_file(
        request: Request,
        file_id: str,
        idempotency_key: IdempotencyKey,
    ) -> FileDeleteResponse:
        return _delete_files(
            request,
            [validated_identifier(file_id)],
            idempotency_key,
        )

    @app.post(
        "/v1/file-deletions",
        response_model=FileDeleteResponse,
        dependencies=dependencies,
    )
    def delete_files(
        request: Request,
        payload: FileBatchDeleteRequest,
        idempotency_key: IdempotencyKey,
    ) -> FileDeleteResponse:
        return _delete_files(request, payload.file_ids, idempotency_key)


def _delete_files(
    request: Request,
    file_ids: list[str],
    idempotency_key: str,
) -> FileDeleteResponse:
    with request.app.state.file_delete_lock:
        existing = request.app.state.file_delete_results.get(idempotency_key)
        if existing is not None:
            return _delete_response(request, existing)
        try:
            records = request.app.state.application_service.delete_files(file_ids)
        except DesktopFileNotFoundError as exc:
            raise SidecarApiError(
                404,
                "file_not_found",
                "One or more indexed files no longer exist.",
            ) from exc
        except DesktopMutationError as exc:
            raise SidecarApiError(
                503,
                "file_delete_failed",
                "MARA could not delete the indexed files.",
                retryable=True,
            ) from exc
        deleted_ids = [str(record["file_id"]) for record in records]
        request.app.state.file_delete_results[idempotency_key] = deleted_ids
        return _delete_response(request, deleted_ids)


async def _stream_task_events(
    request: Request,
    manager: IndexTaskManager,
    task_id: str,
    initial: dict[str, Any],
) -> AsyncIterator[str]:
    task = initial
    while True:
        response = _task_response(request, task)
        yield (
            f"id: {task['version']}\n"
            "event: task\n"
            f"data: {response.model_dump_json()}\n\n"
        )
        if task["status"] in TERMINAL_STATUSES or await request.is_disconnected():
            return
        task = await asyncio.to_thread(
            manager.wait_for_change,
            task_id,
            task["version"],
            timeout=15,
        )


def _task_response(request: Request, task: dict[str, Any]) -> IndexTaskResponse:
    return IndexTaskResponse(request_id=_request_id(request), task=IndexTask(**task))


def _delete_response(request: Request, file_ids: list[str]) -> FileDeleteResponse:
    return FileDeleteResponse(
        request_id=_request_id(request),
        deleted_file_ids=file_ids,
    )


def _task_manager(request: Request) -> IndexTaskManager:
    return request.app.state.index_task_manager


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", uuid4()))


def validated_identifier(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,128}", value):
        raise SidecarApiError(
            422,
            "invalid_request",
            "The Sidecar identifier is invalid.",
        )
    return value
