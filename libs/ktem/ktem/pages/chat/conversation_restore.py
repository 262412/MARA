"""Keep authorized conversation restoration separate from page navigation."""

from functools import WRAPPER_ASSIGNMENTS, update_wrapper, wraps
from inspect import signature

import gradio as gr

from .generation_store import get_view_revision, reset_view


def restore_conversation(callback):
    @wraps(callback)
    def restore(conversation_id, user_id, request: gr.Request):
        session_key = getattr(request, "session_hash", None)
        revision = reset_view(session_key)
        outputs = callback(conversation_id, user_id, request)
        if revision != get_view_revision(session_key):
            return (gr.skip(),) * (len(outputs) + 1)
        # These are already-authorized conversation outputs, not a per-page cache.
        return (*outputs, {})

    return restore


def clear_conversation(callback):
    def clear(request: gr.Request):
        reset_view(getattr(request, "session_hash", None))
        return (*callback(), {})

    interface = signature(clear)
    update_wrapper(
        clear,
        callback,
        assigned=tuple(
            field for field in WRAPPER_ASSIGNMENTS if field != "__annotations__"
        ),
    )
    setattr(clear, "__signature__", interface)
    return clear


def restored_answer(render):
    def answer(history):
        return render(history[:-1], *history[-1]) if history else ""

    return answer


def restored_studio_trace(render, resolve_user_id):
    def trace(history, retrieval, conversation_id, user_id, request: gr.Request):
        from .studio_artifact_results import (
            _conversation_artifacts,
            render_studio_artifacts_html,
        )
        from .studio_callback_identity import _view_ownership

        view = _view_ownership(request)
        user_id = resolve_user_id(user_id, request)
        fallback = render(history, retrieval)
        artifacts = _conversation_artifacts(conversation_id, user_id=user_id)
        output = (
            render_studio_artifacts_html({"artifacts": artifacts})
            if artifacts
            else fallback
        )
        return output if view == _view_ownership(request) else gr.skip()

    interface = signature(trace)
    update_wrapper(
        trace,
        render,
        assigned=tuple(
            field for field in WRAPPER_ASSIGNMENTS if field != "__annotations__"
        ),
    )
    setattr(trace, "__signature__", interface)
    return trace


def cache_request_view(callback):
    def cache(
        conversation_id,
        context,
        page_outputs_cache,
        page_number,
        last_question,
        mindmap_html,
        answer_text,
        file_id,
        chat_history,
        request: gr.Request,
    ):
        if (
            not context
            or context["conversation_id"] != conversation_id
            or context["view_revision"] != get_view_revision(request.session_hash)
            or context["page_messages"] is None
        ):
            return gr.skip()
        return callback(
            page_outputs_cache,
            page_number,
            last_question,
            mindmap_html,
            answer_text,
            file_id,
            context["page_messages"],
        )

    interface = signature(cache)
    update_wrapper(
        cache,
        callback,
        assigned=tuple(
            field for field in WRAPPER_ASSIGNMENTS if field != "__annotations__"
        ),
    )
    setattr(cache, "__signature__", interface)
    return cache
