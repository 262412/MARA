from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse

from .contracts import (
    LatestQueryTaskResponse,
    QueryTask,
    QueryTaskCreateRequest,
    QueryTaskResponse,
)
from .file_routes import IdempotencyKey, validated_identifier
from .query_tasks import TERMINAL_QUERY_STATUSES, QueryTaskManager


def register_query_routes(app: FastAPI, dependencies: list[Any]) -> None:
    _register_query_commands(app, dependencies)
    _register_query_queries(app, dependencies)


def _register_query_commands(app: FastAPI, dependencies: list[Any]) -> None:
    @app.post(
        "/v1/query-tasks",
        response_model=QueryTaskResponse,
        status_code=202,
        dependencies=dependencies,
    )
    def create_query_task(
        request: Request,
        payload: QueryTaskCreateRequest,
        idempotency_key: IdempotencyKey,
    ) -> QueryTaskResponse:
        task = _task_manager(request).create_task(
            payload.conversation_id,
            payload.prompt,
            payload.selected_file_ids,
            idempotency_key=idempotency_key,
        )
        return _task_response(request, task)

    @app.post(
        "/v1/query-tasks/{task_id}/retry",
        response_model=QueryTaskResponse,
        status_code=202,
        dependencies=dependencies,
    )
    def retry_query_task(
        request: Request,
        task_id: str,
        idempotency_key: IdempotencyKey,
    ) -> QueryTaskResponse:
        task = _task_manager(request).retry_task(
            validated_identifier(task_id),
            idempotency_key=idempotency_key,
        )
        return _task_response(request, task)

    @app.post(
        "/v1/query-tasks/{task_id}/cancel",
        response_model=QueryTaskResponse,
        dependencies=dependencies,
    )
    def cancel_query_task(request: Request, task_id: str) -> QueryTaskResponse:
        task = _task_manager(request).cancel_task(validated_identifier(task_id))
        return _task_response(request, task)


def _register_query_queries(app: FastAPI, dependencies: list[Any]) -> None:
    @app.get(
        "/v1/query-tasks/latest",
        response_model=LatestQueryTaskResponse,
        dependencies=dependencies,
    )
    def get_latest_query_task(request: Request) -> LatestQueryTaskResponse:
        task = _task_manager(request).get_latest_task()
        return LatestQueryTaskResponse(
            request_id=_request_id(request),
            task=QueryTask(**task) if task is not None else None,
        )

    @app.get(
        "/v1/query-tasks/{task_id}",
        response_model=QueryTaskResponse,
        dependencies=dependencies,
    )
    def get_query_task(request: Request, task_id: str) -> QueryTaskResponse:
        task = _task_manager(request).get_task(validated_identifier(task_id))
        return _task_response(request, task)

    @app.get(
        "/v1/query-tasks/{task_id}/events",
        dependencies=dependencies,
    )
    async def query_task_events(request: Request, task_id: str) -> StreamingResponse:
        manager = _task_manager(request)
        normalized_task_id = validated_identifier(task_id)
        initial = manager.get_task(normalized_task_id)
        events = _stream_query_events(request, manager, normalized_task_id, initial)
        return StreamingResponse(events, media_type="text/event-stream")


async def _stream_query_events(
    request: Request,
    manager: QueryTaskManager,
    task_id: str,
    initial: dict[str, Any],
) -> AsyncIterator[str]:
    task = initial
    while True:
        response = _task_response(request, task)
        yield (
            f"id: {task['version']}\n"
            "event: query\n"
            f"data: {response.model_dump_json()}\n\n"
        )
        if task["status"] in TERMINAL_QUERY_STATUSES or await request.is_disconnected():
            return
        task = await asyncio.to_thread(
            manager.wait_for_change,
            task_id,
            task["version"],
            timeout=15,
        )


def _task_response(request: Request, task: dict[str, Any]) -> QueryTaskResponse:
    return QueryTaskResponse(request_id=_request_id(request), task=QueryTask(**task))


def _task_manager(request: Request) -> QueryTaskManager:
    return request.app.state.query_task_manager


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", uuid4()))
