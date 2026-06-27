from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


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


def to_runtime_docqa_request(request: DocQARequest):
    from ktem.docqa import DocQARequest as RuntimeDocQARequest

    payload = asdict(request)
    runtime_field_names = {field.name for field in fields(RuntimeDocQARequest)}
    return RuntimeDocQARequest(
        **{key: value for key, value in payload.items() if key in runtime_field_names}
    )
