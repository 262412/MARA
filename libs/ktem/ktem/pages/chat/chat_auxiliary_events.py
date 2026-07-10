from __future__ import annotations

from typing import Any

import gradio as gr

from .chat_knowledge_graph_bindings import bind_knowledge_graph_events


def bind_chat_pre_studio_events(
    page: Any,
    *,
    demo_mode: bool,
    on_suggest_chat_event: dict[str, Any],
    pdfview_js: str,
) -> None:
    if not demo_mode:
        _bind_message_selection_events(page, pdfview_js)
    page.chat_control.cb_is_public.change(
        page.on_set_public_conversation,
        inputs=[
            page.chat_control.cb_is_public,
            page.chat_control.conversation,
            page._app.user_id,
        ],
        outputs=None,
        show_progress="hidden",
    )
    if not demo_mode:
        _bind_user_feedback_events(page)
    page.reasoning_type.change(
        page.reasoning_changed,
        inputs=[page.reasoning_type],
        outputs=[page._reasoning_type],
    )
    _bind_chat_suggestion_toggle(page, on_suggest_chat_event)


def bind_chat_post_studio_events(
    page: Any,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
    quick_urls_submit_js: str,
) -> None:
    page.followup_questions.select(
        page.chat_suggestion.select_example,
        outputs=[page.chat_panel.text_input],
        show_progress="hidden",
    ).then(
        fn=None,
        inputs=None,
        outputs=None,
        js=chat_input_focus_js,
    )

    if page.knowledge_graph and len(page._indices_input) > 1:
        bind_knowledge_graph_events(page)

    if demo_mode:
        page.paper_list.examples.select(
            page.paper_list.select_example,
            inputs=[page.paper_list.papers_state],
            outputs=[page.quick_urls],
            show_progress="hidden",
        ).then(
            lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=[page.paper_list.accordion, page.chat_settings],
        ).then(
            fn=None,
            inputs=None,
            outputs=None,
            js=quick_urls_submit_js,
        )


def _bind_message_selection_events(page: Any, pdfview_js: str) -> None:
    page.chat_panel.chatbot.select(
        page.message_selected,
        inputs=[
            page.state_retrieval_history,
            page.state_plot_history,
        ],
        outputs=[
            page.info_panel,
            page.state_plot_panel,
            page.citations_panel,
            page.reasoning_trace_panel,
        ],
    ).then(
        fn=page._json_to_plot,
        inputs=page.state_plot_panel,
        outputs=page.plot_panel,
    ).then(
        fn=lambda: True,
        inputs=None,
        outputs=[page._preview_links],
        js=pdfview_js,
    )


def _bind_user_feedback_events(page: Any) -> None:
    page.chat_panel.chatbot.like(
        fn=page.is_liked,
        inputs=[page.chat_control.conversation_id, page._app.user_id],
        outputs=None,
    )
    page.report_issue.report_btn.click(
        page.report_issue.report,
        inputs=[
            page.report_issue.correctness,
            page.report_issue.issues,
            page.report_issue.more_detail,
            page.chat_control.conversation_id,
            page.chat_panel.chatbot,
            page._app.settings_state,
            page._app.user_id,
            page.info_panel,
            page.state_chat,
        ]
        + page._indices_input,
        outputs=None,
    )


def _bind_chat_suggestion_toggle(
    page: Any,
    on_suggest_chat_event: dict[str, Any],
) -> None:
    page.chat_control.cb_suggest_chat.change(
        fn=_toggle_chat_suggestion,
        inputs=[page.chat_control.cb_suggest_chat],
        outputs=[page._use_suggestion, page.followup_questions_ui],
        show_progress="hidden",
    ).then(
        fn=_raise_error_on_disabled_suggestion,
        inputs=[page._use_suggestion],
        show_progress="hidden",
    ).success(
        **on_suggest_chat_event
    )


def _toggle_chat_suggestion(current_state):
    return current_state, gr.update(visible=current_state)


def _raise_error_on_disabled_suggestion(state):
    if not state:
        raise ValueError("Chat suggestion disabled")
