from __future__ import annotations

from typing import Any


def iter_index_changed_events(page: Any):
    return page._app.get_event(f"onFileIndex{page._index.id}Changed")


def append_index_changed_events(event_chain: Any, page: Any):
    for event in iter_index_changed_events(page):
        event_chain = event_chain.then(**event)
    return event_chain


def append_file_list_refresh(
    event_chain: Any,
    page: Any,
    *,
    inputs: Any,
    outputs: Any,
):
    return event_chain.then(
        fn=page.list_file,
        inputs=inputs,
        outputs=outputs,
        concurrency_limit=20,
    )


def append_chat_input_focus(
    event_chain: Any,
    chat_input_focus_js: str,
    *,
    inputs: Any,
    outputs: Any,
):
    return event_chain.then(
        fn=lambda: True,
        inputs=inputs,
        outputs=outputs,
        js=chat_input_focus_js,
    )
