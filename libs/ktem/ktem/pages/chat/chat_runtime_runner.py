from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from theflow.settings import settings as flowsettings

from .chat_docqa_streaming import (
    ChatRuntimeTurn,
    build_chat_runtime_request,
    final_docqa_response_output,
    initial_docqa_response_output,
    prepare_chat_runtime_turn,
    run_docqa_turn_with_live_updates,
    value_error_docqa_response_output,
)
from .generation_store import mark_done


@dataclass(frozen=True)
class ChatCallbackInputs:
    conversation_id: str
    chat_history: list
    settings: dict
    reasoning_type: str
    llm_type: str
    use_mind_map: Any
    use_citation: Any
    language: str
    chat_state: dict
    command_state: Any
    user_id: Any
    active_file_id: str
    active_file_name: str
    page_number: int
    qa_scope: str
    selected_page_text: str
    selected_graph_context: str
    controller_mode: str
    route_policy: str
    verification_mode: str
    planner_model: str
    state_plot_panel: Any
    selecteds: tuple


def run_chat_callback_outputs(
    page: Any,
    inputs: ChatCallbackInputs,
    request: Any,
):
    runtime_turn = prepare_chat_runtime_turn(
        chat_history=inputs.chat_history,
        selected_page_text=inputs.selected_page_text,
        active_file_id=inputs.active_file_id or "",
        page_number=inputs.page_number,
        request=request,
    )
    msg_placeholder = getattr(flowsettings, "KH_CHAT_MSG_PLACEHOLDER", "Thinking ...")
    yield initial_docqa_response_output(
        page,
        runtime_turn=runtime_turn,
        state_plot_panel=inputs.state_plot_panel,
        chat_state=inputs.chat_state,
        msg_placeholder=msg_placeholder,
        active_file_id=inputs.active_file_id or "",
    )

    try:
        yield from run_chat_runtime_outputs(
            page,
            runtime_turn=runtime_turn,
            conversation_id=inputs.conversation_id,
            selecteds=inputs.selecteds,
            settings=inputs.settings,
            reasoning_type=inputs.reasoning_type,
            llm_type=inputs.llm_type,
            use_mind_map=inputs.use_mind_map,
            use_citation=inputs.use_citation,
            language=inputs.language,
            chat_state=inputs.chat_state,
            command_state=inputs.command_state,
            user_id=inputs.user_id,
            active_file_id=inputs.active_file_id,
            active_file_name=inputs.active_file_name,
            page_number=inputs.page_number,
            qa_scope=inputs.qa_scope,
            selected_graph_context=inputs.selected_graph_context,
            controller_mode=inputs.controller_mode,
            route_policy=inputs.route_policy,
            verification_mode=inputs.verification_mode,
            planner_model=inputs.planner_model,
            state_plot_panel=inputs.state_plot_panel,
            msg_placeholder=msg_placeholder,
        )
    except ValueError as error:
        yield value_error_docqa_response_output(
            page,
            error=error,
            runtime_turn=runtime_turn,
            state_plot_panel=inputs.state_plot_panel,
            chat_state=inputs.chat_state,
            active_file_id=inputs.active_file_id or "",
        )

    mark_done(runtime_turn.request_key)


def run_chat_runtime_outputs(
    page: Any,
    *,
    runtime_turn: ChatRuntimeTurn,
    conversation_id: str,
    selecteds: tuple,
    settings: dict,
    reasoning_type: str,
    llm_type: str,
    use_mind_map: Any,
    use_citation: Any,
    language: str,
    chat_state: dict,
    command_state: Any,
    user_id: Any,
    active_file_id: str,
    active_file_name: str,
    page_number: int,
    qa_scope: str,
    selected_graph_context: str,
    controller_mode: str,
    route_policy: str,
    verification_mode: str,
    planner_model: str,
    state_plot_panel: Any,
    msg_placeholder: str,
):
    runtime_request = build_chat_runtime_request(
        page,
        chat_input=runtime_turn.chat_input,
        conversation_id=conversation_id,
        preserved_history=runtime_turn.preserved_history,
        selecteds=selecteds,
        settings=settings,
        reasoning_type=reasoning_type,
        llm_type=llm_type,
        use_mind_map=use_mind_map,
        use_citation=use_citation,
        language=language,
        chat_state=chat_state,
        command_state=command_state,
        user_id=user_id,
        active_file_id=active_file_id,
        active_file_name=active_file_name,
        page_number=page_number,
        qa_scope=qa_scope,
        selected_page_text=runtime_turn.selected_page_text,
        selected_graph_context=selected_graph_context,
        controller_mode=controller_mode,
        route_policy=route_policy,
        verification_mode=verification_mode,
        planner_model=planner_model,
    )
    response = yield from run_docqa_turn_with_live_updates(
        page,
        runtime_request=runtime_request,
        preserved_history=runtime_turn.preserved_history,
        chat_input=runtime_turn.chat_input,
        msg_placeholder=msg_placeholder,
        request_key=runtime_turn.request_key,
        fallback_plot=state_plot_panel,
        fallback_chat_state=chat_state,
        is_active_view=runtime_turn.is_active_view,
        active_file_id=active_file_id or "",
        normalized_page_number=runtime_turn.normalized_page_number,
        artifact_payload=None,
    )
    yield final_docqa_response_output(
        page,
        response=response,
        preserved_history=runtime_turn.preserved_history,
        chat_input=runtime_turn.chat_input,
        msg_placeholder=msg_placeholder,
        request_key=runtime_turn.request_key,
        state_plot_panel=state_plot_panel,
        fallback_chat_state=chat_state,
        active_view=runtime_turn.is_active_view(),
        active_file_id=active_file_id or "",
        normalized_page_number=runtime_turn.normalized_page_number,
    )
