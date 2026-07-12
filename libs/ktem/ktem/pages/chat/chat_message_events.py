from __future__ import annotations

from typing import Any

import gradio as gr

from .chat_gradio_adapters import ChatSubmitPorts, chat_submit_ports


def bind_chat_submit_events(
    page: Any,
    *,
    demo_mode: bool,
    pdfview_js: str,
    scroll_answer_panel_js: str,
) -> dict[str, Any]:
    text_input = page.chat_panel.text_input
    assert text_input is not None
    ports = chat_submit_ports(page)

    chat_event = _submit_message_event(
        page,
        text_input,
        ports,
        pdfview_js=pdfview_js,
        scroll_answer_panel_js=scroll_answer_panel_js,
    )
    on_suggest_chat_event = build_suggest_chat_event(page)
    if not demo_mode:
        chat_event = _append_persist_data_source(page, chat_event)
    return on_suggest_chat_event


def build_suggest_chat_event(page: Any) -> dict[str, Any]:
    return {
        "fn": page.suggest_chat_conv,
        "inputs": [
            page._app.settings_state,
            page.language,
            page.chat_panel.chatbot,
            page._use_suggestion,
        ],
        "outputs": [
            page.followup_questions_ui,
            page.followup_questions,
        ],
        "show_progress": "hidden",
    }


def _submit_message_event(
    page: Any,
    text_input: Any,
    ports: ChatSubmitPorts,
    *,
    pdfview_js: str,
    scroll_answer_panel_js: str,
) -> Any:
    chat_event = gr.on(
        triggers=[text_input.submit],
        fn=page.submit_msg,
        inputs=ports.submit.gradio_inputs,
        outputs=ports.submit.gradio_outputs,
        concurrency_limit=20,
        show_progress="hidden",
    )
    chat_event = _append_runtime_stream(page, ports, chat_event)
    chat_event = _append_request_cache(page, ports, chat_event)
    chat_event = _append_post_stream_ui(
        page,
        ports,
        chat_event,
        pdfview_js=pdfview_js,
        scroll_answer_panel_js=scroll_answer_panel_js,
    )
    return _append_conversation_name_update(page, ports, chat_event)


def _append_runtime_stream(page: Any, ports: ChatSubmitPorts, chat_event: Any) -> Any:
    return chat_event.success(
        fn=page.chat_fn,
        inputs=ports.runtime.gradio_inputs,
        outputs=ports.runtime.gradio_outputs,
        concurrency_limit=20,
        show_progress="minimal",
    )


def _append_request_cache(page: Any, ports: ChatSubmitPorts, chat_event: Any) -> Any:
    return chat_event.success(
        fn=page.page_preview.cache_page_outputs,
        inputs=ports.cache.gradio_inputs,
        outputs=ports.cache.gradio_outputs,
        show_progress="hidden",
    )


def _append_post_stream_ui(
    page: Any,
    ports: ChatSubmitPorts,
    chat_event: Any,
    *,
    pdfview_js: str,
    scroll_answer_panel_js: str,
) -> Any:
    return (
        chat_event.then(
            fn=lambda: "",
            outputs=ports.clear_selection.gradio_outputs,
            show_progress="hidden",
        )
        .then(
            fn=lambda: True,
            inputs=ports.pdf_refresh.gradio_inputs,
            outputs=ports.pdf_refresh.gradio_outputs,
            js=pdfview_js,
        )
        .then(
            fn=None,
            inputs=ports.scroll.gradio_inputs,
            outputs=ports.scroll.gradio_outputs,
            js=scroll_answer_panel_js,
        )
    )


def _append_conversation_name_update(
    page: Any, ports: ChatSubmitPorts, chat_event: Any
) -> Any:
    return chat_event.success(
        fn=page.check_and_suggest_name_conv,
        inputs=ports.suggest_name.gradio_inputs,
        outputs=ports.suggest_name.gradio_outputs,
    ).success(
        page.chat_control.rename_conv,
        inputs=ports.rename.gradio_inputs,
        outputs=ports.rename.gradio_outputs,
        show_progress="hidden",
    )


def _append_persist_data_source(page: Any, chat_event: Any) -> Any:
    ports = chat_submit_ports(page)
    return chat_event.then(
        fn=page.persist_data_source,
        inputs=ports.persist.gradio_inputs,
        outputs=ports.persist.gradio_outputs,
        concurrency_limit=20,
    )
