from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import gradio as gr

from ._event_chain import (
    append_chat_input_focus,
    append_file_list_refresh,
    append_index_changed_events,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UploadEventPorts:
    inputs: Any = None
    outputs: Any = None

    @property
    def gradio_inputs(self) -> Any:
        return list(self.inputs) if isinstance(self.inputs, tuple) else self.inputs

    @property
    def gradio_outputs(self) -> Any:
        return list(self.outputs) if isinstance(self.outputs, tuple) else self.outputs


@dataclass(frozen=True)
class QuickUploadPorts:
    waiting: UploadEventPorts
    index: UploadEventPorts
    reset: UploadEventPorts
    graph_merge: UploadEventPorts
    chat_list: UploadEventPorts
    selector_copy: UploadEventPorts
    persist: UploadEventPorts
    complete: UploadEventPorts
    file_list: UploadEventPorts
    focus: UploadEventPorts


@dataclass(frozen=True)
class FullUploadPorts:
    show_panel: UploadEventPorts
    snapshot: UploadEventPorts
    index: UploadEventPorts
    clear_url: UploadEventPorts
    collect: UploadEventPorts
    file_list: UploadEventPorts
    graph_merge: UploadEventPorts
    persist: UploadEventPorts
    chat_list: UploadEventPorts
    clear_files: UploadEventPorts
    close_panel: UploadEventPorts


def quick_file_upload_ports(page: Any) -> QuickUploadPorts:
    return _quick_upload_ports(page, page._app.chat_page.quick_file_upload)


def quick_url_upload_ports(page: Any) -> QuickUploadPorts:
    return _quick_upload_ports(page, page._app.chat_page.quick_urls)


def _quick_upload_ports(page: Any, source_component: Any) -> QuickUploadPorts:
    chat_page = page._app.chat_page
    return QuickUploadPorts(
        waiting=UploadEventPorts(outputs=chat_page.quick_file_upload_status),
        index=UploadEventPorts(
            inputs=(
                source_component,
                gr.State(value=False),
                page._app.settings_state,
                page._app.user_id,
            ),
            outputs=page.quick_upload_state,
        ),
        reset=UploadEventPorts(outputs=(source_component, chat_page._indices_input[0])),
        graph_merge=UploadEventPorts(
            inputs=(chat_page._graph_source_ids, page.quick_upload_state),
            outputs=(chat_page._graph_source_ids,),
        ),
        chat_list=_chat_list_ports(page),
        selector_copy=UploadEventPorts(
            inputs=page._quick_upload_result,
            outputs=page._quick_selection_result,
        ),
        persist=_persist_ports(page),
        complete=UploadEventPorts(outputs=chat_page.quick_file_upload_status),
        file_list=_file_list_ports(page),
        focus=UploadEventPorts(),
    )


def full_upload_ports(page: Any) -> FullUploadPorts:
    graph_merge, persist, chat_list = _full_chat_ports(page)
    return FullUploadPorts(
        show_panel=UploadEventPorts(outputs=(page.upload_progress_panel,)),
        snapshot=UploadEventPorts(
            inputs=(page._app.user_id,), outputs=(page.upload_before_source_ids,)
        ),
        index=UploadEventPorts(
            inputs=(
                page.files,
                page.urls,
                page.reindex,
                page._app.settings_state,
                page._app.user_id,
            ),
            outputs=(page.upload_result, page.upload_info),
        ),
        clear_url=UploadEventPorts(outputs=(page.urls,)),
        collect=UploadEventPorts(
            inputs=(page.upload_before_source_ids, page._app.user_id),
            outputs=(page.upload_new_source_ids,),
        ),
        file_list=_file_list_ports(page),
        graph_merge=graph_merge,
        persist=persist,
        chat_list=chat_list,
        clear_files=UploadEventPorts(outputs=(page.files,)),
        close_panel=UploadEventPorts(
            outputs=(page.upload_progress_panel, page.upload_result, page.upload_info)
        ),
    )


def _full_chat_ports(
    page: Any,
) -> tuple[UploadEventPorts, UploadEventPorts, UploadEventPorts]:
    if not _should_refresh_uploaded_chat_graph(page):
        empty = UploadEventPorts()
        return empty, empty, empty
    chat_page = page._app.chat_page
    graph_merge = UploadEventPorts(
        inputs=(chat_page._graph_source_ids, page.upload_new_source_ids),
        outputs=(chat_page._graph_source_ids,),
    )
    return graph_merge, _persist_ports(page), _chat_list_ports(page)


def _file_list_ports(page: Any) -> UploadEventPorts:
    return UploadEventPorts(
        inputs=(page._app.user_id, page.filter),
        outputs=(page.file_list_state, page.file_list),
    )


def _chat_list_ports(page: Any) -> UploadEventPorts:
    chat_page = page._app.chat_page
    return UploadEventPorts(
        inputs=(
            chat_page.chat_control.conversation_id,
            page._app.user_id,
            chat_page.first_selector_choices,
            chat_page._indices_input[1],
            chat_page._graph_source_ids,
            chat_page.chat_file_filter,
            chat_page._file_browser_stamp,
        ),
        outputs=(chat_page._file_browser_result,),
    )


def _persist_ports(page: Any) -> UploadEventPorts:
    chat_page = page._app.chat_page
    return UploadEventPorts(
        inputs=(
            chat_page.chat_control.conversation_id,
            page._app.user_id,
            chat_page._graph_source_ids,
        ),
        outputs=(chat_page._graph_source_ids,),
    )


def register_quick_upload_events(
    page: Any,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
) -> None:
    stage = "initialization"
    try:
        if page._index.id != 1:
            return
        page.quick_upload_state = gr.State(value=[])
        _bind_quick_upload_results(page)
        _set_chat_page_indexing_functions(page)
        if not demo_mode:
            stage = "quick-file-upload"
            _register_quick_file_upload_event(page, chat_input_focus_js)
        stage = "quick-url-upload"
        _register_quick_url_upload_event(
            page,
            demo_mode=demo_mode,
            chat_input_focus_js=chat_input_focus_js,
        )
    except Exception:
        logger.exception(
            "Quick upload registration failed: index_id=%s demo_mode=%s stage=%s",
            getattr(getattr(page, "_index", None), "id", None),
            demo_mode,
            stage,
        )


def _set_chat_page_indexing_functions(page: Any) -> None:
    page._app.chat_page.first_indexing_url_fn = page.index_fn_url_with_default_loaders
    page._app.chat_page.first_indexing_file_fn = page.index_fn_file_with_default_loaders


def _quick_upload_waiting_update():
    message = (
        "Please wait for the indexing process to complete before adding your question."
    )
    return gr.update(value=message)


def _bind_quick_upload_results(page):
    from ktem.pages.chat.file_browser_updates import APPLY_UPLOAD_SELECTION_JS

    page._quick_upload_stamp = gr.JSON(value=None, visible=False)
    page._quick_upload_result = gr.JSON(value=None, visible=False)
    page._quick_selection_result = gr.JSON(value=None, visible=False)
    chat = page._app.chat_page
    page._quick_selection_result.change(
        fn=None,
        inputs=[page._quick_selection_result, chat.chat_control.conversation],
        outputs=[chat._indices_input[1]],
        js=APPLY_UPLOAD_SELECTION_JS,
        show_progress="hidden",
    )


def _quick_index_event(page, ports, callback, control):
    from ktem.pages.chat.file_browser_updates import (
        CAPTURE_UPLOAD_JS,
        quick_upload_result,
    )

    return {
        "fn": quick_upload_result(callback),
        "inputs": [
            *ports.index.gradio_inputs,
            page._quick_upload_stamp,
            page._app.chat_page.chat_control.conversation,
        ],
        "outputs": [ports.index.gradio_outputs, page._quick_upload_result],
        "js": CAPTURE_UPLOAD_JS.replace("CONTROL", control),
        "concurrency_limit": 10,
    }


def _quick_reset_event(page, ports):
    from ktem.pages.chat.file_browser_updates import APPLY_UPLOAD_RESET_JS

    result = gr.JSON(value=None, visible=False)
    result.change(
        fn=None,
        inputs=[result],
        outputs=ports.reset.gradio_outputs,
        js=APPLY_UPLOAD_RESET_JS,
        show_progress="hidden",
    )
    return {
        "fn": lambda x: x,
        "inputs": [page._quick_upload_result],
        "outputs": [result],
    }


def _register_quick_file_upload_event(page: Any, chat_input_focus_js: str) -> None:
    ports = quick_file_upload_ports(page)
    event_chain = (
        page._app.chat_page.quick_file_upload.upload(
            fn=_quick_upload_waiting_update,
            outputs=ports.waiting.gradio_outputs,
        )
        .then(
            **_quick_index_event(
                page, ports, page.index_fn_file_with_default_loaders, "file"
            )
        )
        .success(**_quick_reset_event(page, ports))
    )
    _append_quick_upload_tail(page, ports, event_chain, chat_input_focus_js)


def _register_quick_url_upload_event(
    page: Any,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
) -> None:
    ports = quick_url_upload_ports(page)
    event_chain = (
        page._app.chat_page.quick_urls.submit(
            fn=_quick_upload_waiting_update,
            outputs=ports.waiting.gradio_outputs,
        )
        .then(
            **_quick_index_event(
                page, ports, page.index_fn_url_with_default_loaders, "url"
            )
        )
        .success(**_quick_reset_event(page, ports))
    )
    _append_quick_upload_tail(
        page,
        ports,
        event_chain,
        chat_input_focus_js,
        refresh_file_list=not demo_mode,
    )


def _append_quick_upload_tail(
    page: Any,
    ports: QuickUploadPorts,
    event_chain: Any,
    chat_input_focus_js: str,
    *,
    refresh_file_list: bool = True,
) -> None:
    event_chain = append_index_changed_events(event_chain, page)
    event_chain = _append_quick_upload_chat_refresh(event_chain, page, ports)
    if refresh_file_list:
        event_chain = append_file_list_refresh(
            event_chain,
            page,
            inputs=ports.file_list.gradio_inputs,
            outputs=ports.file_list.gradio_outputs,
        )
    append_chat_input_focus(
        event_chain,
        chat_input_focus_js,
        inputs=ports.focus.gradio_inputs,
        outputs=ports.focus.gradio_outputs,
    )


def _append_quick_upload_chat_refresh(
    event_chain: Any, page: Any, ports: QuickUploadPorts
):
    from ktem.pages.chat.file_browser_updates import chat_file_refresh_event

    chat_page = page._app.chat_page
    return (
        event_chain.success(
            fn=chat_page.merge_graph_source_ids,
            inputs=ports.graph_merge.gradio_inputs,
            outputs=ports.graph_merge.gradio_outputs,
            show_progress="hidden",
        )
        .then(**chat_file_refresh_event(chat_page))
        .success(
            fn=lambda x: x,
            inputs=ports.selector_copy.gradio_inputs,
            outputs=ports.selector_copy.gradio_outputs,
        )
        .success(
            fn=chat_page.persist_conversation_source_scope,
            inputs=ports.persist.gradio_inputs,
            outputs=ports.persist.gradio_outputs,
            show_progress="hidden",
        )
        .then(
            fn=lambda: gr.update(value="Indexing completed."),
            outputs=ports.complete.gradio_outputs,
        )
    )


def register_upload_events(page: Any) -> None:
    ports = full_upload_ports(page)
    clear_url = (
        page.upload_button.click(
            fn=lambda: gr.update(visible=True),
            outputs=ports.show_panel.gradio_outputs,
        )
        .then(
            fn=page.snapshot_source_ids,
            inputs=ports.snapshot.gradio_inputs,
            outputs=ports.snapshot.gradio_outputs,
            show_progress="hidden",
        )
        .then(
            fn=page.index_fn,
            inputs=ports.index.gradio_inputs,
            outputs=ports.index.gradio_outputs,
            concurrency_limit=20,
        )
        .then(
            fn=lambda: gr.update(value=""),
            outputs=ports.clear_url.gradio_outputs,
        )
    )
    uploaded_event = clear_url.then(
        fn=page.collect_new_source_ids,
        inputs=ports.collect.gradio_inputs,
        outputs=ports.collect.gradio_outputs,
        show_progress="hidden",
    )
    uploaded_event = append_file_list_refresh(
        uploaded_event,
        page,
        inputs=ports.file_list.gradio_inputs,
        outputs=ports.file_list.gradio_outputs,
    )
    uploaded_event = append_index_changed_events(uploaded_event, page)
    if _should_refresh_uploaded_chat_graph(page):
        _append_uploaded_chat_graph_refresh(uploaded_event, page, ports)
    clear_url.success(fn=lambda: None, outputs=ports.clear_files.gradio_outputs)
    page.btn_close_upload_progress_panel.click(
        fn=lambda: (gr.update(visible=False), "", ""),
        outputs=ports.close_panel.gradio_outputs,
    )


def _should_refresh_uploaded_chat_graph(page: Any) -> bool:
    return (
        page._index.id == 1
        and getattr(page._app, "chat_page", None) is not None
        and getattr(page._app.chat_page, "knowledge_graph", None) is not None
        and len(getattr(page._app.chat_page, "_indices_input", [])) > 1
    )


def _append_uploaded_chat_graph_refresh(
    event_chain: Any, page: Any, ports: FullUploadPorts
):
    from ktem.pages.chat.file_browser_updates import chat_file_refresh_event

    chat_page = page._app.chat_page
    return (
        event_chain.then(
            fn=chat_page.merge_graph_source_ids,
            inputs=ports.graph_merge.gradio_inputs,
            outputs=ports.graph_merge.gradio_outputs,
            show_progress="hidden",
        )
        .then(
            fn=chat_page.persist_conversation_source_scope,
            inputs=ports.persist.gradio_inputs,
            outputs=ports.persist.gradio_outputs,
            show_progress="hidden",
        )
        .then(**chat_file_refresh_event(chat_page))
    )
