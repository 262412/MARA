from __future__ import annotations

from typing import Any

from .controller import build_controller_outputs
from .visual_backends import (
    build_visual_generator_backend as _build_visual_generator_backend,
)
from .visual_backends import (
    build_visual_retriever_backend as _build_visual_retriever_backend,
)


class ResponseCapture:
    def __init__(self, request: Any | None = None) -> None:
        self.request = request
        self.agent_trace: list[dict[str, Any]] = []
        self.evidence_metadata: dict[str, Any] = {}
        self.artifact: Any = None

    def ingest(self, channel: str | None, content: Any) -> None:
        mara_channel = None
        mara_content = content
        if channel == "debug" and isinstance(content, dict):
            candidate = content.get("mara_channel")
            if candidate in {"agent_trace", "evidence_metadata", "artifact"}:
                mara_channel = candidate
                mara_content = content.get("payload")

        if channel == "agent_trace" or mara_channel == "agent_trace":
            if mara_content is None:
                self.agent_trace = []
            elif isinstance(mara_content, list):
                self.agent_trace.extend(mara_content)
            else:
                self.agent_trace.append(mara_content)
        elif channel == "evidence_metadata" or mara_channel == "evidence_metadata":
            if isinstance(mara_content, dict):
                self.evidence_metadata.update(mara_content)
            else:
                self.evidence_metadata["value"] = mara_content
        elif channel == "artifact" or mara_channel == "artifact":
            self.artifact = mara_content

    def as_response_kwargs(self, answer: str = "") -> dict[str, Any]:
        payload = {
            "agent_trace": self.agent_trace,
            "evidence_metadata": self.evidence_metadata,
            "backend_metadata": _backend_metadata(self.request, self.evidence_metadata),
            "artifact": self.artifact,
        }
        payload.update(
            build_controller_outputs(
                self.request,
                self.agent_trace,
                self.evidence_metadata,
                answer,
            )
        )
        return payload


def apply_request_context(pipeline: Any, request: Any, graph_context: dict) -> None:
    pipeline.graph_context = graph_context
    pipeline.task_type = request.task_type or ""
    pipeline.agent_mode = request.agent_mode or getattr(pipeline, "agent_mode", "auto")
    pipeline.artifact_type = request.artifact_type or ""
    pipeline.controller_mode = request.controller_mode or "off"
    pipeline.route_policy = request.route_policy or "auto"
    pipeline.planner_model = request.planner_model or ""
    pipeline.allowed_routes = list(request.allowed_routes or [])
    pipeline.verification_mode = request.verification_mode or "off"
    pipeline.graph_mode = str(getattr(request, "graph_mode", "") or "").strip()
    _apply_visual_backends(pipeline, request)
    pipeline.docqa_request = request


def build_visual_retriever_backend(backend_name: str):
    return _build_visual_retriever_backend(backend_name)


def build_visual_generator_backend(backend_name: str):
    return _build_visual_generator_backend(backend_name)


def _apply_visual_backends(pipeline: Any, request: Any) -> None:
    retriever_backend = str(
        getattr(request, "visual_retriever_backend", "") or ""
    ).strip()
    generator_backend = str(
        getattr(request, "visual_generator_backend", "") or ""
    ).strip()
    pipeline.visual_retriever_backend = retriever_backend
    pipeline.visual_generator_backend = generator_backend
    retriever = build_visual_retriever_backend(retriever_backend)
    generator = build_visual_generator_backend(generator_backend)
    if retriever is not None:
        pipeline.visual_retriever = retriever
    if generator is not None:
        pipeline.vlm_generator = generator


def _backend_metadata(
    request: Any | None,
    evidence_metadata: dict[str, Any],
) -> dict[str, str]:
    metadata: dict[str, str] = {}
    graph_backend = str(evidence_metadata.get("graph_backend") or "").strip()
    if not graph_backend and evidence_metadata.get("graph_evidence"):
        graph_backend = "local_graph_index"
    if graph_backend:
        metadata["graph_backend"] = graph_backend

    for source_key, output_key in (
        ("graph_mode", "graph_mode"),
        ("visual_backend_type", "visual_backend_type"),
        ("visual_retriever_backend", "visual_retriever"),
        ("text_retriever_backend", "text_retriever"),
        ("generation_backend", "generator_backend"),
    ):
        value = str(evidence_metadata.get(source_key) or "").strip()
        if value:
            metadata[output_key] = value

    planner_model = str(getattr(request, "planner_model", "") or "").strip()
    if planner_model:
        metadata["planner_backend"] = planner_model
    visual_retriever = str(
        getattr(request, "visual_retriever_backend", "") or ""
    ).strip()
    if visual_retriever:
        metadata["visual_retriever"] = visual_retriever
    visual_generator = str(
        getattr(request, "visual_generator_backend", "") or ""
    ).strip()
    if visual_generator:
        metadata["visual_generator"] = visual_generator
    return metadata


def copy_request_fields(target: Any, source: Any) -> None:
    target.task_type = source.task_type
    target.agent_mode = source.agent_mode
    target.artifact_type = source.artifact_type
    target.note_ids = source.note_ids
    target.controller_mode = source.controller_mode
    target.route_policy = source.route_policy
    target.planner_model = source.planner_model
    target.allowed_routes = source.allowed_routes
    target.verification_mode = source.verification_mode
    target.graph_mode = source.graph_mode
    target.visual_retriever_backend = source.visual_retriever_backend
    target.visual_generator_backend = source.visual_generator_backend


def selected_ids(runtime: Any, user_id: Any, selected_inputs: dict[int, Any]):
    file_index = runtime.file_index
    if file_index is None or file_index.id not in selected_inputs:
        return None
    return file_index.resolve_selected_ids(user_id, selected_inputs[file_index.id])
