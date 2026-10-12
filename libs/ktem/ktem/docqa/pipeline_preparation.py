"""Prepare one reasoning pipeline through explicit runtime capabilities."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from . import _runtime_preview
from ._runtime_models import DocQARequest, _PreparedPipeline


@dataclass(frozen=True)
class PipelinePreparationDependencies:
    """Resolve resources at their use sites, preserving runtime overrides."""

    resolve_user_id: Callable[[Any], Any]
    load_settings: Callable[[Any], dict[str, Any]]
    get_reasonings: Callable[[], Mapping[str, Any]]
    get_indices: Callable[[], Iterable[Any]]
    get_web_search_class: Callable[[], Any]
    get_file_index: Callable[[], Any]
    get_preview: Callable[[], Any]
    normalize_page_number: Callable[[Any], int | None]
    normalize_qa_scope: Callable[[Any, Any], str]
    normalize_selected_file_ids: Callable[[Any], list[str]]
    selected_file_records: Callable[[list[str], str, Any], list[dict[str, Any]]]
    apply_setting_overrides: Callable[[dict[str, Any], str, DocQARequest], None]
    build_reasoning_state: Callable[[dict[str, Any], str], dict[str, Any]]
    apply_page_image_records: Callable[[Any, DocQARequest], None]
    apply_multimodal_indexes: Callable[
        [Any, Any, list[str], str, list[str], dict[str, Any]], dict[str, Any]
    ]
    apply_element_records: Callable[[Any, DocQARequest], None]
    apply_request_context: Callable[[Any, DocQARequest, dict[str, Any]], None]


def prepare_pipeline(
    request: DocQARequest,
    *,
    dependencies: PipelinePreparationDependencies,
    default_state: dict[str, Any],
    web_search_command: str,
) -> _PreparedPipeline:
    resolved_user_id = dependencies.resolve_user_id(request.user_id)
    settings = deepcopy(
        request.settings or dependencies.load_settings(resolved_user_id)
    )
    state = deepcopy(request.state or default_state)
    selected_inputs = dict(request.selected_inputs or {})
    pipeline, reasoning_state, reasoning_id = _create_reasoning_pipeline(
        request,
        dependencies,
        settings,
        state,
        selected_inputs,
        resolved_user_id,
        web_search_command,
    )
    (
        selected_file_ids,
        active_file_id,
        active_file_name,
        qa_scope,
        scoped_page_number,
        selected_text,
        graph_context,
    ) = _prepare_file_context(
        pipeline,
        request,
        dependencies,
        selected_inputs,
        resolved_user_id,
    )
    graph_context = _prepare_multimodal_context(
        pipeline,
        request,
        dependencies,
        resolved_user_id,
        selected_file_ids,
        active_file_id,
        graph_context,
    )
    return _PreparedPipeline(
        pipeline=pipeline,
        reasoning_state=reasoning_state,
        selected_file_ids=selected_file_ids,
        active_file_id=active_file_id or "",
        active_file_name=active_file_name,
        qa_scope=qa_scope,
        page_number=scoped_page_number,
        selected_text=selected_text,
        graph_context=graph_context,
        settings=settings,
        reasoning_id=reasoning_id,
    )


def _create_reasoning_pipeline(
    request,
    dependencies,
    settings,
    state,
    selected_inputs,
    user_id,
    web_search_command,
):
    if request.reasoning_type in ("(default)", None):
        reasoning_mode = settings["reasoning.use"]
    else:
        reasoning_mode = request.reasoning_type
    if reasoning_mode not in dependencies.get_reasonings():
        raise ValueError(f"Unknown reasoning pipeline '{reasoning_mode}'.")
    reasoning_cls = dependencies.get_reasonings()[reasoning_mode]
    reasoning_id = reasoning_cls.get_info()["id"]
    dependencies.apply_setting_overrides(settings, reasoning_id, request)

    retrievers = []
    if request.command_state == web_search_command:
        if not dependencies.get_web_search_class():
            raise ValueError("Web search back-end is not available.")
        retrievers.append(dependencies.get_web_search_class()())
    else:
        for index in dependencies.get_indices():
            selected_input = selected_inputs.get(index.id)
            retrievers.extend(
                index.get_retriever_pipelines(settings, user_id, selected_input)
            )
    reasoning_state = dependencies.build_reasoning_state(state, reasoning_id)
    pipeline = reasoning_cls.get_pipeline(settings, reasoning_state, retrievers)
    return pipeline, reasoning_state, reasoning_id


def _prepare_file_context(pipeline, request, dependencies, selected_inputs, user_id):
    active_file_id = str(request.active_file_id or "")
    active_file_name = str(request.active_file_name or "")
    selected_file_ids: list[str] = []
    if dependencies.get_file_index() is not None:
        selected_input = selected_inputs.get(dependencies.get_file_index().id)
        selected_file_ids = dependencies.get_file_index().resolve_selected_ids(
            user_id,
            selected_input,
        )
        active_file_id, active_file_name = _runtime_preview.resolve_active_source(
            dependencies.get_preview(),
            selected_file_ids,
            active_file_id,
            active_file_name,
            user_id=user_id,
        )
    normalized_page_number = dependencies.normalize_page_number(request.page_number)
    qa_scope = dependencies.normalize_qa_scope(request.qa_scope, normalized_page_number)
    selected_text = str(request.selected_text or "").strip()
    selected_text = _runtime_preview.resolve_page_text(
        dependencies.get_preview(),
        qa_scope,
        normalized_page_number,
        active_file_id,
        active_file_name,
        selected_text,
        user_id=user_id,
    )
    graph_context = (
        request.graph_context if isinstance(request.graph_context, dict) else {}
    )
    is_pdf_file = str(active_file_name or "").lower().endswith(".pdf")
    scoped_page_number = (
        normalized_page_number
        if qa_scope == "page" and is_pdf_file and normalized_page_number is not None
        else None
    )
    pipeline.active_file_id = active_file_id or ""
    pipeline.active_file_name = active_file_name
    pipeline.qa_scope = qa_scope
    pipeline.page_number = scoped_page_number
    pipeline.selected_text = selected_text
    pipeline.selected_file_records = dependencies.selected_file_records(
        selected_file_ids,
        active_file_id or "",
        user_id,
    )
    return (
        selected_file_ids,
        active_file_id,
        active_file_name,
        qa_scope,
        scoped_page_number,
        selected_text,
        graph_context,
    )


def _prepare_multimodal_context(
    pipeline,
    request,
    dependencies,
    user_id,
    selected_file_ids,
    active_file_id,
    graph_context,
):
    dependencies.apply_page_image_records(pipeline, request)
    graph_source_ids = dependencies.normalize_selected_file_ids(
        request.graph_source_ids
    )
    _runtime_preview.validate_sources(
        dependencies.get_preview(),
        graph_source_ids,
        user_id=user_id,
    )
    graph_context = dependencies.apply_multimodal_indexes(
        pipeline,
        dependencies.get_file_index(),
        selected_file_ids,
        active_file_id,
        graph_source_ids,
        graph_context,
    )
    dependencies.apply_element_records(pipeline, request)
    dependencies.apply_request_context(pipeline, request, graph_context)
    return graph_context
