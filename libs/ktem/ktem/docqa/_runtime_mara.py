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
        self.execution: dict[str, Any] | None = None
        self.artifact: Any = None

    def ingest(self, channel: str | None, content: Any) -> None:
        mara_channel = None
        mara_content = content
        if channel == "debug" and isinstance(content, dict):
            candidate = content.get("mara_channel")
            if candidate in {
                "agent_trace",
                "evidence_metadata",
                "execution",
                "artifact",
            }:
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
        elif channel == "execution" or mara_channel == "execution":
            if isinstance(mara_content, dict):
                self.execution = dict(mara_content)
        elif channel == "artifact" or mara_channel == "artifact":
            self.artifact = mara_content

    def as_response_kwargs(self, answer: str = "") -> dict[str, Any]:
        if self.execution is not None:
            return _execution_response_kwargs(
                self.request,
                self.agent_trace,
                self.evidence_metadata,
                self.execution,
                self.artifact,
            )
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


def _execution_response_kwargs(
    request: Any | None,
    agent_trace: list[dict[str, Any]],
    captured_evidence_metadata: dict[str, Any],
    execution: dict[str, Any],
    artifact: Any,
) -> dict[str, Any]:
    evidence_bundle = _dict_field(execution, "evidence_bundle")
    evidence_metadata = dict(captured_evidence_metadata)
    bundle_metadata = evidence_bundle.get("metadata")
    if isinstance(bundle_metadata, dict):
        evidence_metadata.update(bundle_metadata)

    payload = {
        "agent_trace": agent_trace,
        "evidence_metadata": evidence_metadata,
        "backend_metadata": _backend_metadata(request, evidence_metadata),
        "artifact": artifact,
        "controller_trace": _list_field(execution, "controller_trace"),
        "controller_decision": _dict_field(execution, "controller_decision"),
        "route_decision": _dict_field(execution, "route_decision"),
        "retrieve_decision": _dict_field(execution, "retrieve_decision"),
        "verify_decision": _dict_field(execution, "verify_decision"),
        "guardrail_decision": _dict_field(execution, "guardrail_decision"),
        "evidence_bundle": evidence_bundle,
        "workflow_plan": _dict_field(execution, "workflow_plan"),
    }
    if not payload["route_decision"]:
        payload["route_decision"] = _route_decision_from_controller(
            payload["controller_decision"]
        )
    return payload


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _list_field(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _route_decision_from_controller(
    controller_decision: dict[str, Any],
) -> dict[str, Any]:
    legacy_route = str(
        controller_decision.get("legacy_route")
        or controller_decision.get("route")
        or ""
    ).strip()
    if not legacy_route:
        return {}
    return {
        "route": legacy_route,
        "policy": controller_decision.get("policy"),
        "controller_mode": controller_decision.get("controller_mode"),
        "requires_retrieval": controller_decision.get("requires_retrieval"),
        "reason": controller_decision.get("reason"),
    }


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
    target.max_context_length = source.max_context_length


def selected_ids(runtime: Any, user_id: Any, selected_inputs: dict[int, Any]):
    file_index = runtime.file_index
    if file_index is None or file_index.id not in selected_inputs:
        return None
    return file_index.resolve_selected_ids(user_id, selected_inputs[file_index.id])
