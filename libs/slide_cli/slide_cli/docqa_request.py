from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, fields
from typing import Any

RUNTIME_DOCQA_REQUEST_FIELD_NAMES = (
    "prompt",
    "controller_question",
    "retrieval_query",
    "retrieval_slot_id",
    "retrieval_round_id",
    "dataset_family",
    "conversation_id",
    "selected_file_ids",
    "source_identity_crosswalk",
    "selected_inputs",
    "qa_scope",
    "active_file_id",
    "active_file_name",
    "page_number",
    "selected_text",
    "graph_context",
    "graph_source_ids",
    "settings",
    "state",
    "history",
    "max_context_length",
    "reasoning_type",
    "task_type",
    "agent_mode",
    "artifact_type",
    "note_ids",
    "controller_mode",
    "route_policy",
    "planner_backend",
    "planner_model",
    "planned_query_plan",
    "query_plan",
    "query_plan_id",
    "query_plan_state_version",
    "allowed_routes",
    "verification_mode",
    "verification_domain",
    "graph_mode",
    "visual_retriever_backend",
    "visual_generator_backend",
    "reranker_name",
    "page_image_records",
    "element_index_records",
    "llm",
    "use_mindmap",
    "use_citation",
    "language",
    "command_state",
    "route_timeout_seconds",
    "route_deadline_monotonic",
    "generation_temperature",
    "generation_top_p",
    "generation_seed",
    "user_id",
    "origin",
)


class DocQARequestContractError(RuntimeError):
    """The compatibility facade and canonical runtime request have drifted."""


@dataclass
class DocQARequest:
    prompt: str
    conversation_id: str = ""
    selected_file_ids: list[str] | None = None
    selected_inputs: dict[int, Any] | None = None
    qa_scope: str = "auto"
    active_file_id: str = ""
    active_file_name: str = ""
    page_number: int | None = None
    selected_text: str = ""
    graph_context: dict[str, Any] = field(default_factory=dict)
    graph_source_ids: list[str] | None = None
    settings: dict[str, Any] | None = None
    state: dict[str, Any] | None = None
    history: list[tuple[str, str]] | None = None
    max_context_length: int | None = None
    reasoning_type: str | None = None
    task_type: str | None = None
    agent_mode: str | None = None
    artifact_type: str | None = None
    note_ids: list[str] | None = None
    controller_mode: str | None = None
    route_policy: str | None = None
    planner_backend: str | None = None
    planner_model: str | None = None
    allowed_routes: list[str] | None = None
    verification_mode: str | None = None
    verification_domain: str | None = None
    graph_mode: str | None = None
    visual_retriever_backend: str | None = None
    visual_generator_backend: str | None = None
    page_image_records: list[dict[str, Any]] | None = None
    llm: str | None = None
    use_mindmap: bool | str | None = None
    use_citation: str | None = None
    language: str | None = None
    command_state: str | None = None
    user_id: Any = None
    origin: str = "cli"
    controller_question: str = ""
    retrieval_query: str = ""
    dataset_family: str = ""
    element_index_records: list[dict[str, Any]] | None = None
    route_timeout_seconds: float | None = None
    route_deadline_monotonic: float | None = None
    retrieval_slot_id: str = ""
    retrieval_round_id: int = 0
    planned_query_plan: Any = None
    query_plan: Any = None
    query_plan_id: str = ""
    query_plan_state_version: int = 0
    source_identity_crosswalk: list[dict[str, Any]] | None = None
    reranker_name: str | None = None
    generation_temperature: float | None = None
    generation_top_p: float | None = None
    generation_seed: int | None = None


def to_runtime_docqa_request(request: DocQARequest):
    from ktem.docqa import DocQARequest as RuntimeDocQARequest

    expected = set(RUNTIME_DOCQA_REQUEST_FIELD_NAMES)
    runtime_field_names = {field.name for field in fields(RuntimeDocQARequest)}
    missing = sorted(expected - runtime_field_names)
    unexpected = sorted(runtime_field_names - expected)
    if missing or unexpected:
        raise DocQARequestContractError(
            "Canonical DocQARequest contract drifted: "
            f"missing={missing}, unexpected={unexpected}"
        )

    return RuntimeDocQARequest(
        prompt=deepcopy(request.prompt),
        controller_question=deepcopy(request.controller_question),
        retrieval_query=deepcopy(request.retrieval_query),
        retrieval_slot_id=deepcopy(request.retrieval_slot_id),
        retrieval_round_id=deepcopy(request.retrieval_round_id),
        dataset_family=deepcopy(request.dataset_family),
        conversation_id=deepcopy(request.conversation_id),
        selected_file_ids=deepcopy(request.selected_file_ids),
        source_identity_crosswalk=deepcopy(request.source_identity_crosswalk),
        selected_inputs=deepcopy(request.selected_inputs),
        qa_scope=deepcopy(request.qa_scope),
        active_file_id=deepcopy(request.active_file_id),
        active_file_name=deepcopy(request.active_file_name),
        page_number=deepcopy(request.page_number),
        selected_text=deepcopy(request.selected_text),
        graph_context=deepcopy(request.graph_context),
        graph_source_ids=deepcopy(request.graph_source_ids),
        settings=deepcopy(request.settings),
        state=deepcopy(request.state),
        history=deepcopy(request.history),
        max_context_length=deepcopy(request.max_context_length),
        reasoning_type=deepcopy(request.reasoning_type),
        task_type=deepcopy(request.task_type),
        agent_mode=deepcopy(request.agent_mode),
        artifact_type=deepcopy(request.artifact_type),
        note_ids=deepcopy(request.note_ids),
        controller_mode=deepcopy(request.controller_mode),
        route_policy=deepcopy(request.route_policy),
        planner_backend=deepcopy(request.planner_backend),
        planner_model=deepcopy(request.planner_model),
        planned_query_plan=deepcopy(request.planned_query_plan),
        query_plan=deepcopy(request.query_plan),
        query_plan_id=deepcopy(request.query_plan_id),
        query_plan_state_version=deepcopy(request.query_plan_state_version),
        allowed_routes=deepcopy(request.allowed_routes),
        verification_mode=deepcopy(request.verification_mode),
        verification_domain=deepcopy(request.verification_domain),
        graph_mode=deepcopy(request.graph_mode),
        visual_retriever_backend=deepcopy(request.visual_retriever_backend),
        visual_generator_backend=deepcopy(request.visual_generator_backend),
        reranker_name=deepcopy(request.reranker_name),
        page_image_records=deepcopy(request.page_image_records),
        element_index_records=deepcopy(request.element_index_records),
        llm=deepcopy(request.llm),
        use_mindmap=deepcopy(request.use_mindmap),
        use_citation=deepcopy(request.use_citation),
        language=deepcopy(request.language),
        command_state=deepcopy(request.command_state),
        route_timeout_seconds=deepcopy(request.route_timeout_seconds),
        route_deadline_monotonic=deepcopy(request.route_deadline_monotonic),
        generation_temperature=deepcopy(request.generation_temperature),
        generation_top_p=deepcopy(request.generation_top_p),
        generation_seed=deepcopy(request.generation_seed),
        user_id=deepcopy(request.user_id),
        origin=deepcopy(request.origin),
    )
