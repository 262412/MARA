from __future__ import annotations

import logging

import gradio as gr

logger = logging.getLogger(__name__)


def _iter_index_changed_events(page):
    return page._app.get_event(f"onFileIndex{page._index.id}Changed")


def _append_index_changed_events(event_chain, page):
    for event in _iter_index_changed_events(page):
        event_chain = event_chain.then(**event)
    return event_chain


def _append_file_list_refresh(event_chain, page):
    return event_chain.then(
        fn=page.list_file,
        inputs=[page._app.user_id, page.filter],
        outputs=[page.file_list_state, page.file_list],
        concurrency_limit=20,
    )


def _file_selection_outputs(page):
    return [
        page.chunks,
        page.deselect_button,
        page.delete_button,
        page.download_single_button,
        page.chat_button,
    ]


def _append_quick_upload_chat_refresh(event_chain, page):
    return (
        event_chain.success(
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
                page._app.chat_page.workbench_file_summary,
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


def _append_uploaded_chat_graph_refresh(event_chain, page):
    return (
        event_chain.then(
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
                page._app.chat_page.workbench_file_summary,
            ],
            show_progress="hidden",
        )
    )


def _set_chat_page_indexing_functions(page) -> None:
    page._app.chat_page.first_indexing_url_fn = page.index_fn_url_with_default_loaders
    page._app.chat_page.first_indexing_file_fn = page.index_fn_file_with_default_loaders


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

        _set_chat_page_indexing_functions(page)

        if not demo_mode:
            _register_quick_file_upload_event(page, chat_input_focus_js)
        _register_quick_url_upload_event(
            page,
            demo_mode=demo_mode,
            chat_input_focus_js=chat_input_focus_js,
        )
    except Exception as exc:
        print(exc)


def _quick_upload_waiting_update():
    message = (
        "Please wait for the indexing process to complete before adding your question."
    )
    return gr.update(value=message)


def _quick_upload_reset_outputs(page, source_component):
    return [source_component, page._app.chat_page._indices_input[0]]


def _append_quick_upload_focus(event_chain, chat_input_focus_js: str):
    return event_chain.then(
        fn=lambda: True,
        inputs=None,
        outputs=None,
        js=chat_input_focus_js,
    )


def _register_quick_file_upload_event(page, chat_input_focus_js: str) -> None:
    quick_uploaded_event = (
        page._app.chat_page.quick_file_upload.upload(
            fn=_quick_upload_waiting_update,
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
            outputs=_quick_upload_reset_outputs(
                page, page._app.chat_page.quick_file_upload
            ),
        )
    )
    quick_uploaded_event = _append_index_changed_events(quick_uploaded_event, page)
    quick_uploaded_event = _append_quick_upload_chat_refresh(quick_uploaded_event, page)
    quick_uploaded_event = _append_file_list_refresh(quick_uploaded_event, page)
    _append_quick_upload_focus(quick_uploaded_event, chat_input_focus_js)


def _register_quick_url_upload_event(
    page,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
) -> None:
    quick_url_uploaded_event = (
        page._app.chat_page.quick_urls.submit(
            fn=_quick_upload_waiting_update,
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
            outputs=_quick_upload_reset_outputs(page, page._app.chat_page.quick_urls),
        )
    )
    quick_url_uploaded_event = _append_index_changed_events(
        quick_url_uploaded_event, page
    )
    quick_url_uploaded_event = _append_quick_upload_chat_refresh(
        quick_url_uploaded_event, page
    )

    if not demo_mode:
        quick_url_uploaded_event = _append_file_list_refresh(
            quick_url_uploaded_event, page
        )

    _append_quick_upload_focus(quick_url_uploaded_event, chat_input_focus_js)


def _page_selector_outputs(page):
    selector_ui = page._index.get_selector_component_ui()
    return [selector_ui.selector, selector_ui.mode, page._app.tabs]


def _register_delete_file_events(page) -> None:
    on_deleted = (
        page.delete_button.click(
            fn=page.delete_event,
            inputs=[page.selected_file_id, page._app.user_id],
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
            outputs=_file_selection_outputs(page),
            show_progress="hidden",
        )
    )
    _append_index_changed_events(on_deleted, page)

    page.deselect_button.click(
        fn=lambda: (None, page.selected_panel_false),
        inputs=[],
        outputs=[page.selected_file_id, page.selected_panel],
        show_progress="hidden",
    ).then(
        fn=page.file_selected,
        inputs=[page.selected_file_id],
        outputs=_file_selection_outputs(page),
        show_progress="hidden",
    )


def _register_download_events(page, *, sso_enabled: bool) -> None:
    if not sso_enabled:
        page.download_all_button.click(
            fn=page.download_all_files,
            inputs=[],
            outputs=page.download_all_button,
            show_progress="hidden",
        )
        page.download_single_button.click(
            fn=page.download_single_file,
            inputs=[page.is_zipped_state, page.selected_file_id],
            outputs=[page.is_zipped_state, page.download_single_button],
            show_progress="hidden",
        )
        return

    page.download_single_button.click(
        fn=page.download_single_file_simple,
        inputs=[page.is_zipped_state, page.chunks, page.selected_file_id],
        outputs=[page.is_zipped_state, page.download_single_button],
        show_progress="hidden",
    )


def _register_delete_all_events(page) -> None:
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
        inputs=[page.file_list, page._app.user_id],
        outputs=[],
        show_progress="hidden",
    ).then(
        fn=page.list_file,
        inputs=[page._app.user_id, page.filter],
        outputs=[page.file_list_state, page.file_list],
    )
    on_deleted_all = _append_index_changed_events(on_deleted_all, page)

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


def _should_refresh_uploaded_chat_graph(page) -> bool:
    return (
        page._index.id == 1
        and getattr(page._app, "chat_page", None) is not None
        and getattr(page._app.chat_page, "knowledge_graph", None) is not None
        and len(getattr(page._app.chat_page, "_indices_input", [])) > 1
    )


def _register_upload_events(page) -> None:
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
    )
    uploaded_event = _append_file_list_refresh(uploaded_event, page)
    uploaded_event = _append_index_changed_events(uploaded_event, page)
    if _should_refresh_uploaded_chat_graph(page):
        uploaded_event = _append_uploaded_chat_graph_refresh(uploaded_event, page)

    on_uploaded.success(fn=lambda: None, outputs=[page.files])
    page.btn_close_upload_progress_panel.click(
        fn=lambda: (gr.update(visible=False), "", ""),
        outputs=[page.upload_progress_panel, page.upload_result, page.upload_info],
    )


def _register_file_selection_events(page) -> None:
    page.file_list.select(
        fn=page.interact_file_list,
        inputs=[page.file_list],
        outputs=[page.selected_file_id, page.selected_panel],
        show_progress="hidden",
    ).then(
        fn=page.file_selected,
        inputs=[page.selected_file_id],
        outputs=_file_selection_outputs(page),
        show_progress="hidden",
    )

    page.filter.submit(
        fn=page.list_file,
        inputs=[page._app.user_id, page.filter],
        outputs=[page.file_list_state, page.file_list],
        show_progress="hidden",
    )


def _group_closed_event(page):
    return {
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


def _register_group_events(page, page_selector_outputs) -> None:
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

    on_group_closed_event = _group_closed_event(page)
    page.group_close_button.click(**on_group_closed_event)
    on_group_saved = _register_group_save_event(page, on_group_closed_event)
    on_group_deleted = _register_group_delete_event(page, on_group_closed_event)

    _append_index_changed_events(on_group_deleted, page)
    _append_index_changed_events(on_group_saved, page)


def _register_group_save_event(page, on_group_closed_event):
    return (
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


def _register_group_delete_event(page, on_group_closed_event):
    return (
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


def register_file_index_events(
    page,
    *,
    demo_mode: bool,
    sso_enabled: bool,
) -> None:
    page_selector_outputs = _page_selector_outputs(page)

    _register_delete_file_events(page)
    page.chat_button.click(
        fn=page.set_file_id_selector,
        inputs=[page.selected_file_id],
        outputs=page_selector_outputs,
    )
    _register_download_events(page, sso_enabled=sso_enabled)
    _register_delete_all_events(page)
    _register_upload_events(page)
    _register_file_selection_events(page)
    _register_group_events(page, page_selector_outputs)

    if demo_mode:
        return
