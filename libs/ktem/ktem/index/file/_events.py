from __future__ import annotations

import logging

import gradio as gr

logger = logging.getLogger(__name__)


def _iter_index_changed_events(page):
    return page._app.get_event(f"onFileIndex{page._index.id}Changed")


def register_quick_upload_events(
    page,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
) -> None:
    try:
        if page._index.id != 1:
            return

        page.quick_upload_state = gr.State(value=[])
        logger.debug("Setting up quick upload event")

        page._app.chat_page.first_indexing_url_fn = (
            page.index_fn_url_with_default_loaders
        )

        if not demo_mode:
            quick_uploaded_event = (
                page._app.chat_page.quick_file_upload.upload(
                    fn=lambda: gr.update(
                        value="Please wait for the indexing process "
                        "to complete before adding your question."
                    ),
                    outputs=page._app.chat_page.quick_file_upload_status,
                )
                .then(
                    fn=page.index_fn_file_with_default_loaders,
                    inputs=[
                        page._app.chat_page.quick_file_upload,
                        gr.State(value=False),
                        page._app.settings_state,
                        page._app.user_id,
                    ],
                    outputs=page.quick_upload_state,
                    concurrency_limit=10,
                )
                .success(
                    fn=lambda: [
                        gr.update(value=None),
                        gr.update(value="select"),
                    ],
                    outputs=[
                        page._app.chat_page.quick_file_upload,
                        page._app.chat_page._indices_input[0],
                    ],
                )
            )
            for event in _iter_index_changed_events(page):
                quick_uploaded_event = quick_uploaded_event.then(**event)

            quick_uploaded_event = (
                quick_uploaded_event.success(
                    fn=page._app.chat_page.merge_graph_source_ids,
                    inputs=[
                        page._app.chat_page._graph_source_ids,
                        page.quick_upload_state,
                    ],
                    outputs=[page._app.chat_page._graph_source_ids],
                    show_progress="hidden",
                )
                .then(
                    fn=page._app.chat_page.refresh_chat_file_list,
                    inputs=[
                        page._app.chat_page.chat_control.conversation_id,
                        page._app.user_id,
                        page._app.chat_page.first_selector_choices,
                        page._app.chat_page._indices_input[1],
                        page._app.chat_page._graph_source_ids,
                        page._app.chat_page.chat_file_filter,
                    ],
                    outputs=[
                        page._app.chat_page.chat_file_rows,
                        page._app.chat_page.chat_file_list,
                        page._app.chat_page.chat_selected_file,
                    ],
                    show_progress="hidden",
                )
                .then(
                    fn=page._app.chat_page.show_knowledge_graph_loading,
                    inputs=[page._app.chat_page.chat_control.conversation_id],
                    outputs=[
                        page._app.chat_page.plot_panel,
                        page._app.chat_page.knowledge_graph_status,
                    ],
                    show_progress="hidden",
                )
                .then(
                    fn=page._app.chat_page.refresh_knowledge_graph,
                    inputs=[
                        page._app.chat_page.chat_control.conversation_id,
                        page._app.chat_page._graph_source_ids,
                        page._app.chat_page._active_file_id,
                        page._app.chat_page._indices_input[1],
                    ],
                    outputs=[
                        page._app.chat_page.plot_panel,
                        page._app.chat_page.state_plot_panel,
                        page._app.chat_page.knowledge_graph_status,
                        page._app.chat_page._graph_source_ids,
                    ],
                    show_progress="hidden",
                )
                .success(
                    fn=lambda x: x,
                    inputs=page.quick_upload_state,
                    outputs=page._app.chat_page._indices_input[1],
                )
                .success(
                    fn=page._app.chat_page.persist_conversation_source_scope,
                    inputs=[
                        page._app.chat_page.chat_control.conversation_id,
                        page._app.user_id,
                        page._app.chat_page._graph_source_ids,
                    ],
                    outputs=[page._app.chat_page._graph_source_ids],
                    show_progress="hidden",
                )
                .then(
                    fn=lambda: gr.update(value="Indexing completed."),
                    outputs=page._app.chat_page.quick_file_upload_status,
                )
                .then(
                    fn=page.list_file,
                    inputs=[page._app.user_id, page.filter],
                    outputs=[page.file_list_state, page.file_list],
                    concurrency_limit=20,
                )
                .then(
                    fn=lambda: True,
                    inputs=None,
                    outputs=None,
                    js=chat_input_focus_js,
                )
            )

        quick_url_uploaded_event = (
            page._app.chat_page.quick_urls.submit(
                fn=lambda: gr.update(
                    value="Please wait for the indexing process "
                    "to complete before adding your question."
                ),
                outputs=page._app.chat_page.quick_file_upload_status,
            )
            .then(
                fn=page.index_fn_url_with_default_loaders,
                inputs=[
                    page._app.chat_page.quick_urls,
                    gr.State(value=False),
                    page._app.settings_state,
                    page._app.user_id,
                ],
                outputs=page.quick_upload_state,
                concurrency_limit=10,
            )
            .success(
                fn=lambda: [
                    gr.update(value=None),
                    gr.update(value="select"),
                ],
                outputs=[
                    page._app.chat_page.quick_urls,
                    page._app.chat_page._indices_input[0],
                ],
            )
        )
        for event in _iter_index_changed_events(page):
            quick_url_uploaded_event = quick_url_uploaded_event.then(**event)

        quick_url_uploaded_event = (
            quick_url_uploaded_event.success(
                fn=page._app.chat_page.merge_graph_source_ids,
                inputs=[
                    page._app.chat_page._graph_source_ids,
                    page.quick_upload_state,
                ],
                outputs=[page._app.chat_page._graph_source_ids],
                show_progress="hidden",
            )
            .then(
                fn=page._app.chat_page.refresh_chat_file_list,
                inputs=[
                    page._app.chat_page.chat_control.conversation_id,
                    page._app.user_id,
                    page._app.chat_page.first_selector_choices,
                    page._app.chat_page._indices_input[1],
                    page._app.chat_page._graph_source_ids,
                    page._app.chat_page.chat_file_filter,
                ],
                outputs=[
                    page._app.chat_page.chat_file_rows,
                    page._app.chat_page.chat_file_list,
                    page._app.chat_page.chat_selected_file,
                ],
                show_progress="hidden",
            )
            .then(
                fn=page._app.chat_page.show_knowledge_graph_loading,
                inputs=[page._app.chat_page.chat_control.conversation_id],
                outputs=[
                    page._app.chat_page.plot_panel,
                    page._app.chat_page.knowledge_graph_status,
                ],
                show_progress="hidden",
            )
            .then(
                fn=page._app.chat_page.refresh_knowledge_graph,
                inputs=[
                    page._app.chat_page.chat_control.conversation_id,
                    page._app.chat_page._graph_source_ids,
                    page._app.chat_page._active_file_id,
                    page._app.chat_page._indices_input[1],
                ],
                outputs=[
                    page._app.chat_page.plot_panel,
                    page._app.chat_page.state_plot_panel,
                    page._app.chat_page.knowledge_graph_status,
                    page._app.chat_page._graph_source_ids,
                ],
                show_progress="hidden",
            )
            .success(
                fn=lambda x: x,
                inputs=page.quick_upload_state,
                outputs=page._app.chat_page._indices_input[1],
            )
            .success(
                fn=page._app.chat_page.persist_conversation_source_scope,
                inputs=[
                    page._app.chat_page.chat_control.conversation_id,
                    page._app.user_id,
                    page._app.chat_page._graph_source_ids,
                ],
                outputs=[page._app.chat_page._graph_source_ids],
                show_progress="hidden",
            )
            .then(
                fn=lambda: gr.update(value="Indexing completed."),
                outputs=page._app.chat_page.quick_file_upload_status,
            )
        )

        if not demo_mode:
            quick_url_uploaded_event = quick_url_uploaded_event.then(
                fn=page.list_file,
                inputs=[page._app.user_id, page.filter],
                outputs=[page.file_list_state, page.file_list],
                concurrency_limit=20,
            )

        quick_url_uploaded_event.then(
            fn=lambda: True,
            inputs=None,
            outputs=None,
            js=chat_input_focus_js,
        )
    except Exception as exc:
        print(exc)


def register_file_index_events(
    page,
    *,
    demo_mode: bool,
    sso_enabled: bool,
) -> None:
    selector_ui = page._index.get_selector_component_ui()
    page_selector_outputs = [
        selector_ui.selector,
        selector_ui.mode,
        page._app.tabs,
    ]

    on_deleted = (
        page.delete_button.click(
            fn=page.delete_event,
            inputs=[page.selected_file_id],
            outputs=None,
        )
        .then(
            fn=lambda: (None, page.selected_panel_false),
            inputs=[],
            outputs=[page.selected_file_id, page.selected_panel],
            show_progress="hidden",
        )
        .then(
            fn=page.list_file,
            inputs=[page._app.user_id, page.filter],
            outputs=[page.file_list_state, page.file_list],
        )
        .then(
            fn=page.file_selected,
            inputs=[page.selected_file_id],
            outputs=[
                page.chunks,
                page.deselect_button,
                page.delete_button,
                page.download_single_button,
                page.chat_button,
            ],
            show_progress="hidden",
        )
    )
    for event in _iter_index_changed_events(page):
        on_deleted = on_deleted.then(**event)

    page.deselect_button.click(
        fn=lambda: (None, page.selected_panel_false),
        inputs=[],
        outputs=[page.selected_file_id, page.selected_panel],
        show_progress="hidden",
    ).then(
        fn=page.file_selected,
        inputs=[page.selected_file_id],
        outputs=[
            page.chunks,
            page.deselect_button,
            page.delete_button,
            page.download_single_button,
            page.chat_button,
        ],
        show_progress="hidden",
    )

    page.chat_button.click(
        fn=page.set_file_id_selector,
        inputs=[page.selected_file_id],
        outputs=page_selector_outputs,
    )

    if not sso_enabled:
        page.download_all_button.click(
            fn=page.download_all_files,
            inputs=[],
            outputs=page.download_all_button,
            show_progress="hidden",
        )

    page.delete_all_button.click(
        fn=page.show_delete_all_confirm,
        inputs=[page.file_list],
        outputs=[
            page.delete_all_button,
            page.delete_all_button_confirm,
            page.delete_all_button_cancel,
        ],
    )
    page.delete_all_button_cancel.click(
        fn=lambda: [
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
        ],
        inputs=None,
        outputs=[
            page.delete_all_button,
            page.delete_all_button_confirm,
            page.delete_all_button_cancel,
        ],
    )

    on_deleted_all = page.delete_all_button_confirm.click(
        fn=page.delete_all_files,
        inputs=[page.file_list],
        outputs=[],
        show_progress="hidden",
    ).then(
        fn=page.list_file,
        inputs=[page._app.user_id, page.filter],
        outputs=[page.file_list_state, page.file_list],
    )
    for event in _iter_index_changed_events(page):
        on_deleted_all = on_deleted_all.then(**event)

    on_deleted_all.then(
        fn=lambda: [
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
        ],
        inputs=None,
        outputs=[
            page.delete_all_button,
            page.delete_all_button_confirm,
            page.delete_all_button_cancel,
        ],
    )

    if not sso_enabled:
        page.download_single_button.click(
            fn=page.download_single_file,
            inputs=[page.is_zipped_state, page.selected_file_id],
            outputs=[page.is_zipped_state, page.download_single_button],
            show_progress="hidden",
        )
    else:
        page.download_single_button.click(
            fn=page.download_single_file_simple,
            inputs=[page.is_zipped_state, page.chunks, page.selected_file_id],
            outputs=[page.is_zipped_state, page.download_single_button],
            show_progress="hidden",
        )

    on_uploaded = (
        page.upload_button.click(
            fn=lambda: gr.update(visible=True),
            outputs=[page.upload_progress_panel],
        )
        .then(
            fn=page.snapshot_source_ids,
            inputs=[page._app.user_id],
            outputs=[page.upload_before_source_ids],
            show_progress="hidden",
        )
        .then(
            fn=page.index_fn,
            inputs=[
                page.files,
                page.urls,
                page.reindex,
                page._app.settings_state,
                page._app.user_id,
            ],
            outputs=[page.upload_result, page.upload_info],
            concurrency_limit=20,
        )
        .then(
            fn=lambda: gr.update(value=""),
            outputs=[page.urls],
        )
    )

    uploaded_event = on_uploaded.then(
        fn=page.collect_new_source_ids,
        inputs=[page.upload_before_source_ids, page._app.user_id],
        outputs=[page.upload_new_source_ids],
        show_progress="hidden",
    ).then(
        fn=page.list_file,
        inputs=[page._app.user_id, page.filter],
        outputs=[page.file_list_state, page.file_list],
        concurrency_limit=20,
    )
    for event in _iter_index_changed_events(page):
        uploaded_event = uploaded_event.then(**event)

    if (
        page._index.id == 1
        and getattr(page._app, "chat_page", None) is not None
        and getattr(page._app.chat_page, "knowledge_graph", None) is not None
        and len(getattr(page._app.chat_page, "_indices_input", [])) > 1
    ):
        uploaded_event = (
            uploaded_event.then(
                fn=page._app.chat_page.merge_graph_source_ids,
                inputs=[
                    page._app.chat_page._graph_source_ids,
                    page.upload_new_source_ids,
                ],
                outputs=[page._app.chat_page._graph_source_ids],
                show_progress="hidden",
            )
            .then(
                fn=page._app.chat_page.persist_conversation_source_scope,
                inputs=[
                    page._app.chat_page.chat_control.conversation_id,
                    page._app.user_id,
                    page._app.chat_page._graph_source_ids,
                ],
                outputs=[page._app.chat_page._graph_source_ids],
                show_progress="hidden",
            )
            .then(
                fn=page._app.chat_page.refresh_chat_file_list,
                inputs=[
                    page._app.chat_page.chat_control.conversation_id,
                    page._app.user_id,
                    page._app.chat_page.first_selector_choices,
                    page._app.chat_page._indices_input[1],
                    page._app.chat_page._graph_source_ids,
                    page._app.chat_page.chat_file_filter,
                ],
                outputs=[
                    page._app.chat_page.chat_file_rows,
                    page._app.chat_page.chat_file_list,
                    page._app.chat_page.chat_selected_file,
                ],
                show_progress="hidden",
            )
            .then(
                fn=page._app.chat_page.refresh_knowledge_graph,
                inputs=[
                    page._app.chat_page.chat_control.conversation_id,
                    page._app.chat_page._graph_source_ids,
                    page._app.chat_page._active_file_id,
                    page._app.chat_page._indices_input[1],
                ],
                outputs=[
                    page._app.chat_page.plot_panel,
                    page._app.chat_page.state_plot_panel,
                    page._app.chat_page.knowledge_graph_status,
                    page._app.chat_page._graph_source_ids,
                ],
                show_progress="hidden",
            )
        )

    on_uploaded.success(
        fn=lambda: None,
        outputs=[page.files],
    )

    page.btn_close_upload_progress_panel.click(
        fn=lambda: (gr.update(visible=False), "", ""),
        outputs=[page.upload_progress_panel, page.upload_result, page.upload_info],
    )

    page.file_list.select(
        fn=page.interact_file_list,
        inputs=[page.file_list],
        outputs=[page.selected_file_id, page.selected_panel],
        show_progress="hidden",
    ).then(
        fn=page.file_selected,
        inputs=[page.selected_file_id],
        outputs=[
            page.chunks,
            page.deselect_button,
            page.delete_button,
            page.download_single_button,
            page.chat_button,
        ],
        show_progress="hidden",
    )

    page.group_list.select(
        fn=page.interact_group_list,
        inputs=[page.group_list_state],
        outputs=[
            page.group_label,
            page.selected_group_id,
            page.group_name,
            page.group_files,
        ],
        show_progress="hidden",
    ).then(
        fn=lambda: (
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=True),
            gr.update(visible=True),
        ),
        outputs=[
            page._group_info_panel,
            page.group_add_button,
            page.group_close_button,
            page.group_delete_button,
            page.group_chat_button,
        ],
    )

    page.filter.submit(
        fn=page.list_file,
        inputs=[page._app.user_id, page.filter],
        outputs=[page.file_list_state, page.file_list],
        show_progress="hidden",
    )

    page.group_add_button.click(
        fn=lambda: [
            gr.update(visible=False),
            gr.update(value="### Add new group"),
            gr.update(visible=True),
            gr.update(value=""),
            gr.update(value=[]),
            None,
        ],
        outputs=[
            page.group_add_button,
            page.group_label,
            page._group_info_panel,
            page.group_name,
            page.group_files,
            page.selected_group_id,
        ],
    )

    page.group_chat_button.click(
        fn=page.set_group_id_selector,
        inputs=[page.selected_group_id],
        outputs=page_selector_outputs,
    )

    on_group_closed_event = {
        "fn": lambda: [
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            None,
        ],
        "outputs": [
            page.group_add_button,
            page._group_info_panel,
            page.group_close_button,
            page.group_delete_button,
            page.group_chat_button,
            page.selected_group_id,
        ],
    }
    page.group_close_button.click(**on_group_closed_event)
    on_group_saved = (
        page.group_save_button.click(
            fn=page.save_group,
            inputs=[
                page.selected_group_id,
                page.group_name,
                page.group_files,
                page._app.user_id,
            ],
        )
        .then(
            fn=page.list_group,
            inputs=[page._app.user_id, page.file_list_state],
            outputs=[page.group_list_state, page.group_list],
        )
        .then(**on_group_closed_event)
    )
    on_group_deleted = (
        page.group_delete_button.click(
            fn=page.delete_group,
            inputs=[page.selected_group_id],
        )
        .then(
            fn=page.list_group,
            inputs=[page._app.user_id, page.file_list_state],
            outputs=[page.group_list_state, page.group_list],
        )
        .then(**on_group_closed_event)
    )

    for event in _iter_index_changed_events(page):
        on_group_deleted = on_group_deleted.then(**event)
        on_group_saved = on_group_saved.then(**event)

    if demo_mode:
        return
