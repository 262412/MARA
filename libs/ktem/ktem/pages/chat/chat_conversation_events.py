from __future__ import annotations

from typing import Any

import gradio as gr


def bind_chat_conversation_events(
    page: Any,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
    clear_bot_message_selection_js: str,
    pdfview_js: str,
) -> None:
    page.chat_control.btn_chat_expand.click(
        fn=None, inputs=None, js="function() {toggleChatColumn();}"
    )
    if demo_mode:
        _bind_demo_conversation_events(page, chat_input_focus_js)
    else:
        _bind_standard_conversation_events(page, chat_input_focus_js)
        _bind_delete_conversation_events(page)
    _bind_conversation_select_event(
        page,
        demo_mode=demo_mode,
        chat_input_focus_js=chat_input_focus_js,
        clear_bot_message_selection_js=clear_bot_message_selection_js,
        pdfview_js=pdfview_js,
    )


def _conversation_outputs(page: Any) -> list[Any]:
    return [
        page.chat_control.conversation_id,
        page.chat_control.conversation,
        page.chat_control.conversation_rn,
        page.chat_panel.chatbot,
        page.followup_questions,
        page.info_panel,
        page.state_plot_panel,
        page.state_retrieval_history,
        page.state_plot_history,
        page.chat_control.cb_is_public,
        page.state_chat,
    ] + page._indices_input


def _suggest_chat_inputs(page: Any) -> list[Any]:
    return [
        page._app.settings_state,
        page.language,
        page.chat_panel.chatbot,
        page._use_suggestion,
    ]


def _suggest_chat_outputs(page: Any) -> list[Any]:
    return [page.followup_questions_ui, page.followup_questions]


def _bind_demo_conversation_events(page: Any, chat_input_focus_js: str) -> None:
    page.chat_control.btn_demo_logout.click(fn=None, js=page.chat_control.logout_js)
    page.chat_control.btn_new.click(
        fn=lambda: page.chat_control.select_conv("", None),
        outputs=_conversation_outputs(page),
    ).then(
        lambda: (gr.update(visible=False), gr.update(visible=True)),
        outputs=[page.paper_list.accordion, page.chat_settings],
    ).then(
        fn=lambda: "",
        outputs=[page.answer_panel],
    ).then(
        fn=page.render_latest_citations_card,
        inputs=[page.state_retrieval_history],
        outputs=[page.citations_panel],
    ).then(
        fn=page.render_latest_reasoning_trace,
        inputs=[page.chat_panel.chatbot, page.state_retrieval_history],
        outputs=[page.reasoning_trace_panel],
    ).then(
        fn=lambda: "",
        outputs=[page._last_question],
    ).then(
        fn=page.suggest_chat_conv,
        inputs=_suggest_chat_inputs(page),
        outputs=_suggest_chat_outputs(page),
    ).then(
        fn=None, inputs=None, js=chat_input_focus_js
    )


def _bind_standard_conversation_events(page: Any, chat_input_focus_js: str) -> None:
    page.chat_control.btn_new.click(
        page.chat_control.new_conv,
        inputs=page._app.user_id,
        outputs=[page.chat_control.conversation_id, page.chat_control.conversation],
        show_progress="hidden",
    ).then(
        page.chat_control.select_conv,
        inputs=[page.chat_control.conversation, page._app.user_id],
        outputs=_conversation_outputs(page),
        show_progress="hidden",
    ).then(
        fn=page._json_to_plot,
        inputs=page.state_plot_panel,
        outputs=page.plot_panel,
    ).then(
        fn=lambda: "",
        outputs=[page.answer_panel],
    ).then(
        fn=page.render_latest_citations_card,
        inputs=[page.state_retrieval_history],
        outputs=[page.citations_panel],
    ).then(
        fn=page.render_latest_reasoning_trace,
        inputs=[page.chat_panel.chatbot, page.state_retrieval_history],
        outputs=[page.reasoning_trace_panel],
    ).then(
        fn=lambda: "",
        outputs=[page._last_question],
    ).then(
        fn=page.suggest_chat_conv,
        inputs=_suggest_chat_inputs(page),
        outputs=_suggest_chat_outputs(page),
    ).then(
        fn=None, inputs=None, js=chat_input_focus_js
    )


def _bind_delete_conversation_events(page: Any) -> None:
    page.chat_control.btn_del.click(
        lambda conv_id: page.toggle_delete(conv_id),
        inputs=[page.chat_control.conversation_id],
        outputs=[page.chat_control._new_delete, page.chat_control._delete_confirm],
    )
    page.chat_control.btn_del_conf.click(
        page.chat_control.delete_conv,
        inputs=[page.chat_control.conversation_id, page._app.user_id],
        outputs=[page.chat_control.conversation_id, page.chat_control.conversation],
        show_progress="hidden",
    ).then(
        page.chat_control.select_conv,
        inputs=[page.chat_control.conversation, page._app.user_id],
        outputs=_conversation_outputs(page),
        show_progress="hidden",
    ).then(
        fn=page._json_to_plot,
        inputs=page.state_plot_panel,
        outputs=page.plot_panel,
    ).then(
        fn=page.render_latest_citations_card,
        inputs=[page.state_retrieval_history],
        outputs=[page.citations_panel],
    ).then(
        fn=page.render_latest_reasoning_trace,
        inputs=[page.chat_panel.chatbot, page.state_retrieval_history],
        outputs=[page.reasoning_trace_panel],
    ).then(
        lambda: page.toggle_delete(""),
        outputs=[page.chat_control._new_delete, page.chat_control._delete_confirm],
    )
    page.chat_control.btn_del_cnl.click(
        lambda: page.toggle_delete(""),
        outputs=[page.chat_control._new_delete, page.chat_control._delete_confirm],
    )
    page.chat_control.btn_conversation_rn.click(
        lambda: gr.update(visible=True),
        outputs=[page.chat_control.conversation_rn],
    )
    page.chat_control.conversation_rn.submit(
        page.chat_control.rename_conv,
        inputs=[
            page.chat_control.conversation_id,
            page.chat_control.conversation_rn,
            gr.State(value=True),
            page._app.user_id,
        ],
        outputs=[
            page.chat_control.conversation,
            page.chat_control.conversation,
            page.chat_control.conversation_rn,
        ],
        show_progress="hidden",
    )


def _bind_conversation_select_event(
    page: Any,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
    clear_bot_message_selection_js: str,
    pdfview_js: str,
) -> None:
    on_conv_select = (
        page.chat_control.conversation.select(
            page.chat_control.select_conv,
            inputs=[page.chat_control.conversation, page._app.user_id],
            outputs=_conversation_outputs(page),
            show_progress="hidden",
        )
        .then(
            fn=page._json_to_plot,
            inputs=page.state_plot_panel,
            outputs=page.plot_panel,
        )
        .then(
            lambda: page.toggle_delete(""),
            outputs=[page.chat_control._new_delete, page.chat_control._delete_confirm],
        )
        .then(
            fn=page.suggest_chat_conv,
            inputs=_suggest_chat_inputs(page),
            outputs=_suggest_chat_outputs(page),
        )
    )

    if demo_mode:
        on_conv_select = on_conv_select.then(
            lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[page.paper_list.accordion, page.chat_settings],
        )

    _append_conversation_preview_refresh(
        page,
        on_conv_select,
        chat_input_focus_js=chat_input_focus_js,
        clear_bot_message_selection_js=clear_bot_message_selection_js,
        pdfview_js=pdfview_js,
    )


def _append_conversation_preview_refresh(
    page: Any,
    event_chain: Any,
    *,
    chat_input_focus_js: str,
    clear_bot_message_selection_js: str,
    pdfview_js: str,
) -> None:
    event_chain.then(
        fn=page.page_preview.refresh_selected_file_preview,
        inputs=[
            page.first_selector_choices,
            page._indices_input[1],
            page.chat_panel.page_number,
            page._active_file_total_pages,
        ],
        outputs=[
            page._active_file_id,
            page._active_file_name,
            page._active_file_path,
            page.chat_panel.page_number,
            page._active_file_total_pages,
            page.chat_panel.pdf_preview_src,
            page.chat_panel.pdf_preview_notice,
        ],
        show_progress="hidden",
    ).then(
        fn=page.refresh_page_context_view,
        inputs=[
            page._active_file_id,
            page._active_file_name,
            page._active_file_path,
            page.chat_panel.page_number,
            page._active_file_total_pages,
            page.page_strip_search,
        ],
        outputs=[
            page.page_strip_file_summary,
            page.page_thumbnail_strip,
            page.page_metadata_strip,
        ],
        show_progress="hidden",
    ).then(
        fn=lambda: True,
        js=clear_bot_message_selection_js,
    ).then(
        fn=lambda: "",
        outputs=[page._selected_page_text],
        show_progress="hidden",
    ).then(
        fn=lambda: True,
        inputs=None,
        outputs=[page._preview_links],
        js=pdfview_js,
    ).then(
        fn=lambda history: history[-1][1] if history else "",
        inputs=[page.chat_panel.chatbot],
        outputs=[page.answer_panel],
        show_progress="hidden",
    ).then(
        fn=lambda history: history[-1][0] if history else "",
        inputs=[page.chat_panel.chatbot],
        outputs=[page._last_question],
        show_progress="hidden",
    ).then(
        fn=page.render_latest_citations_card,
        inputs=[page.state_retrieval_history],
        outputs=[page.citations_panel],
        show_progress="hidden",
    ).then(
        fn=page.render_latest_reasoning_trace,
        inputs=[page.chat_panel.chatbot, page.state_retrieval_history],
        outputs=[page.reasoning_trace_panel],
        show_progress="hidden",
    ).then(
        fn=None, inputs=None, outputs=None, js=chat_input_focus_js
    )
