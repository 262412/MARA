from __future__ import annotations

import math
from types import SimpleNamespace
from typing import Any

import gradio as gr

from .answer_reasoning import render_answer_reasoning_block
from .chat_docqa_runtime import build_web_docqa_request, runtime_trace_references
from .generation_store import update_answer, update_mindmap, update_plot

_MAX_TYPEWRITER_FRAMES = 128


def build_chat_runtime_request(
    page: Any,
    *,
    chat_input: Any,
    conversation_id: str,
    preserved_history: list,
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
    selected_page_text: str,
    selected_graph_context: str,
    controller_mode: str,
    route_policy: str,
    verification_mode: str,
    planner_model: str,
):
    return build_web_docqa_request(
        prompt=str(chat_input or ""),
        conversation_id=conversation_id,
        history=preserved_history,
        selected_inputs=page._build_selected_input_map(*selecteds),
        settings=settings,
        reasoning_type=reasoning_type,
        llm=llm_type,
        use_mindmap=use_mind_map,
        use_citation=use_citation,
        language=language,
        state=chat_state,
        command_state=command_state,
        user_id=user_id,
        active_file_id=active_file_id,
        active_file_name=active_file_name,
        page_number=page_number,
        qa_scope=qa_scope,
        selected_text=selected_page_text,
        selected_graph_context=selected_graph_context,
        controller_mode=controller_mode,
        route_policy=route_policy,
        verification_mode=verification_mode,
        planner_model=planner_model,
    )


def run_docqa_turn_with_live_updates(
    page: Any,
    *,
    runtime_request: Any,
    preserved_history: list,
    chat_input: Any,
    msg_placeholder: str,
    request_key: str,
    fallback_plot: Any,
    fallback_chat_state: dict,
    is_active_view: Any,
    active_file_id: str,
    normalized_page_number: int,
    artifact_payload: Any,
):
    stream_turn = getattr(page.docqa, "stream_turn", None)
    if not callable(stream_turn):
        return page.docqa.run_turn(runtime_request)

    response = None
    displayed_answer = ""
    for turn_update in stream_turn(runtime_request):
        if turn_update.is_final:
            response = turn_update.response
            continue
        for display_answer in _typewriter_answer_frames(
            displayed_answer,
            turn_update.answer,
        ):
            displayed_answer = display_answer
            yield live_docqa_update_output(
                page,
                turn_update=_with_answer(turn_update, display_answer),
                preserved_history=preserved_history,
                chat_input=chat_input,
                msg_placeholder=msg_placeholder,
                request_key=request_key,
                fallback_plot=fallback_plot,
                fallback_chat_state=fallback_chat_state,
                active_view=is_active_view(),
                active_file_id=active_file_id or "",
                normalized_page_number=normalized_page_number,
                artifact_payload=artifact_payload,
            )
    if response is None:
        raise ValueError("DocQA stream did not return a final response")
    return _with_displayed_final_answer(
        response,
        displayed_answer,
        preserved_history=preserved_history,
        chat_input=chat_input,
    )


def live_docqa_update_output(
    page: Any,
    *,
    turn_update: Any,
    preserved_history: list,
    chat_input: Any,
    msg_placeholder: str,
    request_key: str,
    fallback_plot: Any,
    fallback_chat_state: dict,
    active_view: bool,
    active_file_id: str,
    normalized_page_number: int,
    artifact_payload: Any,
):
    text = turn_update.answer
    refs = turn_update.references_html
    mindmap_html = turn_update.mindmap_html
    plot = turn_update.plot if turn_update.plot is not None else fallback_plot
    plot_gr = page._json_to_plot(plot)
    chat_state = turn_update.state or fallback_chat_state
    chat_history_full = preserved_history + [(chat_input, text or msg_placeholder)]
    reasoning_html = render_answer_reasoning_block(
        is_streaming=True,
        stream_events=turn_update.stream_events,
    )
    answer_html = page._generate_answer_panel_html(
        preserved_history,
        chat_input,
        text,
        is_thinking=True,
        reasoning_html=reasoning_html,
    )
    update_answer(
        request_key,
        answer_text=text,
        answer_html=answer_html,
        chat_history=chat_history_full,
    )
    update_mindmap(request_key, mindmap_html)
    update_plot(request_key, plot)
    return (
        chat_history_full if active_view else gr.skip(),
        mindmap_html if active_view else gr.skip(),
        plot_gr if active_view else gr.skip(),
        plot,
        chat_state,
        answer_html if active_view else gr.skip(),
        page._render_citations_card_html(refs) if active_view else gr.skip(),
        (
            page._render_reasoning_trace_html(
                chat_input,
                refs,
                answer_html,
                active_file_id or "",
                normalized_page_number,
                artifact_payload,
            )
            if active_view
            else gr.skip()
        ),
        normalized_page_number,
        active_file_id or "",
        str(chat_input or ""),
        mindmap_html,
        answer_html,
        chat_history_full,
    )


def _typewriter_answer_frames(previous_answer: str, current_answer: str):
    previous = str(previous_answer or "")
    current = str(current_answer or "")
    if current == previous:
        yield current
        return
    if not current.startswith(previous):
        yield current
        return

    delta = current[len(previous) :]
    step = max(1, math.ceil(len(delta) / _MAX_TYPEWRITER_FRAMES))
    emitted = previous
    for index in range(step, len(delta) + 1, step):
        emitted = previous + delta[:index]
        yield emitted
    if emitted != current:
        yield current


def _with_answer(turn_update: Any, answer: str) -> Any:
    return SimpleNamespace(
        event=turn_update.event,
        answer=answer,
        references_html=turn_update.references_html,
        mindmap_html=turn_update.mindmap_html,
        plot=turn_update.plot,
        state=turn_update.state,
        stream_events=turn_update.stream_events,
        response=turn_update.response,
        is_final=turn_update.is_final,
    )


def _with_displayed_final_answer(
    response: Any,
    displayed_answer: str,
    *,
    preserved_history: list,
    chat_input: Any,
) -> Any:
    if not displayed_answer:
        return response

    response.answer = displayed_answer
    response.messages = list(preserved_history) + [(chat_input, displayed_answer)]
    return response


def final_docqa_response_output(
    page: Any,
    *,
    response: Any,
    preserved_history: list,
    chat_input: Any,
    msg_placeholder: str,
    request_key: str,
    state_plot_panel: Any,
    fallback_chat_state: dict,
    active_view: bool,
    active_file_id: str,
    normalized_page_number: int,
):
    text = response.answer or ""
    refs = response.references_html or ""
    trace_refs = runtime_trace_references(response, refs)
    mindmap_html = response.mindmap_html or ""
    plot = response.plot if response.plot is not None else state_plot_panel
    plot_gr = page._json_to_plot(plot)
    artifact_payload = response.artifact
    chat_state = response.state or fallback_chat_state
    chat_history_full = response.messages or preserved_history + [
        (chat_input, text or msg_placeholder)
    ]
    reasoning_html = render_answer_reasoning_block(
        route_decision=response.route_decision,
        retrieve_decision=response.retrieve_decision,
        verify_decision=response.verify_decision,
        evidence_bundle=response.evidence_bundle,
        stream_events=response.stream_events,
    )
    answer_html = page._generate_answer_panel_html(
        preserved_history,
        chat_input,
        text,
        is_thinking=False,
        reasoning_html=reasoning_html,
    )
    update_answer(
        request_key,
        answer_text=text,
        answer_html=answer_html,
        chat_history=chat_history_full,
    )
    update_mindmap(request_key, mindmap_html)
    update_plot(request_key, plot)
    trace_html = page._render_reasoning_trace_html(
        chat_input,
        trace_refs,
        answer_html,
        response.active_file_id or active_file_id or "",
        response.page_number or normalized_page_number,
        artifact_payload,
    )
    return (
        chat_history_full if active_view else gr.skip(),
        mindmap_html if active_view else gr.skip(),
        plot_gr if active_view else gr.skip(),
        plot,
        chat_state,
        answer_html if active_view else gr.skip(),
        page._render_citations_card_html(refs) if active_view else gr.skip(),
        trace_html if active_view else gr.skip(),
        response.page_number or normalized_page_number,
        response.active_file_id or active_file_id or "",
        str(chat_input or ""),
        mindmap_html,
        answer_html,
        chat_history_full,
    )
