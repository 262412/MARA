"""Gradio callback helpers for request-scoped Studio notebook identity."""

from __future__ import annotations

from inspect import Signature, signature
from typing import Any, cast

import gradio as gr

DIRECT_CALL_REQUEST = cast(gr.Request, object())


def resolve_page_user_id(page: Any, request: gr.Request) -> Any:
    """Use the server principal remotely and the runtime user only locally."""
    fallback_user_id = page.docqa._resolve_user_id()
    return page._resolve_persist_user_id(fallback_user_id, request)


def bind_page_callback(callback, page):
    """Bind a page without adding it or the injected Request to component ports."""
    parameters = tuple(signature(callback).parameters.values())[1:]
    interface = Signature(parameters=parameters)

    def bound(*args, **kwargs):
        from ktem.docqa._runtime_notebook import NotebookAccessError

        request = interface.bind(*args, **kwargs).arguments.get("request")
        view = _view_ownership(request)
        try:
            outputs = callback(page, *args, **kwargs)
        except NotebookAccessError as exc:
            raise gr.Error(str(exc)) from exc
        if view != _view_ownership(request):
            return (
                (gr.skip(),) * len(outputs)
                if isinstance(outputs, (list, tuple))
                else gr.skip()
            )
        return outputs

    bound.__signature__ = interface  # type: ignore[attr-defined]
    bound.__annotations__ = {"request": gr.Request}
    bound.__name__ = callback.__name__
    return bound


def _view_ownership(request):
    """Use the existing per-browser view and generation tokens, without new state."""
    session_key = getattr(request, "session_hash", None)
    if not session_key:
        return None
    from .generation_store import (
        get_current_view,
        get_snapshot_by_page,
        get_view_revision,
    )

    revision = get_view_revision(session_key)
    page_key = get_current_view(session_key)
    generation = get_snapshot_by_page(session_key, page_key) if page_key else None
    return revision, page_key, generation.get("request_key") if generation else None


__all__ = ["DIRECT_CALL_REQUEST", "bind_page_callback", "resolve_page_user_id"]
