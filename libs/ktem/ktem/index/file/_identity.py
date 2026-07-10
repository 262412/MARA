from __future__ import annotations

from typing import Any, cast

import gradio as gr
from ktem.auth.service import resolve_request_user_id
from theflow.settings import settings as flowsettings

MISSING_REQUEST = cast(gr.Request, object())


def resolve_file_index_user_id(user_id: Any, request: gr.Request | None) -> Any:
    auth_mode = str(getattr(flowsettings, "MARA_AUTH_MODE", "auto")).lower()
    if auth_mode not in {"password", "sso"}:
        return user_id

    resolved = resolve_request_user_id(request, auth_mode=auth_mode)
    if not resolved:
        raise gr.Error("Authenticated user identity is unavailable.")
    return resolved


__all__ = ["MISSING_REQUEST", "resolve_file_index_user_id"]
