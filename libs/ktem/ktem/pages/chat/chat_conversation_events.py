from __future__ import annotations

from typing import Any

import gradio as gr

from .chat_gradio_adapters import (
    ChatConversationPorts,
    chat_conversation_ports,
    conversation_rename_ports,
)


def bind_chat_conversation_events(
    page: Any,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
    clear_bot_message_selection_js: str,
    pdfview_js: str,
) -> None:
    ports = chat_conversation_ports(page, demo_mode=demo_mode)
    page.chat_control.btn_chat_expand.click(
        fn=None, inputs=None, js="function() {toggleChatColumn();}"
    )
    if demo_mode:
        _bind_demo_conversation_events(page, ports, chat_input_focus_js)
    else:
        _bind_standard_conversation_events(page, ports, chat_input_focus_js)
        _bind_delete_conversation_events(page, ports)
    _bind_conversation_select_event(
        page,
        ports,
        demo_mode=demo_mode,
        chat_input_focus_js=chat_input_focus_js,
        clear_bot_message_selection_js=clear_bot_message_selection_js,
        pdfview_js=pdfview_js,
    )


def _bind_demo_conversation_events(
    page: Any, ports: ChatConversationPorts, chat_input_focus_js: str
) -> None:
    page.chat_control.btn_demo_logout.click(fn=None, js=page.chat_control.logout_js)
    page.chat_control.btn_new.click(
        fn=page.chat_control.clear_conv,
        outputs=ports.selection.gradio_outputs,
    ).then(
        lambda: (gr.update(visible=False), gr.update(visible=True)),
        outputs=ports.demo_visibility.gradio_outputs,
    ).then(
        fn=lambda: "",
        outputs=ports.clear_answer.gradio_outputs,
    ).then(
        fn=page.render_latest_citations_card,
        inputs=ports.citations.gradio_inputs,
        outputs=ports.citations.gradio_outputs,
    ).then(
        fn=page.render_latest_reasoning_trace,
        inputs=ports.reasoning.gradio_inputs,
        outputs=ports.reasoning.gradio_outputs,
    ).then(
        fn=lambda: "",
        outputs=ports.last_question.gradio_outputs,
    ).then(
        fn=page.suggest_chat_conv,
        inputs=ports.suggestions.gradio_inputs,
        outputs=ports.suggestions.gradio_outputs,
    ).then(
        fn=None, inputs=None, js=chat_input_focus_js
    )


def _bind_standard_conversation_events(
    page: Any, ports: ChatConversationPorts, chat_input_focus_js: str
) -> None:
    page.chat_control.btn_new.click(
        page.chat_control.new_conv,
        inputs=ports.new_conversation.gradio_inputs,
        outputs=ports.new_conversation.gradio_outputs,
        show_progress="hidden",
    ).then(
        page.chat_control.select_conv,
        inputs=ports.selection.gradio_inputs,
        outputs=ports.selection.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=page._json_to_plot,
        inputs=ports.plot.gradio_inputs,
        outputs=ports.plot.gradio_outputs,
    ).then(
        fn=lambda: "",
        outputs=ports.clear_answer.gradio_outputs,
    ).then(
        fn=page.render_latest_citations_card,
        inputs=ports.citations.gradio_inputs,
        outputs=ports.citations.gradio_outputs,
    ).then(
        fn=page.render_latest_reasoning_trace,
        inputs=ports.reasoning.gradio_inputs,
        outputs=ports.reasoning.gradio_outputs,
    ).then(
        fn=lambda: "",
        outputs=ports.last_question.gradio_outputs,
    ).then(
        fn=page.suggest_chat_conv,
        inputs=ports.suggestions.gradio_inputs,
        outputs=ports.suggestions.gradio_outputs,
    ).then(
        fn=None, inputs=None, js=chat_input_focus_js
    )


def _bind_delete_conversation_events(page: Any, ports: ChatConversationPorts) -> None:
    page.chat_control.btn_del.click(
        lambda conv_id: page.toggle_delete(conv_id),
        inputs=ports.toggle_delete.gradio_inputs,
        outputs=ports.toggle_delete.gradio_outputs,
    )
    page.chat_control.btn_del_conf.click(
        page.chat_control.delete_conv,
        inputs=ports.delete_conversation.gradio_inputs,
        outputs=ports.delete_conversation.gradio_outputs,
        show_progress="hidden",
    ).then(
        page.chat_control.select_conv,
        inputs=ports.selection.gradio_inputs,
        outputs=ports.selection.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=page._json_to_plot,
        inputs=ports.plot.gradio_inputs,
        outputs=ports.plot.gradio_outputs,
    ).then(
        fn=page.render_latest_citations_card,
        inputs=ports.citations.gradio_inputs,
        outputs=ports.citations.gradio_outputs,
    ).then(
        fn=page.render_latest_reasoning_trace,
        inputs=ports.reasoning.gradio_inputs,
        outputs=ports.reasoning.gradio_outputs,
    ).then(
        lambda: page.toggle_delete(""),
        outputs=ports.toggle_delete.gradio_outputs,
    )
    page.chat_control.btn_del_cnl.click(
        lambda: page.toggle_delete(""),
        outputs=ports.toggle_delete.gradio_outputs,
    )
    page.chat_control.btn_conversation_rn.click(
        lambda: gr.update(visible=True),
        outputs=[page.chat_control.conversation_rn],
    )
    rename_ports = conversation_rename_ports(page, gr.State(value=True))
    page.chat_control.conversation_rn.submit(
        page.chat_control.rename_conv,
        inputs=rename_ports.gradio_inputs,
        outputs=rename_ports.gradio_outputs,
        show_progress="hidden",
    )


def _bind_conversation_select_event(
    page: Any,
    ports: ChatConversationPorts,
    *,
    demo_mode: bool,
    chat_input_focus_js: str,
    clear_bot_message_selection_js: str,
    pdfview_js: str,
) -> None:
    on_conv_select = (
        page.chat_control.conversation.select(
            page.chat_control.select_conv,
            inputs=ports.selection.gradio_inputs,
            outputs=ports.selection.gradio_outputs,
            show_progress="hidden",
        )
        .then(
            fn=page._json_to_plot,
            inputs=ports.plot.gradio_inputs,
            outputs=ports.plot.gradio_outputs,
        )
        .then(
            lambda: page.toggle_delete(""),
            outputs=ports.toggle_delete.gradio_outputs,
        )
        .then(
            fn=page.suggest_chat_conv,
            inputs=ports.suggestions.gradio_inputs,
            outputs=ports.suggestions.gradio_outputs,
        )
    )

    if demo_mode:
        on_conv_select = on_conv_select.then(
            lambda: (gr.update(visible=False), gr.update(visible=True)),
            outputs=ports.demo_visibility.gradio_outputs,
        )

    _append_conversation_preview_refresh(
        page,
        ports,
        on_conv_select,
        chat_input_focus_js=chat_input_focus_js,
        clear_bot_message_selection_js=clear_bot_message_selection_js,
        pdfview_js=pdfview_js,
    )


def _append_conversation_preview_refresh(
    page: Any,
    ports: ChatConversationPorts,
    event_chain: Any,
    *,
    chat_input_focus_js: str,
    clear_bot_message_selection_js: str,
    pdfview_js: str,
) -> None:
    event_chain.then(
        fn=page.page_preview.refresh_selected_file_preview,
        inputs=ports.preview.gradio_inputs,
        outputs=ports.preview.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=page.refresh_page_context_view,
        inputs=ports.context.gradio_inputs,
        outputs=ports.context.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=lambda: True,
        js=clear_bot_message_selection_js,
    ).then(
        fn=lambda: "",
        outputs=ports.clear_selection.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=lambda: True,
        inputs=None,
        outputs=ports.pdf_refresh.gradio_outputs,
        js=pdfview_js,
    ).then(
        fn=lambda history: history[-1][1] if history else "",
        inputs=ports.answer.gradio_inputs,
        outputs=ports.answer.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=lambda history: history[-1][0] if history else "",
        inputs=ports.answer.gradio_inputs,
        outputs=ports.last_question.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=page.render_latest_citations_card,
        inputs=ports.citations.gradio_inputs,
        outputs=ports.citations.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=page.render_latest_reasoning_trace,
        inputs=ports.reasoning.gradio_inputs,
        outputs=ports.reasoning.gradio_outputs,
        show_progress="hidden",
    ).then(
        fn=None, inputs=None, outputs=None, js=chat_input_focus_js
    )
