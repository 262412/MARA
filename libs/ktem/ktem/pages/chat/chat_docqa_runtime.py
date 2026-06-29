from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import gradio as gr
from ktem.docqa import DocQARequest

from .studio_artifacts import render_controller_trace_html


def build_web_docqa_request(
    *,
    prompt: str,
    conversation_id: str = "",
    history: list | None = None,
    selected_file_ids: list[str] | None = None,
    selected_inputs: dict[int, Any] | None = None,
    settings: dict | None = None,
    reasoning_type: str | None = None,
    llm: str | None = None,
    use_mindmap: bool | str | None = None,
    use_citation: str | None = None,
    language: str | None = None,
    state: dict | None = None,
    command_state: str | None = None,
    user_id: Any = None,
    active_file_id: str = "",
    active_file_name: str = "",
    page_number: Any = None,
    qa_scope: str = "page",
    selected_text: str = "",
    selected_graph_context: str = "",
    task_type: str | None = None,
    agent_mode: str | None = None,
    artifact_type: str | None = None,
    note_ids: list[str] | None = None,
    controller_mode: str = "llm",
    route_policy: str = "auto",
    verification_mode: str = "light",
    verification_domain: str | None = None,
    max_context_length: int | None = None,
    page_image_records: list[dict[str, Any]] | None = None,
    planner_backend: str | None = None,
    planner_model: str | None = None,
    allowed_routes: list[str] | None = None,
) -> DocQARequest:
    return DocQARequest(
        prompt=str(prompt or ""),
        conversation_id=str(conversation_id or ""),
        selected_file_ids=list(selected_file_ids) if selected_file_ids else None,
        selected_inputs=dict(selected_inputs or {}),
        active_file_id=str(active_file_id or ""),
        active_file_name=str(active_file_name or ""),
        qa_scope=str(qa_scope or "page").replace("-", "_"),
        page_number=max(1, int(page_number or 1)),
        selected_text=str(selected_text or "").strip(),
        graph_context=_parse_graph_context(selected_graph_context),
        settings=deepcopy(settings),
        state=deepcopy(state),
        history=list(history or []),
        reasoning_type=reasoning_type,
        task_type=task_type,
        agent_mode=agent_mode,
        artifact_type=artifact_type,
        note_ids=list(note_ids or []),
        controller_mode=str(controller_mode or "llm"),
        route_policy=str(route_policy or "auto"),
        planner_backend=planner_backend,
        planner_model=planner_model,
        allowed_routes=list(allowed_routes or []),
        verification_mode=str(verification_mode or "light"),
        verification_domain=verification_domain,
        max_context_length=max_context_length,
        page_image_records=list(page_image_records or []),
        llm=llm,
        use_mindmap=use_mindmap,
        use_citation=use_citation,
        language=language,
        command_state=command_state,
        user_id=user_id,
        origin="web",
    )


def _parse_graph_context(value: str) -> dict[str, Any]:
    try:
        payload = json.loads(value) if value else {}
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def runtime_trace_references(response: Any, references_html: str) -> str:
    if not any(
        getattr(response, field, None)
        for field in (
            "route_decision",
            "controller_decision",
            "retrieve_decision",
            "verify_decision",
            "evidence_bundle",
        )
    ):
        return references_html
    route_decision = getattr(response, "route_decision", None) or _route_decision(
        getattr(response, "controller_decision", None)
    )
    controller_html = render_controller_trace_html(
        route_decision=route_decision,
        retrieve_decision=getattr(response, "retrieve_decision", None),
        verify_decision=getattr(response, "verify_decision", None),
        evidence_bundle=getattr(response, "evidence_bundle", None),
    )
    return references_html + controller_html


def _route_decision(controller_decision: Any) -> dict[str, Any]:
    if not isinstance(controller_decision, dict):
        return {}
    route = str(
        controller_decision.get("legacy_route")
        or controller_decision.get("route")
        or ""
    ).strip()
    if not route:
        return {}
    return {
        "route": route,
        "policy": controller_decision.get("policy"),
        "controller_mode": controller_decision.get("controller_mode"),
    }


def render_docqa_runtime_controls(
    page: Any,
    *,
    reasoning_limits: int,
    default_setting: str,
) -> None:
    reasoning_setting = page._app.default_settings.reasoning.settings["use"]
    language_setting = page._app.default_settings.reasoning.settings["lang"]
    with gr.Column(
        elem_id="reader-hidden-settings", visible=False
    ) as page.chat_settings:
        page.reasoning_type = gr.Dropdown(
            choices=reasoning_setting.choices[:reasoning_limits],
            value=reasoning_setting.value,
            container=False,
            show_label=False,
            visible=False,
        )
        page.language = gr.Dropdown(
            choices=language_setting.choices,
            value=language_setting.value,
            container=False,
            show_label=False,
            visible=False,
        )
        page.model_type = gr.State(value=default_setting)
        page.citation = gr.State(value=default_setting)
        page.use_mindmap = gr.State(value=default_setting)

    with gr.Accordion(
        label="Research Controls",
        open=False,
        elem_id="docqa-research-controls",
    ):
        with gr.Row():
            page.docqa_controller_mode = gr.Dropdown(
                choices=["llm", "off"],
                value="llm",
                label="Controller",
                container=False,
            )
            page.docqa_route_policy = gr.Dropdown(
                choices=[
                    "auto",
                    "direct",
                    "doc",
                    "visual",
                    "element",
                    "graph",
                    "hybrid",
                ],
                value="auto",
                label="Route",
                container=False,
            )
            page.docqa_verification_mode = gr.Dropdown(
                choices=["off", "light", "strict"],
                value="light",
                label="Verify",
                container=False,
            )
        page.docqa_planner_model = gr.Textbox(
            value="",
            label="Planner model",
            placeholder="optional",
            container=False,
        )


def docqa_research_control_inputs(page: Any) -> list[Any]:
    return [
        page.docqa_controller_mode,
        page.docqa_route_policy,
        page.docqa_verification_mode,
        page.docqa_planner_model,
    ]
