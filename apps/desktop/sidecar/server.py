from __future__ import annotations

import hmac
import json
import logging
import os
import re
import signal
import socket
import sys
import threading
import time
from pathlib import Path
from typing import Annotated, Any, Protocol, cast
from uuid import uuid4

if os.environ.get("MARA_DESKTOP_DATA_DIR"):
    os.environ.setdefault("THEFLOW_SETTINGS_MODULE", "ktem.default_flowsettings")
    os.environ.setdefault("KOTAEMON_RUNTIME_SETTINGS_BOOTSTRAPPED", "1")

import uvicorn
from fastapi import BackgroundTasks, Depends, FastAPI
from fastapi import Path as FastApiPath
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sidecar.api_errors import SidecarApiError
from sidecar.application import (
    DesktopApplicationService,
    DesktopSessionNotFoundError,
    configure_desktop_data_root,
)
from sidecar.contracts import (
    DoctorPayload,
    DoctorResponse,
    FileListResponse,
    ImportCapabilitiesResponse,
    RuntimeHealth,
    SessionDetailResponse,
    SessionListResponse,
    SidecarError,
)
from sidecar.file_routes import register_gate3_routes
from sidecar.index_task_journal import JsonIndexTaskJournal
from sidecar.index_tasks import IndexTaskManager
from sidecar.maintenance_logging import configure_maintenance_logging
from sidecar.query_routes import register_query_routes
from sidecar.query_tasks import QueryService, QueryTaskManager
from sidecar.session_routes import register_session_mutation_routes
from sidecar.smoke_faults import inject_smoke_fault
from sidecar.task_error_handlers import register_task_exception_handlers
from starlette.exceptions import HTTPException as StarletteHTTPException

PROTOCOL_VERSION = 1
SIDECAR_VERSION = "0.7.0"
REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
CAPABILITIES = [
    "health",
    "lifecycle",
    "doctor",
    "files",
    "sessions",
    "session_detail",
    "session_create",
    "session_mutations",
    "index_tasks",
    "task_events",
    "file_delete",
    "file_batch_delete",
    "import_capabilities",
    "query_stream",
    "query_cancel",
    "query_retry",
]
LOGGER = logging.getLogger("mara.desktop.sidecar")


class ApplicationService(Protocol):
    def get_doctor(self) -> dict[str, Any]:
        ...

    def list_files(self) -> list[dict[str, Any]]:
        ...

    def list_sessions(self) -> list[dict[str, Any]]:
        ...

    def get_session(self, conversation_id: str) -> dict[str, Any]:
        ...

    def create_session(self) -> dict[str, Any]:
        ...

    def rename_session(self, conversation_id: str, name: str) -> dict[str, Any]:
        ...

    def delete_session(self, conversation_id: str) -> str:
        ...

    def get_import_capabilities(self) -> dict[str, list[str]]:
        ...

    def index_files(
        self,
        paths: list[str],
        *,
        reindex: bool = False,
    ) -> dict[str, list[dict[str, Any]]]:
        ...

    def validate_indexing(self, paths: list[str]) -> None:
        ...

    def delete_file(self, file_id: str) -> list[dict[str, str]]:
        ...

    def delete_files(self, file_ids: list[str]) -> list[dict[str, str]]:
        ...


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", uuid4()))


def _error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
    retryable: bool = False,
) -> JSONResponse:
    payload = SidecarError(
        code=code,
        message=message,
        details=details,
        retryable=retryable,
        request_id=_request_id(request),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json"),
        headers={"Cache-Control": "no-store"},
    )


def _require_authentication(request: Request) -> None:
    if request.headers.get("Origin"):
        raise SidecarApiError(
            403,
            "origin_forbidden",
            "Browser-origin requests are not accepted by the Sidecar.",
        )

    authorization = request.headers.get("Authorization", "")
    expected = f"Bearer {request.app.state.token}"
    if not hmac.compare_digest(authorization, expected):
        raise SidecarApiError(
            401,
            "unauthorized",
            "Valid Sidecar credentials are required.",
        )


def _reject_query_parameters(request: Request) -> None:
    if request.query_params:
        raise SidecarApiError(
            422,
            "invalid_request",
            "This endpoint does not accept query parameters.",
            details={"parameters": sorted(request.query_params.keys())},
        )


def _call_service(request: Request, operation: str) -> Any:
    service: ApplicationService = request.app.state.application_service
    try:
        return getattr(service, operation)()
    except Exception as exc:
        LOGGER.error(
            "Desktop application service failed request_id=%s operation=%s",
            _request_id(request),
            operation,
            exc_info=exc,
        )
        raise SidecarApiError(
            503,
            "application_service_unavailable",
            "MARA data is temporarily unavailable.",
            retryable=True,
        ) from exc


def _call_service_with_identifier(
    request: Request,
    operation: str,
    identifier: str,
) -> Any:
    service: ApplicationService = request.app.state.application_service
    try:
        return getattr(service, operation)(identifier)
    except DesktopSessionNotFoundError:
        raise
    except Exception as exc:
        LOGGER.error(
            "Desktop application service failed request_id=%s operation=%s",
            _request_id(request),
            operation,
            exc_info=exc,
        )
        raise SidecarApiError(
            503,
            "application_service_unavailable",
            "MARA data is temporarily unavailable.",
            retryable=True,
        ) from exc


def create_app(
    token: str,
    application_service: ApplicationService | None = None,
    index_task_manager: IndexTaskManager | None = None,
    query_task_manager: QueryTaskManager | None = None,
    *,
    smoke_fault: str | None = None,
) -> FastAPI:
    if not token:
        raise ValueError("Sidecar token is required")

    app = FastAPI(
        title="MARA Desktop Sidecar",
        version=SIDECAR_VERSION,
        docs_url=None,
        redoc_url=None,
        responses={
            401: {"model": SidecarError},
            403: {"model": SidecarError},
            404: {"model": SidecarError},
            409: {"model": SidecarError},
            422: {"model": SidecarError},
            503: {"model": SidecarError},
            507: {"model": SidecarError},
        },
    )
    service = application_service or DesktopApplicationService()
    task_manager = index_task_manager
    if task_manager is None:
        index_service, journal = inject_smoke_fault(
            service,
            JsonIndexTaskJournal(_index_task_journal_path()),
            smoke_fault,
        )
        task_manager = IndexTaskManager(
            index_service,
            journal=journal,
            validator=service.validate_indexing,
        )
    answer_task_manager = query_task_manager or QueryTaskManager(
        cast(QueryService, service),
        journal_path=_query_task_journal_path(),
    )
    app.state.token = token
    app.state.application_service = service
    app.state.index_task_manager = task_manager
    app.state.query_task_manager = answer_task_manager
    app.state.request_shutdown = None
    app.add_event_handler("shutdown", task_manager.close)
    app.add_event_handler("shutdown", answer_task_manager.close)
    _register_request_middleware(app)
    _register_exception_handlers(app)
    register_task_exception_handlers(
        app,
        error_response=_error_response,
        request_id=_request_id,
        logger=LOGGER,
    )
    _register_lifecycle_routes(app)
    _register_data_routes(app)
    return app


def _register_request_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        supplied_request_id = request.headers.get("X-Request-ID", "")
        request.state.request_id = supplied_request_id or str(uuid4())
        if supplied_request_id and not REQUEST_ID_PATTERN.fullmatch(
            supplied_request_id
        ):
            return _error_response(
                request,
                status_code=400,
                code="invalid_request_id",
                message="X-Request-ID contains unsupported characters.",
            )
        response = await call_next(request)
        response.headers["X-Request-ID"] = _request_id(request)
        response.headers["Cache-Control"] = "no-store"
        return response


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(SidecarApiError)
    async def handle_sidecar_error(
        request: Request, error: SidecarApiError
    ) -> JSONResponse:
        return _error_response(
            request,
            status_code=error.status_code,
            code=error.code,
            message=error.message,
            details=error.details,
            retryable=error.retryable,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, error: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "type": item.get("type"),
                "location": [str(part) for part in item.get("loc", ())],
                "message": item.get("msg"),
            }
            for item in error.errors()
        ]
        return _error_response(
            request,
            status_code=422,
            code="invalid_request",
            message="The Sidecar request is invalid.",
            details={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(
        request: Request, error: StarletteHTTPException
    ) -> JSONResponse:
        code = "not_found" if error.status_code == 404 else "http_error"
        message = (
            "The requested Sidecar endpoint does not exist."
            if error.status_code == 404
            else "The Sidecar request could not be completed."
        )
        return _error_response(
            request,
            status_code=error.status_code,
            code=code,
            message=message,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(
        request: Request, error: Exception
    ) -> JSONResponse:
        LOGGER.error(
            "Unhandled Sidecar error request_id=%s path=%s",
            _request_id(request),
            request.url.path,
            exc_info=error,
        )
        return _error_response(
            request,
            status_code=500,
            code="internal_error",
            message="The Sidecar encountered an unexpected error.",
            retryable=True,
        )


def _protected_dependencies() -> list[Any]:
    return [
        Depends(_require_authentication),
        Depends(_reject_query_parameters),
    ]


def _register_lifecycle_routes(app: FastAPI) -> None:
    protected = _protected_dependencies()

    @app.get(
        "/health",
        response_model=RuntimeHealth,
        dependencies=protected,
    )
    def health(request: Request) -> RuntimeHealth:
        return RuntimeHealth(
            state="healthy",
            protocol=PROTOCOL_VERSION,
            version=SIDECAR_VERSION,
            capabilities=CAPABILITIES,
            request_id=_request_id(request),
        )

    @app.get("/capabilities", dependencies=protected)
    def capabilities(request: Request) -> dict[str, Any]:
        return {
            "request_id": _request_id(request),
            "capabilities": CAPABILITIES,
        }

    @app.post("/shutdown", dependencies=protected)
    def shutdown(request: Request, background_tasks: BackgroundTasks) -> dict[str, str]:
        shutdown_callback = request.app.state.request_shutdown
        if shutdown_callback is not None:
            background_tasks.add_task(shutdown_callback)
        return {"request_id": _request_id(request), "state": "stopping"}


def _register_data_routes(app: FastAPI) -> None:
    protected_without_query = _protected_dependencies()

    @app.get(
        "/v1/doctor",
        response_model=DoctorResponse,
        dependencies=protected_without_query,
    )
    def get_doctor(request: Request) -> DoctorResponse:
        request_id = _request_id(request)
        doctor = _call_service(request, "get_doctor")
        return DoctorResponse(
            request_id=request_id,
            doctor=DoctorPayload.model_validate({**doctor, "request_id": request_id}),
        )

    @app.get(
        "/v1/files",
        response_model=FileListResponse,
        dependencies=protected_without_query,
    )
    def list_files(request: Request) -> FileListResponse:
        return FileListResponse(
            request_id=_request_id(request),
            files=_call_service(request, "list_files"),
        )

    @app.get(
        "/v1/sessions",
        response_model=SessionListResponse,
        dependencies=protected_without_query,
    )
    def list_sessions(request: Request) -> SessionListResponse:
        return SessionListResponse(
            request_id=_request_id(request),
            sessions=_call_service(request, "list_sessions"),
        )

    @app.get(
        "/v1/sessions/{conversation_id}",
        response_model=SessionDetailResponse,
        dependencies=protected_without_query,
    )
    def get_session(
        request: Request,
        conversation_id: Annotated[
            str,
            FastApiPath(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._-]+$"),
        ],
    ) -> SessionDetailResponse:
        return SessionDetailResponse(
            request_id=_request_id(request),
            session=_call_service_with_identifier(
                request,
                "get_session",
                conversation_id,
            ),
        )

    @app.get(
        "/v1/import-capabilities",
        response_model=ImportCapabilitiesResponse,
        dependencies=protected_without_query,
    )
    def get_import_capabilities(request: Request) -> ImportCapabilitiesResponse:
        return ImportCapabilitiesResponse(
            request_id=_request_id(request),
            import_capabilities=_call_service(request, "get_import_capabilities"),
        )

    register_gate3_routes(app, protected_without_query)
    register_session_mutation_routes(app, protected_without_query)
    register_query_routes(app, protected_without_query)


def _index_task_journal_path() -> Path | None:
    data_root = os.environ.get("MARA_DESKTOP_DATA_DIR", "")
    return Path(data_root) / "state" / "index-tasks.json" if data_root else None


def _query_task_journal_path() -> Path | None:
    data_root = os.environ.get("MARA_DESKTOP_DATA_DIR", "")
    return Path(data_root) / "state" / "query-tasks.json" if data_root else None


def _watch_parent_pipe(server: uvicorn.Server) -> None:
    try:
        stdin_fd = sys.stdin.fileno()
        while os.read(stdin_fd, 1):
            pass
    except OSError:
        pass
    finally:
        server.should_exit = True


def _create_listener() -> socket.socket:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(("127.0.0.1", 0))
    listener.listen()
    return listener


def main() -> int:
    token = os.environ.get("MARA_DESKTOP_TOKEN", "")
    data_root = os.environ.get("MARA_DESKTOP_DATA_DIR", "")
    if not token:
        print("MARA_DESKTOP_TOKEN is required", file=sys.stderr)
        return 2
    if not data_root:
        print("MARA_DESKTOP_DATA_DIR is required", file=sys.stderr)
        return 2

    desktop_data_root = Path(data_root)
    configure_desktop_data_root(desktop_data_root)
    configure_maintenance_logging(desktop_data_root)
    app = create_app(
        token,
        smoke_fault=os.environ.get("MARA_DESKTOP_SMOKE_FAULT") or None,
    )
    listener = _create_listener()
    host, port = listener.getsockname()
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)
    app.state.request_shutdown = lambda: setattr(server, "should_exit", True)

    def stop_server(_signum: int, _frame: Any) -> None:
        server.should_exit = True

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)
    threading.Thread(target=_watch_parent_pipe, args=(server,), daemon=True).start()
    server_thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [listener]},
        daemon=True,
    )
    server_thread.start()

    deadline = time.monotonic() + 20
    while not server.started and server_thread.is_alive():
        if time.monotonic() >= deadline:
            server.should_exit = True
            server_thread.join(timeout=2)
            print("Sidecar startup timed out", file=sys.stderr)
            return 1
        time.sleep(0.01)

    if not server.started:
        print("Sidecar failed during startup", file=sys.stderr)
        return 1

    ready = {
        "type": "ready",
        "protocol": PROTOCOL_VERSION,
        "port": port,
        "pid": os.getpid(),
    }
    print(json.dumps(ready, separators=(",", ":")), flush=True)
    server_thread.join()
    listener.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
