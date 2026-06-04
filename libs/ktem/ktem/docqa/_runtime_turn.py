from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from kotaemon.base import Document

from . import _runtime_mara as _mara
from ._runtime_models import DocQARequest, _PreparedPipeline
from ._runtime_utils import _serialize_value


@dataclass
class TurnStreamResult:
    text: str
    refs: str
    plot: Any
    mindmap_html: str
    stream_events: list[dict[str, Any]]
    state: dict[str, Any]
    capture: _mara.ResponseCapture


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
        graph_context=deepcopy(request.graph_context),
        graph_source_ids=deepcopy(request.graph_source_ids),
        settings=deepcopy(request.settings or load_settings(resolved_user_id)),
        state=deepcopy(request.state or session_info.state),
        history=list(request.history or session_info.messages),
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
    state = request.state or {"app": {"regen": False}}
    request.state = state
    capture = _mara.ResponseCapture(request)
    result = TurnStreamResult(
        text="",
        refs="",
        plot=None,
        mindmap_html="",
        stream_events=[],
        state=state,
        capture=capture,
    )

    for response in prepared.pipeline.stream(request.prompt, conversation_id, history):
        _ingest_stream_response(response, prepared, result)

    if not result.text:
        result.text = empty_message
    return result


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
        result.text = (
            "" if response.content is None else result.text + str(response.content)
        )
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
