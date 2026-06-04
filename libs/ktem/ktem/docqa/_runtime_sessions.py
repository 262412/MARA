from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from . import _runtime_notebook as _nb

STATE = {"app": {"regen": False}}


@dataclass
class ConversationHistories:
    retrieval_history: list[str]
    plot_history: list[Any]
    state: dict[str, Any]


def prepare_conversation_histories(
    *,
    retrieval_message: str,
    plot_data: Any,
    retrieval_history: list[str],
    plot_history: list[Any],
    state: dict[str, Any],
) -> ConversationHistories:
    state_to_store = deepcopy(state or STATE)
    retrieval_history_to_store = list(retrieval_history or [])
    plot_history_to_store = list(plot_history or [])

    if not state_to_store.get("app", {}).get("regen", False):
        retrieval_history_to_store.append(retrieval_message)
        plot_history_to_store.append(plot_data)
    else:
        if retrieval_history_to_store:
            retrieval_history_to_store[-1] = retrieval_message
        if plot_history_to_store:
            plot_history_to_store[-1] = plot_data
    state_to_store.setdefault("app", {})["regen"] = False
    return ConversationHistories(
        retrieval_history=retrieval_history_to_store,
        plot_history=plot_history_to_store,
        state=state_to_store,
    )


def build_conversation_data_source(
    *,
    data_source: dict[str, Any],
    selected_mapping: dict[str, Any],
    is_owner: bool,
    messages: list[tuple[str, str]],
    retrieval_history: list[str],
    plot_history: list[Any],
    state: dict[str, Any],
    graph_source_ids: list[str],
    origin: str | None,
) -> dict[str, Any]:
    updated_data_source = {
        "selected": selected_mapping if is_owner else data_source.get("selected", {}),
        "messages": messages,
        "retrieval_messages": retrieval_history,
        "plot_history": plot_history,
        "state": state,
        "graph_source_ids": graph_source_ids,
        "likes": deepcopy(data_source.get("likes", [])),
    }
    if "chat_suggestions" in data_source:
        updated_data_source["chat_suggestions"] = deepcopy(
            data_source.get("chat_suggestions", [])
        )
    if origin or data_source.get("origin"):
        updated_data_source["origin"] = origin or data_source.get("origin")
    return _nb.preserve_state(updated_data_source, data_source)
