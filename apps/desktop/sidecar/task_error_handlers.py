from __future__ import annotations

import logging
from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .application import DesktopFileNotFoundError, DesktopSessionNotFoundError
from .index_task_journal import IndexTaskPersistenceError
from .index_tasks import IndexTaskConflictError, IndexTaskNotFoundError
from .indexing_readiness import DesktopIndexingPreflightError
from .query_task_journal import QueryTaskPersistenceError
from .query_tasks import QueryTaskConflictError, QueryTaskNotFoundError

ErrorResponse = Callable[..., JSONResponse]
RequestId = Callable[[Request], str]
INDEX_TASK_LOGGER = logging.getLogger("mara.desktop.index_tasks")


def register_task_exception_handlers(
    app: FastAPI,
    *,
    error_response: ErrorResponse,
    request_id: RequestId,
    logger: logging.Logger,
) -> None:
    _register_session_error(app, error_response)
    _register_file_error(app, error_response)
    _register_index_task_errors(app, error_response, request_id, logger)
    _register_query_task_errors(app, error_response, request_id, logger)


def _register_session_error(
    app: FastAPI,
    error_response: ErrorResponse,
) -> None:
    @app.exception_handler(DesktopSessionNotFoundError)
    async def handle_session_not_found(
        request: Request, _error: DesktopSessionNotFoundError
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=404,
            code="session_not_found",
            message="The requested session no longer exists.",
        )


def _register_file_error(
    app: FastAPI,
    error_response: ErrorResponse,
) -> None:
    @app.exception_handler(DesktopFileNotFoundError)
    async def handle_file_not_found(
        request: Request, _error: DesktopFileNotFoundError
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=404,
            code="file_not_found",
            message="One or more selected files no longer exist.",
        )


def _register_index_task_errors(
    app: FastAPI,
    error_response: ErrorResponse,
    request_id: RequestId,
    logger: logging.Logger,
) -> None:
    @app.exception_handler(DesktopIndexingPreflightError)
    async def handle_indexing_preflight_error(
        request: Request,
        error: DesktopIndexingPreflightError,
    ) -> JSONResponse:
        logger.error(
            "Index task rejected request_id=%s error_code=%s error_type=%s",
            request_id(request),
            error.code,
            type(error).__name__,
        )
        INDEX_TASK_LOGGER.error(
            "Index task rejected request_id=%s error_code=%s error_type=%s",
            request_id(request),
            error.code,
            type(error).__name__,
        )
        return error_response(
            request,
            status_code=error.status_code,
            code=error.code,
            message=error.message,
            retryable=error.retryable,
        )

    @app.exception_handler(IndexTaskPersistenceError)
    async def handle_task_persistence_error(
        request: Request, error: IndexTaskPersistenceError
    ) -> JSONResponse:
        logger.error(
            "Index task persistence unavailable request_id=%s error_code=%s",
            request_id(request),
            error.code,
        )
        INDEX_TASK_LOGGER.error(
            "Index task persistence unavailable request_id=%s error_code=%s",
            request_id(request),
            error.code,
        )
        return error_response(
            request,
            status_code=503,
            code=error.code,
            message=error.message,
            retryable=error.retryable,
        )

    @app.exception_handler(IndexTaskNotFoundError)
    async def handle_task_not_found(
        request: Request, _error: IndexTaskNotFoundError
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=404,
            code="index_task_not_found",
            message="The index task no longer exists.",
        )

    @app.exception_handler(IndexTaskConflictError)
    async def handle_task_conflict(
        request: Request, _error: IndexTaskConflictError
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=409,
            code="index_task_conflict",
            message="The index task cannot perform that action in its current state.",
        )


def _register_query_task_errors(
    app: FastAPI,
    error_response: ErrorResponse,
    request_id: RequestId,
    logger: logging.Logger,
) -> None:
    @app.exception_handler(QueryTaskPersistenceError)
    async def handle_query_persistence_error(
        request: Request, error: QueryTaskPersistenceError
    ) -> JSONResponse:
        logger.error(
            "Query task persistence unavailable request_id=%s error_code=%s "
            "operation=%s error_type=%s errno=%s winerror=%s retried=%s "
            "retry_count=%s",
            request_id(request),
            error.code,
            error.operation,
            error.error_type,
            error.error_number,
            error.winerror,
            error.retry_count > 0,
            error.retry_count,
        )
        return error_response(
            request,
            status_code=503,
            code=error.code,
            message=error.message,
            retryable=error.retryable,
        )

    @app.exception_handler(QueryTaskNotFoundError)
    async def handle_query_not_found(
        request: Request, _error: QueryTaskNotFoundError
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=404,
            code="query_task_not_found",
            message="The answer task no longer exists.",
        )

    @app.exception_handler(QueryTaskConflictError)
    async def handle_query_conflict(
        request: Request, _error: QueryTaskConflictError
    ) -> JSONResponse:
        return error_response(
            request,
            status_code=409,
            code="query_task_conflict",
            message="The answer task cannot perform that action in its current state.",
        )
