from __future__ import annotations

import gradio as gr

from ._chat_upload_events import register_quick_upload_events, register_upload_events
from ._event_chain import append_index_changed_events as _append_index_changed_events

__all__ = [
    "register_file_index_events",
    "register_quick_upload_events",
    "register_upload_events",
]


def _file_selection_outputs(page):
    return [
        page.chunks,
        page.deselect_button,
        page.delete_button,
        page.download_single_button,
        page.chat_button,
    ]


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
    register_upload_events(page)
    _register_file_selection_events(page)
    _register_group_events(page, page_selector_outputs)

    if demo_mode:
        return
