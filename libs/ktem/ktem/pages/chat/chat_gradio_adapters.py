from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .chat_docqa_runtime import docqa_research_control_inputs


@dataclass(frozen=True)
class EventPorts:
    inputs: Any = None
    outputs: Any = None

    @property
    def gradio_inputs(self) -> Any:
        return list(self.inputs) if isinstance(self.inputs, tuple) else self.inputs

    @property
    def gradio_outputs(self) -> Any:
        return list(self.outputs) if isinstance(self.outputs, tuple) else self.outputs


@dataclass(frozen=True)
class ChatSubmitPorts:
    submit: EventPorts
    runtime: EventPorts
    cache: EventPorts
    clear_selection: EventPorts
    pdf_refresh: EventPorts
    scroll: EventPorts
    suggest_name: EventPorts
    rename: EventPorts
    persist: EventPorts


@dataclass(frozen=True)
class ChatConversationPorts:
    selection: EventPorts
    new_conversation: EventPorts
    delete_conversation: EventPorts
    toggle_delete: EventPorts
    suggestions: EventPorts
    plot: EventPorts
    demo_visibility: EventPorts
    clear_answer: EventPorts
    citations: EventPorts
    reasoning: EventPorts
    last_question: EventPorts
    preview: EventPorts
    context: EventPorts
    clear_selection: EventPorts
    pdf_refresh: EventPorts
    answer: EventPorts
    focus: EventPorts


@dataclass(frozen=True)
class ChatAppLoadPorts:
    api_key: EventPorts
    login_visibility: EventPorts
    suggestions: EventPorts
    focus: EventPorts


def chat_submit_ports(page: Any) -> ChatSubmitPorts:
    return ChatSubmitPorts(
        submit=_submit_ports(page),
        runtime=_runtime_ports(page),
        cache=_cache_ports(page),
        clear_selection=EventPorts(outputs=(page._selected_page_text,)),
        pdf_refresh=EventPorts(outputs=(page._preview_links,)),
        scroll=EventPorts(),
        suggest_name=EventPorts(
            inputs=page._request_chat_history,
            outputs=(page.chat_control.conversation_rn, page._conversation_renamed),
        ),
        rename=_rename_ports(page),
        persist=_persist_ports(page),
    )


def _submit_ports(page: Any) -> EventPorts:
    return EventPorts(
        inputs=(
            page.chat_panel.text_input,
            page.chat_panel.chatbot,
            page._app.user_id,
            page._app.settings_state,
            page.chat_control.conversation_id,
            page.chat_control.conversation_rn,
            page.first_selector_choices,
            page._graph_source_ids,
            page._selected_page_text,
            page._selected_graph_context,
        ),
        outputs=(
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
        ),
    )


def _runtime_ports(page: Any) -> EventPorts:
    fixed_inputs = (
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
    )
    return EventPorts(
        inputs=(*fixed_inputs, *page._indices_input),
        outputs=(
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
        ),
    )


def _cache_ports(page: Any) -> EventPorts:
    return EventPorts(
        inputs=(
            page._page_outputs_cache,
            page._request_page_number,
            page._request_last_question,
            page._request_info_html,
            page._request_answer_html,
            page._request_file_id,
            page._request_chat_history,
        ),
        outputs=(page._page_outputs_cache,),
    )


def _rename_ports(page: Any) -> EventPorts:
    return EventPorts(
        inputs=(
            page.chat_control.conversation_id,
            page.chat_control.conversation_rn,
            page._conversation_renamed,
            page._app.user_id,
        ),
        outputs=(
            page.chat_control.conversation,
            page.chat_control.conversation,
            page.chat_control.conversation_rn,
        ),
    )


def _persist_ports(page: Any) -> EventPorts:
    return EventPorts(
        inputs=(
            page.chat_control.conversation_id,
            page._app.user_id,
            page._request_info_html,
            page.state_plot_panel,
            page.state_retrieval_history,
            page.state_plot_history,
            page._request_chat_history,
            page.state_chat,
            page._graph_source_ids,
            *page._indices_input,
        ),
        outputs=(page.state_retrieval_history, page.state_plot_history),
    )


def chat_conversation_ports(page: Any) -> ChatConversationPorts:
    selection = _conversation_selection_ports(page)
    return ChatConversationPorts(
        selection=selection,
        new_conversation=EventPorts(
            inputs=page._app.user_id,
            outputs=(page.chat_control.conversation_id, page.chat_control.conversation),
        ),
        delete_conversation=EventPorts(
            inputs=(page.chat_control.conversation_id, page._app.user_id),
            outputs=(page.chat_control.conversation_id, page.chat_control.conversation),
        ),
        toggle_delete=EventPorts(
            inputs=(page.chat_control.conversation_id,),
            outputs=(page.chat_control._new_delete, page.chat_control._delete_confirm),
        ),
        suggestions=_suggestion_ports(page),
        plot=EventPorts(inputs=page.state_plot_panel, outputs=page.plot_panel),
        demo_visibility=EventPorts(
            outputs=(page.paper_list.accordion, page.chat_settings)
        ),
        clear_answer=EventPorts(outputs=(page.answer_panel,)),
        citations=EventPorts(
            inputs=(page.state_retrieval_history,), outputs=(page.citations_panel,)
        ),
        reasoning=EventPorts(
            inputs=(page.chat_panel.chatbot, page.state_retrieval_history),
            outputs=(page.reasoning_trace_panel,),
        ),
        last_question=EventPorts(outputs=(page._last_question,)),
        preview=_conversation_preview_ports(page),
        context=_page_context_ports(page),
        clear_selection=EventPorts(outputs=(page._selected_page_text,)),
        pdf_refresh=EventPorts(outputs=(page._preview_links,)),
        answer=EventPorts(
            inputs=(page.chat_panel.chatbot,), outputs=(page.answer_panel,)
        ),
        focus=EventPorts(),
    )


def conversation_rename_ports(page: Any, confirmed_state: Any) -> EventPorts:
    return EventPorts(
        inputs=(
            page.chat_control.conversation_id,
            page.chat_control.conversation_rn,
            confirmed_state,
            page._app.user_id,
        ),
        outputs=(
            page.chat_control.conversation,
            page.chat_control.conversation,
            page.chat_control.conversation_rn,
        ),
    )


def chat_app_load_ports(page: Any) -> ChatAppLoadPorts:
    return ChatAppLoadPorts(
        api_key=EventPorts(inputs=(page._user_api_key,), outputs=(page._user_api_key,)),
        login_visibility=EventPorts(
            inputs=(page._user_api_key,),
            outputs=(
                page.chat_control.cb_suggest_chat,
                page.chat_control.btn_new,
                page.chat_control.btn_demo_logout,
                page.chat_control.btn_demo_login,
            ),
        ),
        suggestions=_suggestion_ports(page),
        focus=EventPorts(),
    )


def _conversation_selection_ports(page: Any) -> EventPorts:
    return EventPorts(
        inputs=(page.chat_control.conversation, page._app.user_id),
        outputs=(
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
            *page._indices_input,
        ),
    )


def _suggestion_ports(page: Any) -> EventPorts:
    return EventPorts(
        inputs=(
            page._app.settings_state,
            page.language,
            page.chat_panel.chatbot,
            page._use_suggestion,
        ),
        outputs=(page.followup_questions_ui, page.followup_questions),
    )


def _conversation_preview_ports(page: Any) -> EventPorts:
    return EventPorts(
        inputs=(
            page.first_selector_choices,
            page._indices_input[1],
            page.chat_panel.page_number,
            page._active_file_total_pages,
        ),
        outputs=(
            page._active_file_id,
            page._active_file_name,
            page._active_file_path,
            page.chat_panel.page_number,
            page._active_file_total_pages,
            page.chat_panel.pdf_preview_src,
            page.chat_panel.pdf_preview_notice,
        ),
    )


def _page_context_ports(page: Any) -> EventPorts:
    return EventPorts(
        inputs=(
            page._active_file_id,
            page._active_file_name,
            page._active_file_path,
            page.chat_panel.page_number,
            page._active_file_total_pages,
            page.page_strip_search,
        ),
        outputs=(
            page.page_strip_file_summary,
            page.page_thumbnail_strip,
            page.page_metadata_strip,
        ),
    )
