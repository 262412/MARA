from __future__ import annotations

from .chat_gradio_adapters import chat_preview_ports
from .file_browser_updates import (
    bind_file_browser_result,
    bind_file_selection_result,
    chat_file_refresh_event,
)


def _chat_file_list_inputs(page):
    return [
        page.chat_control.conversation_id,
        page._app.user_id,
        page.first_selector_choices,
        page._indices_input[1],
        page._graph_source_ids,
        page.chat_file_filter,
    ]


def _chat_file_list_outputs(page):
    return [
        page.chat_file_rows,
        page.chat_file_list,
        page.chat_selected_file,
        page.workbench_file_summary,
    ]


def _graph_scope_sync_inputs(page):
    return [
        page._graph_source_ids,
        page.first_selector_choices,
        page._app.user_id,
    ]


def _graph_scope_sync_outputs(page):
    return [page._graph_source_ids]


def _persist_graph_scope_inputs(page):
    return [
        page.chat_control.conversation_id,
        page._app.user_id,
        page._graph_source_ids,
    ]


def _sync_scope_then_refresh_file_list(chain, page):
    return chain.then(
        fn=page.persist_conversation_source_scope,
        inputs=_persist_graph_scope_inputs(page),
        outputs=_graph_scope_sync_outputs(page),
        show_progress="hidden",
    ).then(**chat_file_refresh_event(page))


def bind_knowledge_graph_events(page) -> None:
    bind_file_browser_result(page)
    page.chat_file_filter.change(**chat_file_refresh_event(page))

    page._indices_input[1].change(**chat_file_refresh_event(page))

    ports = chat_preview_ports(page)
    bind_file_selection_result(page)
    page._file_browser_selection_applied.change(
        fn=page.page_preview.on_selected_file_change,
        inputs=ports.selected_file.gradio_inputs,
        outputs=ports.selected_file.gradio_outputs,
        show_progress="hidden",
    )

    _sync_scope_then_refresh_file_list(
        page.first_selector_choices.change(
            fn=page.sync_graph_source_ids_with_selector_choices,
            inputs=_graph_scope_sync_inputs(page),
            outputs=_graph_scope_sync_outputs(page),
            show_progress="hidden",
        ),
        page,
    )

    _sync_scope_then_refresh_file_list(
        page.chat_control.conversation_id.change(
            fn=page.load_conversation_graph_state,
            inputs=[page.chat_control.conversation_id, page._app.user_id],
            outputs=_graph_scope_sync_outputs(page),
            show_progress="hidden",
        ).then(
            fn=page.sync_graph_source_ids_with_selector_choices,
            inputs=_graph_scope_sync_inputs(page),
            outputs=_graph_scope_sync_outputs(page),
            show_progress="hidden",
        ),
        page,
    )

    chat_tab = getattr(getattr(page._app, "_tabs", {}), "get", lambda *_: None)(
        "chat-tab"
    )
    if chat_tab is not None:
        _sync_scope_then_refresh_file_list(
            chat_tab.select(
                fn=page.sync_graph_source_ids_with_selector_choices,
                inputs=_graph_scope_sync_inputs(page),
                outputs=_graph_scope_sync_outputs(page),
                show_progress="hidden",
            ),
            page,
        )


def subscribe_public_knowledge_graph_events(page) -> None:
    event_name = f"onFileIndex{page.file_index.id}Changed"
    definitions = [
        {
            "fn": page.sync_graph_source_ids_with_selector_choices,
            "inputs": _graph_scope_sync_inputs(page),
            "outputs": _graph_scope_sync_outputs(page),
            "show_progress": "hidden",
        },
        {
            "fn": page.persist_conversation_source_scope,
            "inputs": _persist_graph_scope_inputs(page),
            "outputs": _graph_scope_sync_outputs(page),
            "show_progress": "hidden",
        },
        chat_file_refresh_event(page),
    ]
    for definition in definitions:
        page._app.subscribe_event(name=event_name, definition=definition)
