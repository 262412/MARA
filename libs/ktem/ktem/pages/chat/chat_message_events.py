from __future__ import annotations

from typing import Any

import gradio as gr

from .chat_docqa_runtime import docqa_research_control_inputs


def bind_chat_submit_events(
    page: Any,
    *,
    demo_mode: bool,
    pdfview_js: str,
    scroll_answer_panel_js: str,
) -> dict[str, Any]:
    text_input = page.chat_panel.text_input
    assert text_input is not None

    chat_event = _submit_message_event(
        page,
        text_input,
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
    *,
    pdfview_js: str,
    scroll_answer_panel_js: str,
) -> Any:
    chat_event = gr.on(
        triggers=[text_input.submit],
        fn=page.submit_msg,
        inputs=_submit_message_inputs(page, text_input),
        outputs=_submit_message_outputs(page),
        concurrency_limit=20,
        show_progress="hidden",
    )
    chat_event = _append_runtime_stream(page, chat_event)
    chat_event = _append_request_cache(page, chat_event)
    chat_event = _append_post_stream_ui(
        page,
        chat_event,
        pdfview_js=pdfview_js,
        scroll_answer_panel_js=scroll_answer_panel_js,
    )
    return _append_conversation_name_update(page, chat_event)


def _submit_message_inputs(page: Any, text_input: Any) -> list[Any]:
    return [
        text_input,
        page.chat_panel.chatbot,
        page._app.user_id,
        page._app.settings_state,
        page.chat_control.conversation_id,
        page.chat_control.conversation_rn,
        page.first_selector_choices,
        page._graph_source_ids,
        page._selected_page_text,
        page._selected_graph_context,
    ]


def _submit_message_outputs(page: Any) -> list[Any]:
    return [
        page.chat_panel.text_input,
        page.chat_panel.chatbot,
        page.chat_control.conversation_id,
        page.chat_control.conversation,
        page.chat_control.conversation_rn,
        page._indices_input[0],
        page._indices_input[1],
        page._last_question,
        page._command_state,
        page._selected_page_text,
        page._selected_graph_context,
        page._graph_source_ids,
    ]


def _append_runtime_stream(page: Any, chat_event: Any) -> Any:
    return chat_event.success(**_chat_runtime_event(page))


def _append_request_cache(page: Any, chat_event: Any) -> Any:
    return chat_event.success(
        fn=page.page_preview.cache_page_outputs,
        inputs=[
            page._page_outputs_cache,
            page._request_page_number,
            page._request_last_question,
            page._request_info_html,
            page._request_answer_html,
            page._request_file_id,
            page._request_chat_history,
        ],
        outputs=[page._page_outputs_cache],
        show_progress="hidden",
    )


def _append_post_stream_ui(
    page: Any,
    chat_event: Any,
    *,
    pdfview_js: str,
    scroll_answer_panel_js: str,
) -> Any:
    return (
        chat_event.then(
            fn=lambda: "",
            outputs=[page._selected_page_text],
            show_progress="hidden",
        )
        .then(
            fn=lambda: True,
            inputs=None,
            outputs=[page._preview_links],
            js=pdfview_js,
        )
        .then(
            fn=None,
            inputs=None,
            outputs=None,
            js=scroll_answer_panel_js,
        )
    )


def _append_conversation_name_update(page: Any, chat_event: Any) -> Any:
    return chat_event.success(
        fn=page.check_and_suggest_name_conv,
        inputs=page._request_chat_history,
        outputs=[
            page.chat_control.conversation_rn,
            page._conversation_renamed,
        ],
    ).success(
        page.chat_control.rename_conv,
        inputs=[
            page.chat_control.conversation_id,
            page.chat_control.conversation_rn,
            page._conversation_renamed,
            page._app.user_id,
        ],
        outputs=[
            page.chat_control.conversation,
            page.chat_control.conversation,
            page.chat_control.conversation_rn,
        ],
        show_progress="hidden",
    )


def _chat_runtime_event(page: Any) -> dict[str, Any]:
    return {
        "fn": page.chat_fn,
        "inputs": [
            page.chat_control.conversation_id,
            page.chat_panel.chatbot,
            page._app.settings_state,
            page._reasoning_type,
            page.model_type,
            page.use_mindmap,
            page.citation,
            page.language,
            page.state_chat,
            page._command_state,
            page._app.user_id,
            page._active_file_id,
            page._active_file_name,
            page.chat_panel.page_number,
            page.chat_panel.qa_scope,
            page._selected_page_text,
            page._selected_graph_context,
            *docqa_research_control_inputs(page),
            page.state_plot_panel,
        ]
        + page._indices_input,
        "outputs": [
            page.chat_panel.chatbot,
            page.info_panel,
            page.plot_panel,
            page.state_plot_panel,
            page.state_chat,
            page.answer_panel,
            page.citations_panel,
            page.reasoning_trace_panel,
            page._request_page_number,
            page._request_file_id,
            page._request_last_question,
            page._request_info_html,
            page._request_answer_html,
            page._request_chat_history,
        ],
        "concurrency_limit": 20,
        "show_progress": "minimal",
    }


def _append_persist_data_source(page: Any, chat_event: Any) -> Any:
    return chat_event.then(
        fn=page.persist_data_source,
        inputs=[
            page.chat_control.conversation_id,
            page._app.user_id,
            page._request_info_html,
            page.state_plot_panel,
            page.state_retrieval_history,
            page.state_plot_history,
            page._request_chat_history,
            page.state_chat,
            page._graph_source_ids,
        ]
        + page._indices_input,
        outputs=[
            page.state_retrieval_history,
            page.state_plot_history,
        ],
        concurrency_limit=20,
    )
