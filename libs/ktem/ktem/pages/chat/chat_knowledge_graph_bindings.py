from __future__ import annotations


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
    ]


def _graph_refresh_inputs(page):
    return [
        page.chat_control.conversation_id,
        page._graph_source_ids,
        page._active_file_id,
        page._indices_input[1],
    ]


def _graph_refresh_outputs(page):
    return [
        page.plot_panel,
        page.state_plot_panel,
        page.knowledge_graph_status,
        page._graph_source_ids,
    ]


def _graph_loading_outputs(page):
    return [
        page.plot_panel,
        page.knowledge_graph_status,
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


def _load_then_refresh_graph(chain, page):
    return chain.then(
        fn=page.show_knowledge_graph_loading,
        inputs=[page.chat_control.conversation_id],
        outputs=_graph_loading_outputs(page),
        show_progress="hidden",
    ).then(
        fn=page.refresh_knowledge_graph,
        inputs=_graph_refresh_inputs(page),
        outputs=_graph_refresh_outputs(page),
        show_progress="hidden",
    )


def _sync_scope_then_refresh_graph(chain, page):
    return (
        chain.then(
            fn=page.persist_conversation_source_scope,
            inputs=_persist_graph_scope_inputs(page),
            outputs=_graph_scope_sync_outputs(page),
            show_progress="hidden",
        )
        .then(
            fn=page.refresh_chat_file_list,
            inputs=_chat_file_list_inputs(page),
            outputs=_chat_file_list_outputs(page),
            show_progress="hidden",
        )
        .then(
            fn=page.show_knowledge_graph_loading,
            inputs=[page.chat_control.conversation_id],
            outputs=_graph_loading_outputs(page),
            show_progress="hidden",
        )
        .then(
            fn=page.refresh_knowledge_graph,
            inputs=_graph_refresh_inputs(page),
            outputs=_graph_refresh_outputs(page),
            show_progress="hidden",
        )
    )


def bind_knowledge_graph_events(page) -> None:
    page.chat_file_filter.change(
        fn=page.refresh_chat_file_list,
        inputs=_chat_file_list_inputs(page),
        outputs=_chat_file_list_outputs(page),
        show_progress="hidden",
    )

    _load_then_refresh_graph(
        page._indices_input[1].change(
            fn=page.refresh_chat_file_list,
            inputs=_chat_file_list_inputs(page),
            outputs=_chat_file_list_outputs(page),
            show_progress="hidden",
        ),
        page,
    )

    page._chat_file_click.change(
        fn=page.select_chat_file,
        inputs=[page._chat_file_click],
        outputs=[
            page._indices_input[0],
            page._indices_input[1],
            page._chat_file_click,
        ],
        show_progress="hidden",
    )

    _sync_scope_then_refresh_graph(
        page.first_selector_choices.change(
            fn=page.sync_graph_source_ids_with_selector_choices,
            inputs=_graph_scope_sync_inputs(page),
            outputs=_graph_scope_sync_outputs(page),
            show_progress="hidden",
        ),
        page,
    )

    _sync_scope_then_refresh_graph(
        page.chat_control.conversation_id.change(
            fn=page.load_conversation_graph_state,
            inputs=[page.chat_control.conversation_id],
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
        _sync_scope_then_refresh_graph(
            chat_tab.select(
                fn=page.sync_graph_source_ids_with_selector_choices,
                inputs=_graph_scope_sync_inputs(page),
                outputs=_graph_scope_sync_outputs(page),
                show_progress="hidden",
            ),
            page,
        )

    page.knowledge_graph_refresh.click(
        fn=lambda conversation_id: page.show_knowledge_graph_loading(
            conversation_id, mode="generate"
        ),
        inputs=[page.chat_control.conversation_id],
        outputs=_graph_loading_outputs(page),
        show_progress="hidden",
    ).then(
        fn=page.generate_knowledge_graph,
        inputs=_graph_refresh_inputs(page),
        outputs=_graph_refresh_outputs(page),
        show_progress="minimal",
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
        {
            "fn": page.refresh_chat_file_list,
            "inputs": _chat_file_list_inputs(page),
            "outputs": _chat_file_list_outputs(page),
            "show_progress": "hidden",
        },
        {
            "fn": page.show_knowledge_graph_loading,
            "inputs": [page.chat_control.conversation_id],
            "outputs": _graph_loading_outputs(page),
            "show_progress": "hidden",
        },
        {
            "fn": page.refresh_knowledge_graph,
            "inputs": _graph_refresh_inputs(page),
            "outputs": _graph_refresh_outputs(page),
            "show_progress": "hidden",
        },
    ]
    for definition in definitions:
        page._app.subscribe_event(name=event_name, definition=definition)
