from __future__ import annotations

import logging
import threading
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request

from .api_errors import SidecarApiError
from .application import DesktopSessionNotFoundError
from .contracts import (
    SessionDeleteResponse,
    SessionDetailResponse,
    SessionRenameRequest,
)
from .file_routes import IdempotencyKey, validated_identifier

LOGGER = logging.getLogger("mara.desktop.sidecar")


def register_session_mutation_routes(
    app: FastAPI,
    dependencies: list[Any],
) -> None:
    app.state.session_rename_results = {}
    app.state.session_rename_lock = threading.Lock()
    app.state.session_delete_results = {}
    app.state.session_delete_lock = threading.Lock()

    @app.patch(
        "/v1/sessions/{conversation_id}",
        response_model=SessionDetailResponse,
        dependencies=dependencies,
    )
    def rename_session(
        request: Request,
        conversation_id: str,
        payload: SessionRenameRequest,
        idempotency_key: IdempotencyKey,
    ) -> SessionDetailResponse:
        normalized_id = validated_identifier(conversation_id)
        with request.app.state.session_rename_lock:
            existing = request.app.state.session_rename_results.get(idempotency_key)
            if existing is None:
                existing = _call_session_service(
                    request,
                    "rename_session",
                    normalized_id,
                    payload.name,
                )
                request.app.state.session_rename_results[idempotency_key] = existing
        return SessionDetailResponse(
            request_id=_request_id(request),
            session=existing,
        )

    @app.delete(
        "/v1/sessions/{conversation_id}",
        response_model=SessionDeleteResponse,
        dependencies=dependencies,
    )
    def delete_session(
        request: Request,
        conversation_id: str,
        idempotency_key: IdempotencyKey,
    ) -> SessionDeleteResponse:
        normalized_id = validated_identifier(conversation_id)
        with request.app.state.session_delete_lock:
            existing = request.app.state.session_delete_results.get(idempotency_key)
            if existing is None:
                existing = str(
                    _call_session_service(
                        request,
                        "delete_session",
                        normalized_id,
                    )
                )
                request.app.state.session_delete_results[idempotency_key] = existing
        return SessionDeleteResponse(
            request_id=_request_id(request),
            deleted_conversation_id=existing,
        )


def _call_session_service(
    request: Request,
    operation: str,
    *arguments: str,
) -> Any:
    try:
        return getattr(request.app.state.application_service, operation)(*arguments)
    except DesktopSessionNotFoundError:
        raise
    except Exception as exc:
        LOGGER.error(
            "Desktop session mutation failed request_id=%s operation=%s",
            _request_id(request),
            operation,
            exc_info=exc,
        )
        raise SidecarApiError(
            503,
            "session_mutation_failed",
            "MARA could not update the session.",
            retryable=True,
        ) from exc


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", uuid4()))
