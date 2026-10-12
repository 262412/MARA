"""Authenticated claiming of generated outputs, without a Gradio cache copy."""

from __future__ import annotations

import os
import re
from pathlib import Path

import gradio as gr
from gradio.data_classes import FileData
from gradio.events import Dependency
from ktem.auth.service import resolve_request_user_id
from ktem.db.models import engine as default_engine
from starlette.concurrency import run_in_threadpool
from starlette.responses import Response, StreamingResponse
from starlette.routing import Route
from theflow.settings import settings

from kotaemon.artifact_transfers import claim_download
from kotaemon.artifact_types import ArtifactNamespaceError

from ._selection_service import FileSelectionError, FileSelectionService
from .download_scope import DownloadScope

class DownloadButton(gr.DownloadButton):
    is_template = True

    def postprocess(self, value):
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return FileData(path=value, url=value, orig_name=value.rsplit("/", 1)[-1])
        return super().postprocess(value)

def download_button(path, index_id, file_id, request):
    path = Path(path)
    url = request.request.url_for(
        "mara_download",
        index_id=str(index_id),
        file_id=str(file_id),
        request_name=path.parent.name,
        filename=path.name,
    )
    return DownloadButton(label="Start download", value=str(url))

def _principal(request):
    mode = str(getattr(settings, "MARA_AUTH_MODE", "auto")).lower()
    if mode in {"auto", "local"}:
        return "default"
    app = request.app
    if app.auth_dependency is not None:
        username = app.auth_dependency(request)
    else:
        token = request.cookies.get(
            f"access-token-{app.cookie_id}"
        ) or request.cookies.get(f"access-token-unsecure-{app.cookie_id}")
        username = app.tokens.get(token)
    if not username:
        raise FileSelectionError("Authentication is required")
    user = resolve_request_user_id(
        gr.Request(request=request, username=username), auth_mode=mode
    )
    if user is None:
        raise FileSelectionError("Authentication is unavailable")
    return user

class _DownloadResponse(StreamingResponse):
    def __init__(self, transfer, request):
        self.transfer = transfer
        start, end, partial = _byte_range(request.headers.get("range"), transfer.size)
        length = max(0, end - start + 1)
        headers = {
            "Content-Length": str(length),
            "Accept-Ranges": "bytes",
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": f'attachment; filename="{transfer.filename}"',
        }
        if partial:
            headers["Content-Range"] = f"bytes {start}-{end}/{transfer.size}"

        async def body():
            if request.method == "HEAD":
                return
            os.lseek(transfer.fd, start, os.SEEK_SET)
            remaining = length
            while remaining:
                chunk = await run_in_threadpool(
                    os.read, transfer.fd, min(1024 * 1024, remaining)
                )
                if not chunk:
                    raise OSError("Download ended before its declared size")
                remaining -= len(chunk)
                yield chunk
        super().__init__(
            body(),
            status_code=206 if partial else 200,
            headers=headers,
            media_type="application/octet-stream",
        )
    async def __call__(self, scope, receive, send):
        try:
            await super().__call__(scope, receive, send)
        finally:
            self.transfer.close()

def _byte_range(value, size):
    if not value:
        return 0, size - 1, False
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value)
    if match is None or not any(match.groups()) or size == 0:
        raise ValueError("Unsatisfiable range")
    left, right = match.groups()
    if left:
        start, end = int(left), min(int(right), size - 1) if right else size - 1
    else:
        start, end = max(0, size - int(right)), size - 1
    if start > end:
        raise ValueError("Unsatisfiable range")
    return start, end, True

def download_app_kwargs(app, *, engine=default_engine):
    def claim(request):
        user = _principal(request)
        params = request.path_params
        index = next(
            (
                index
                for index in app.index_manager.indices
                if str(index.id) == params["index_id"]
            ),
            None,
        )
        if index is None:
            raise FileSelectionError("Download index is unavailable")
        selection = FileSelectionService(
            index=index, engine=engine, sort_key=lambda doc: 0
        )
        scope = DownloadScope(selection, params["file_id"], user)
        expected = f'download-{params["request_name"]}'
        filename = params["filename"]
        if filename not in {expected + ".zip", expected + ".html"}:
            raise FileSelectionError("Download filename is unavailable")
        with scope.current():
            return claim_download(
                settings.KH_ZIP_OUTPUT_DIR,
                params["file_id"],
                params["request_name"],
                Path(filename).suffix,
                scope.context,
            )
    async def serve(request):
        try:
            transfer = await run_in_threadpool(claim, request)
        except FileSelectionError:
            return Response(status_code=404)
        except (ArtifactNamespaceError, OSError):
            return Response(status_code=503 if os.name != "posix" else 404)
        try:
            return _DownloadResponse(transfer, request)
        except ValueError:
            transfer.close()
            return Response(
                status_code=416, headers={"Content-Range": f"bytes */{transfer.size}"}
            )
        except BaseException:
            transfer.close()
            raise
    return {
        "routes": [
            Route(
                "/mara-download/{index_id}/{file_id}/{request_name}/{filename}",
                serve,
                methods=["GET", "HEAD"],
                name="mara_download",
            )
        ]
    }
