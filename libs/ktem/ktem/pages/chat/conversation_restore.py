"""Keep authorized conversation restoration separate from page navigation."""

from functools import update_wrapper, wraps
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
    update_wrapper(clear, callback)
    setattr(clear, "__signature__", interface)
    return clear


def restored_answer(render):
    def answer(history):
        return render(history[:-1], *history[-1]) if history else ""

    return answer


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
        ):
            return gr.skip()
        return callback(
            page_outputs_cache,
            page_number,
            last_question,
            mindmap_html,
            answer_text,
            file_id,
            chat_history,
        )

    interface = signature(cache)
    update_wrapper(cache, callback)
    setattr(cache, "__signature__", interface)
    return cache
