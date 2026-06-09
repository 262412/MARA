from __future__ import annotations

import logging
from functools import partial
from typing import Any

import gradio as gr

from .chat_docqa_runtime import docqa_research_control_inputs
from .studio_artifact_generation import (
    run_studio_artifact_regenerate_turn,
    run_studio_artifact_turn,
    selected_source_ids_for_studio_artifact,
)
from .studio_artifact_mindmap import (
    generate_studio_mindmap_outputs,
    save_studio_mindmap_artifact,
)
from .studio_artifact_outputs import generation_panel_outputs
from .studio_artifact_outputs import (
    latest_notebook_artifact as _latest_notebook_artifact,
)
from .studio_artifact_outputs import unique_text as _unique_text
from .studio_artifact_parameters import dependent_parameter_updates
from .studio_artifact_picker import bind_studio_artifact_picker_events
from .studio_artifact_status import (
    failed_generation_studio_artifact_outputs,
    failed_regeneration_studio_artifact_outputs,
    render_studio_artifact_regenerating_update,
    render_studio_artifact_running_update,
)
from .studio_artifacts import (
    delete_latest_artifact_update,
    export_latest_artifact_update,
)
from .studio_note_controls import bind_studio_note_events

LOGGER = logging.getLogger(__name__)


def bind_studio_artifact_events(page: Any) -> None:
    bind_studio_artifact_picker_events(page)
    page.studio_artifact_format.change(
        update_studio_artifact_dependent_parameters,
        inputs=[page.studio_artifact_type, page.studio_artifact_format],
        outputs=[page.studio_artifact_prompt, page.studio_artifact_format_explanation],
        show_progress="hidden",
    )
    page.studio_generate_artifact_button.click(
        render_studio_artifact_running_update,
        inputs=[
            page.studio_artifact_type,
            page._graph_source_ids,
            page._active_file_id,
            *page._indices_input,
        ],
        outputs=[
            page.reasoning_trace_panel,
            page.plot_panel,
            page.studio_artifact_selector_panel,
            page.studio_artifact_overlay_backdrop,
            page.studio_artifact_detail_panel,
        ],
        show_progress="hidden",
    ).then(
        partial(generate_studio_artifact_panel_update, page),
        inputs=studio_generate_inputs(page),
        outputs=studio_generate_outputs(page),
        show_progress="minimal",
    )
    bind_studio_note_events(page)
    page.studio_delete_artifact_button.click(
        delete_latest_artifact_update,
        inputs=[page.chat_control.conversation_id],
        outputs=[page.notebook_panel],
        show_progress="hidden",
    )
    page.studio_export_artifact_button.click(
        export_latest_artifact_update,
        inputs=[page.chat_control.conversation_id, page.studio_export_format],
        outputs=[page.notebook_panel],
        show_progress="hidden",
    )
    page.studio_regenerate_artifact_button.click(
        render_studio_artifact_regenerating_update,
        inputs=[page.chat_control.conversation_id],
        outputs=[page.reasoning_trace_panel, page.plot_panel],
        show_progress="hidden",
    ).then(
        partial(regenerate_latest_studio_artifact_panel_update, page),
        inputs=studio_regenerate_inputs(page),
        outputs=studio_generate_outputs(page),
        show_progress="minimal",
    )


def update_studio_artifact_dependent_parameters(
    artifact_type: str,
    output_format: Any,
) -> tuple[Any, Any]:
    prompt_update, explanation_update = dependent_parameter_updates(
        artifact_type,
        output_format,
    )
    return gr.update(**prompt_update), gr.update(**explanation_update)


def studio_generate_inputs(page: Any) -> list[Any]:
    return [
        page.studio_artifact_type,
        page.studio_artifact_prompt,
        page.studio_artifact_scope,
        page.studio_artifact_format,
        page.studio_artifact_difficulty,
        page.studio_artifact_count,
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
        page._selected_page_text,
        page._selected_graph_context,
        *docqa_research_control_inputs(page),
        page.studio_artifact_note_ids,
        *page._indices_input,
    ]


def studio_generate_outputs(page: Any) -> list[Any]:
    return [
        page.chat_control.conversation_id,
        page.chat_panel.chatbot,
        page.state_retrieval_history,
        page.state_plot_history,
        page.state_chat,
        page.answer_panel,
        page.citations_panel,
        page.reasoning_trace_panel,
        page.notebook_panel,
        page._graph_source_ids,
        page.plot_panel,
        page.state_plot_panel,
    ]


def studio_regenerate_inputs(page: Any) -> list[Any]:
    return [
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
        page._selected_page_text,
        page._selected_graph_context,
        *docqa_research_control_inputs(page),
        page._graph_source_ids,
        *page._indices_input,
    ]


def generate_studio_artifact_panel_update(
    page: Any,
    artifact_type: str,
    prompt: str,
    qa_scope: str,
    output_format: str,
    difficulty: str,
    count: Any,
    conversation_id: str,
    chat_history: list,
    settings: dict,
    reasoning_type: str,
    llm_type: str,
    use_mindmap: bool | str,
    use_citation: str,
    language: str,
    chat_state: dict,
    command_state: str | None,
    user_id: Any,
    active_file_id: str,
    active_file_name: str,
    page_number: int,
    selected_page_text: str,
    selected_graph_context: str,
    controller_mode: str,
    route_policy: str,
    verification_mode: str,
    planner_model: str,
    note_ids: str = "",
    *selecteds: Any,
):
    values = locals()
    if not str(conversation_id or "").strip():
        return failed_generation_studio_artifact_outputs(
            page,
            **_generation_failure_kwargs(
                values,
                "Select or start a conversation before generating artifacts.",
            ),
        )

    if str(artifact_type or "").strip() == "mindmap":
        try:
            return generate_studio_mindmap_outputs(
                page,
                values,
                save_artifact=save_studio_mindmap_artifact,
            )
        except Exception as exc:
            LOGGER.exception("Studio mind map generation failed")
            return failed_generation_studio_artifact_outputs(
                page, **_generation_failure_kwargs(values, str(exc))
            )
    try:
        response = _run_generation_turn(page, **_generation_turn_kwargs(values))
    except Exception as exc:
        LOGGER.exception("Studio artifact generation failed")
        return failed_generation_studio_artifact_outputs(
            page, **_generation_failure_kwargs(values, str(exc))
        )
    return generation_panel_outputs(
        page,
        response,
        chat_state=chat_state,
        fallback_conversation_id=conversation_id,
        fallback_active_file_id=active_file_id,
        fallback_page_number=page_number,
    )


def _generation_turn_kwargs(values: dict[str, Any]) -> dict[str, Any]:
    keys = [
        "artifact_type",
        "prompt",
        "output_format",
        "difficulty",
        "count",
        "note_ids",
        "conversation_id",
        "chat_history",
        "settings",
        "reasoning_type",
        "llm_type",
        "use_mindmap",
        "use_citation",
        "language",
        "chat_state",
        "command_state",
        "user_id",
        "active_file_id",
        "active_file_name",
        "page_number",
        "qa_scope",
        "selected_page_text",
        "selected_graph_context",
        "controller_mode",
        "route_policy",
        "verification_mode",
        "planner_model",
        "selecteds",
    ]
    return {key: values[key] for key in keys}


def _generation_failure_kwargs(values: dict[str, Any], error: str) -> dict[str, Any]:
    keys = [
        "conversation_id",
        "artifact_type",
        "prompt",
        "qa_scope",
        "page_number",
        "active_file_id",
        "note_ids",
        "chat_history",
        "chat_state",
    ]
    output = {key: values[key] for key in keys}
    selected_inputs = values["page"]._build_selected_input_map(
        *values.get("selecteds", ())
    )
    output["source_ids"] = selected_source_ids_for_studio_artifact(
        values["active_file_id"],
        selected_inputs,
    )
    output["error"] = error
    return output


def regenerate_latest_studio_artifact_panel_update(
    page: Any,
    conversation_id: str,
    chat_history: list,
    settings: dict,
    reasoning_type: str,
    llm_type: str,
    use_mindmap: bool | str,
    use_citation: str,
    language: str,
    chat_state: dict,
    command_state: str | None,
    user_id: Any,
    active_file_id: str,
    active_file_name: str,
    selected_page_text: str,
    selected_graph_context: str,
    controller_mode: str,
    route_policy: str,
    verification_mode: str,
    planner_model: str,
    graph_source_ids: list[str],
    *selecteds: Any,
):
    if not str(conversation_id or "").strip():
        raise ValueError("Select a conversation before regenerating artifacts.")
    artifact = _latest_notebook_artifact(conversation_id)
    if artifact is None:
        raise ValueError("No saved Studio artifact to regenerate.")
    try:
        response = _run_regeneration_turn(
            page,
            artifact,
            conversation_id=conversation_id,
            chat_history=chat_history,
            settings=settings,
            reasoning_type=reasoning_type,
            llm_type=llm_type,
            use_mindmap=use_mindmap,
            use_citation=use_citation,
            language=language,
            chat_state=chat_state,
            command_state=command_state,
            user_id=user_id,
            active_file_id=active_file_id,
            active_file_name=active_file_name,
            selected_page_text=selected_page_text,
            selected_graph_context=selected_graph_context,
            controller_mode=controller_mode,
            route_policy=route_policy,
            verification_mode=verification_mode,
            planner_model=planner_model,
            graph_source_ids=graph_source_ids,
            selecteds=selecteds,
        )
    except Exception as exc:
        LOGGER.exception("Studio artifact regeneration failed")
        return failed_regeneration_studio_artifact_outputs(
            page,
            conversation_id=conversation_id,
            artifact=artifact,
            active_file_id=active_file_id,
            error=str(exc),
            chat_history=chat_history,
            chat_state=chat_state,
        )
    return generation_panel_outputs(
        page,
        response,
        chat_state=chat_state,
        fallback_conversation_id=conversation_id,
        fallback_active_file_id=active_file_id,
        fallback_page_number=1,
    )


def _run_generation_turn(
    page: Any,
    *,
    artifact_type: str,
    prompt: str,
    output_format: str,
    difficulty: str,
    count: Any,
    conversation_id: str,
    chat_history: list,
    settings: dict,
    reasoning_type: str,
    llm_type: str,
    use_mindmap: bool | str,
    use_citation: str,
    language: str,
    chat_state: dict,
    command_state: str | None,
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
    selecteds: tuple[Any, ...],
    note_ids: str = "",
):
    return run_studio_artifact_turn(
        page.docqa,
        artifact_type=artifact_type,
        prompt=prompt,
        output_format=output_format,
        difficulty=difficulty,
        count=count,
        note_ids=note_ids,
        conversation_id=conversation_id,
        chat_history=chat_history,
        selected_inputs=page._build_selected_input_map(*selecteds),
        settings=settings,
        reasoning_type=reasoning_type,
        llm_type=llm_type,
        use_mindmap=use_mindmap,
        use_citation=use_citation,
        language=language,
        chat_state=chat_state,
        command_state=command_state,
        user_id=user_id,
        active_file_id=active_file_id,
        active_file_name=active_file_name,
        page_number=page_number,
        qa_scope=qa_scope,
        selected_page_text=selected_page_text,
        selected_graph_context=selected_graph_context,
        controller_mode=controller_mode,
        route_policy=route_policy,
        verification_mode=verification_mode,
        planner_model=planner_model,
    )


def _run_regeneration_turn(
    page: Any,
    artifact: dict[str, Any],
    *,
    conversation_id: str,
    chat_history: list,
    settings: dict,
    reasoning_type: str,
    llm_type: str,
    use_mindmap: bool | str,
    use_citation: str,
    language: str,
    chat_state: dict,
    command_state: str | None,
    user_id: Any,
    active_file_id: str,
    active_file_name: str,
    selected_page_text: str,
    selected_graph_context: str,
    controller_mode: str,
    route_policy: str,
    verification_mode: str,
    planner_model: str,
    graph_source_ids: list[str],
    selecteds: tuple[Any, ...],
):
    return run_studio_artifact_regenerate_turn(
        page.docqa,
        artifact=artifact,
        fallback_source_ids=_unique_text(graph_source_ids),
        conversation_id=conversation_id,
        chat_history=chat_history,
        selected_inputs=page._build_selected_input_map(*selecteds),
        settings=settings,
        reasoning_type=reasoning_type,
        llm_type=llm_type,
        use_mindmap=use_mindmap,
        use_citation=use_citation,
        language=language,
        chat_state=chat_state,
        command_state=command_state,
        user_id=user_id,
        active_file_id=active_file_id,
        active_file_name=active_file_name,
        selected_page_text=selected_page_text,
        selected_graph_context=selected_graph_context,
        controller_mode=controller_mode,
        route_policy=route_policy,
        verification_mode=verification_mode,
        planner_model=planner_model,
    )
