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

    def bound(*args, **kwargs):
        from ktem.docqa._runtime_notebook import NotebookAccessError

        try:
            return callback(page, *args, **kwargs)
        except NotebookAccessError as exc:
            raise gr.Error(str(exc)) from exc

    parameters = tuple(signature(callback).parameters.values())[1:]
    bound.__signature__ = Signature(parameters=parameters)  # type: ignore[attr-defined]
    bound.__annotations__ = {"request": gr.Request}
    bound.__name__ = callback.__name__
    return bound


__all__ = ["DIRECT_CALL_REQUEST", "bind_page_callback", "resolve_page_user_id"]
