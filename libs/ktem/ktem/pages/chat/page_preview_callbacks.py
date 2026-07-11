from __future__ import annotations

import logging
import os
from typing import Any

import gradio as gr
from ktem.auth.service import resolve_request_user_id
from ktem.preview.context import PreviewAccess, preview_access_for_user
from ktem.preview.errors import PreviewAccessError, PreviewErrorCode
from theflow.settings import settings as flowsettings

logger = logging.getLogger(__name__)


def resolve_preview_access(
    app: Any, request: gr.Request, direct_request
) -> PreviewAccess:
    auth_mode = str(getattr(flowsettings, "MARA_AUTH_MODE", "auto")).lower()
    if auth_mode not in {"password", "sso"}:
        return preview_access_for_user(app, "default")
    resolved = (
        None
        if request is direct_request
        else resolve_request_user_id(request, auth_mode=auth_mode)
    )
    if not resolved:
        raise _preview_access_error()
    return PreviewAccess(user_id=str(resolved), owner_required=True)


def normalize_preview_tick(values: list[Any], request: gr.Request, direct_request):
    if is_request_value(request, direct_request):
        return values, request
    return [*values, request][-7:], direct_request


def is_request_value(value: Any, direct_request) -> bool:
    return bool(
        value is direct_request
        or isinstance(value, gr.Request)
        or hasattr(value, "username")
        or hasattr(value, "session_hash")
    )


def poll_office_conversion(
    controller: Any, file_name: str | None, file_path: str
) -> None:
    office_extensions = (".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")
    if not file_path or not str(file_name or "").lower().endswith(office_extensions):
        return
    try:
        if controller._get_office_job_status(file_path) != "done":
            return
        cached_pdf = controller._get_cached_office_pdf_preview(file_path)
        if cached_pdf and os.path.isfile(cached_pdf):
            return
    except Exception as exc:
        logger.debug("Failed to poll Office preview conversion: %s", exc)


def _preview_access_error() -> PreviewAccessError:
    return PreviewAccessError(
        PreviewErrorCode.SOURCE_UNAVAILABLE,
        stage="source_resolution",
        source_path="source-unavailable",
        converter="database",
        details="The requested source is unavailable.",
    )
