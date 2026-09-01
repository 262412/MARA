from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterator

from kotaemon.base import Document

from . import _runtime_mara as _mara
from ._runtime_models import DocQARequest, _PreparedPipeline
from ._runtime_utils import _serialize_value
from .evidence_text import extract_final_answer_text
from .terminal_session_state import (
    state_with_stream_terminal_commit as _state_with_stream_terminal_commit,
)


@dataclass
class TurnStreamResult:
    text: str
    refs: str
    plot: Any
    mindmap_html: str
    stream_events: list[dict[str, Any]]
    state: dict[str, Any]
    capture: _mara.ResponseCapture
    preserve_text_after_chat_clear: bool = False


def state_with_stream_terminal_commit(
    stream_result: TurnStreamResult,
    message_index: int,
) -> dict[str, Any]:
    return _state_with_stream_terminal_commit(stream_result, message_index)


def build_turn_request(
    request: DocQARequest,
    session_info: Any,
    *,
    resolved_user_id: Any,
    selected_inputs: dict[int, Any],
    request_file_ids: list[str] | None,
    load_settings: Any,
) -> DocQARequest:
    request_to_run = DocQARequest(
        prompt=request.prompt,
        conversation_id=session_info.conversation_id,
        selected_file_ids=request_file_ids,
        selected_inputs=selected_inputs,
        active_file_id=request.active_file_id,
        active_file_name=request.active_file_name,
        qa_scope=request.qa_scope,
        page_number=request.page_number,
        selected_text=request.selected_text,
        selected_source_title=request.selected_source_title,
        graph_context=deepcopy(request.graph_context),
        graph_source_ids=deepcopy(request.graph_source_ids),
        settings=deepcopy(request.settings or load_settings(resolved_user_id)),
        state=deepcopy(request.state or session_info.state),
        history=list(request.history or session_info.messages),
        max_context_length=request.max_context_length,
        reasoning_type=request.reasoning_type,
        llm=request.llm,
        use_mindmap=request.use_mindmap,
        use_citation=request.use_citation,
        language=request.language,
        command_state=request.command_state,
        user_id=resolved_user_id,
        origin=request.origin,
    )
    _mara.copy_request_fields(request_to_run, request)
    return request_to_run


def collect_stream_result(
    prepared: _PreparedPipeline,
    request: DocQARequest,
    *,
    conversation_id: str,
    history: list,
    empty_message: str,
) -> TurnStreamResult:
    result = create_stream_result(request)
    for _event in consume_stream_result(
        prepared,
        request,
        conversation_id=conversation_id,
        history=history,
        result=result,
    ):
        pass
    finalize_stream_result(result, empty_message)
    return result


def create_stream_result(request: DocQARequest) -> TurnStreamResult:
    state = request.state or {"app": {"regen": False}}
    request.state = state
    capture = _mara.ResponseCapture(request)
    return TurnStreamResult(
        text="",
        refs="",
        plot=None,
        mindmap_html="",
        stream_events=[],
        state=state,
        capture=capture,
    )


def consume_stream_result(
    prepared: _PreparedPipeline,
    request: DocQARequest,
    *,
    conversation_id: str,
    history: list,
    result: TurnStreamResult,
) -> Iterator[dict[str, Any]]:
    generation_kwargs = _generation_kwargs_for_request(request)
    stream = iter(
        prepared.pipeline.stream(
            request.prompt,
            conversation_id,
            history,
            **generation_kwargs,
        )
    )
    while True:
        try:
            response = next(stream)
        except StopIteration as stop:
            response = stop.value
            if response is not None:
                yield from _ingest_response_event(response, prepared, result)
            break
        yield from _ingest_response_event(response, prepared, result)


def _generation_kwargs_for_request(request: DocQARequest) -> dict[str, Any]:
    values = {
        "temperature": request.generation_temperature,
        "top_p": request.generation_top_p,
        "seed": request.generation_seed,
    }
    return {key: value for key, value in values.items() if value is not None}


def _ingest_response_event(
    response: Any,
    prepared: _PreparedPipeline,
    result: TurnStreamResult,
) -> Iterator[dict[str, Any]]:
    previous_event_count = len(result.stream_events)
    _ingest_stream_response(response, prepared, result)
    if len(result.stream_events) > previous_event_count:
        yield result.stream_events[-1]


def finalize_stream_result(result: TurnStreamResult, empty_message: str) -> None:
    answer = result.text
    execution = result.capture.execution
    if isinstance(execution, dict):
        terminal_answer = str(execution.get("engine_terminal_answer") or "").strip()
        if terminal_answer:
            answer = terminal_answer
        terminal_commit = execution.get("engine_terminal_commit") or execution.get(
            "terminal_semantic_commit"
        )
        if (
            isinstance(terminal_commit, dict)
            and terminal_commit.get("answer_status") == "abstained"
        ):
            presentation_answer = str(execution.get("answer") or "").strip()
            if presentation_answer:
                answer = presentation_answer
    result.text = extract_final_answer_text(_hide_unclosed_think_block(answer))
    if not result.text:
        result.text = empty_message


def partial_answer_text(answer: str) -> str:
    return extract_final_answer_text(_hide_unclosed_think_block(answer)).strip()


def graph_source_ids_for_turn(
    requested_graph_source_ids: Any,
    selected_file_ids: list[str],
    existing_graph_source_ids: list[str],
    normalize_selected_file_ids: Any,
) -> list[str]:
    graph_source_ids = normalize_selected_file_ids(requested_graph_source_ids)
    if graph_source_ids:
        return graph_source_ids
    return (
        list(selected_file_ids)
        if selected_file_ids
        else list(existing_graph_source_ids)
    )


def _ingest_stream_response(
    response: Any,
    prepared: _PreparedPipeline,
    result: TurnStreamResult,
) -> None:
    if not isinstance(response, Document) or response.channel is None:
        return
    event = {
        "channel": response.channel,
        "content": _serialize_value(response.content),
    }
    result.stream_events.append(event)
    result.capture.ingest(response.channel, event["content"])
    _collect_channel_content(response, result)
    _update_pipeline_state(prepared, result.state)


def _collect_channel_content(response: Document, result: TurnStreamResult) -> None:
    if response.channel == "chat":
        if response.content is None:
            if _has_substantial_visible_answer(result.text):
                result.preserve_text_after_chat_clear = True
            else:
                result.text = ""
                result.preserve_text_after_chat_clear = False
            return
        if not result.preserve_text_after_chat_clear:
            result.text += str(response.content)
    elif response.channel == "info":
        content = "" if response.content is None else str(response.content)
        result.refs = "" if response.content is None else result.refs + content
        if "markmap" in content:
            result.mindmap_html += content
    elif response.channel == "plot":
        result.plot = response.content


def _update_pipeline_state(prepared: _PreparedPipeline, state: dict[str, Any]) -> None:
    pipeline_id = str(prepared.pipeline.get_info()["id"])
    state.setdefault(pipeline_id, {})
    state[pipeline_id] = prepared.reasoning_state["pipeline"]


def _has_substantial_visible_answer(answer: str) -> bool:
    cleaned = extract_final_answer_text(_hide_unclosed_think_block(answer)).strip()
    return len(cleaned) >= 160


def _hide_unclosed_think_block(answer: str) -> str:
    text = str(answer or "")
    lowered = text.lower()
    last_open = lowered.rfind("<think")
    last_close = lowered.rfind("</think>")
    if last_open > last_close:
        return text[:last_open]
    return text
