"""Adapt the completed runtime turn to the Web naming and persistence tail."""

from copy import deepcopy
from dataclasses import dataclass
from functools import wraps
from inspect import signature
from typing import Callable

import gradio as gr


def with_completion_context(callback):
    """Keep the old stream callback intact and capture its actual input scope."""

    @wraps(callback)
    def stream(*args, **kwargs):
        inputs = signature(callback).bind(*args, **kwargs).arguments
        context = {
            "conversation_id": inputs["conversation_id"],
            "selecteds": deepcopy(inputs.get("selecteds", ())),
        }
        for output in callback(*args, **kwargs):
            yield (*output, {**context, "messages": deepcopy(output[13])})

    return stream


@dataclass
class CompletionTail:
    resolve_user: Callable
    load_session: Callable
    suggest_name: Callable
    rename_conversation: Callable
    persist_data_source: Callable
    demo_mode: bool = False

    def _completed(self, conversation_id, user_id, messages, context, request):
        if not context or context["conversation_id"] != conversation_id:
            return None
        if not messages or context["messages"] != messages:
            return None
        user_id = self.resolve_user(user_id, request)
        session = self.load_session(conversation_id, user_id=user_id)
        # The finalizer is the authority for a successful turn. Error placeholders,
        # partial streams and a different/newer turn must never reach Web writes.
        if session is None or session.messages != [tuple(pair) for pair in messages]:
            return None
        return session

    def suggest(self, conversation_id, user_id, messages, context, request: gr.Request):
        if (
            self.demo_mode
            or self._completed(conversation_id, user_id, messages, context, request)
            is not None
        ):
            return self.suggest_name(messages)
        return gr.skip(), False

    def rename(
        self,
        conversation_id,
        new_name,
        is_renamed,
        user_id,
        messages,
        context,
        request: gr.Request,
    ):
        if (
            self.demo_mode
            or self._completed(conversation_id, user_id, messages, context, request)
            is not None
        ):
            return self.rename_conversation(
                conversation_id, new_name, is_renamed, user_id, request
            )
        return gr.skip(), gr.skip(), gr.skip()

    def persist(
        self,
        conversation_id,
        user_id,
        retrieval_msg,
        plot_data,
        retrieval_history,
        plot_history,
        messages,
        state,
        graph_source_ids,
        context,
        request: gr.Request,
        *selecteds,
    ):
        session = self._completed(conversation_id, user_id, messages, context, request)
        if session is None:
            return gr.skip(), gr.skip()
        # Reconcile through the existing Web writer using the finalizer's payload,
        # not UI fragments (mindmap HTML, stale state or a changed file selector).
        return self.persist_data_source(
            conversation_id,
            user_id,
            session.retrieval_messages[-1],
            session.plot_history[-1],
            session.retrieval_messages[:-1],
            session.plot_history[:-1],
            session.messages,
            session.state,
            session.graph_source_ids,
            request,
            *context["selecteds"],
        )
