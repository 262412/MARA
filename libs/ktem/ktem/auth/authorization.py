"""Request-scoped authorization for Web callbacks."""

from __future__ import annotations

from typing import Any, cast

import gradio as gr
from ktem.auth.service import resolve_request_user_id
from ktem.db.models import User, engine
from sqlmodel import Session, select
from theflow.settings import settings as flowsettings

CALLBACK_REQUEST = cast(gr.Request, object())


class CallbackAuthorizationError(RuntimeError):
    """A callback principal or required role is unavailable."""

    def __init__(self) -> None:
        super().__init__("This operation is unavailable.")


def resolve_callback_user_id(
    state_user_id: Any,
    request: gr.Request = CALLBACK_REQUEST,
) -> str:
    """Resolve managed identity from Request and local identity from State."""
    auth_mode = str(getattr(flowsettings, "MARA_AUTH_MODE", "auto")).lower()
    if auth_mode in {"password", "sso"}:
        resolved = (
            None
            if request is CALLBACK_REQUEST
            else resolve_request_user_id(request, auth_mode=auth_mode)
        )
    else:
        resolved = str(state_user_id or "").strip()
    if not resolved:
        raise CallbackAuthorizationError()
    return str(resolved)


def require_admin(
    state_user_id: Any,
    request: gr.Request = CALLBACK_REQUEST,
    *,
    db_engine: Any = engine,
) -> str:
    """Resolve the callback principal and re-check its current admin role."""
    user_id = resolve_callback_user_id(state_user_id, request)
    with Session(db_engine) as session:
        user = session.exec(
            select(User).where(User.id == user_id, User.admin.is_(True))
        ).first()
    if user is None:
        raise CallbackAuthorizationError()
    return user_id


__all__ = [
    "CALLBACK_REQUEST",
    "CallbackAuthorizationError",
    "require_admin",
    "resolve_callback_user_id",
]
