from __future__ import annotations

import os
from copy import copy, deepcopy
from time import monotonic
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
                self.execution = deepcopy(mara_content)
        elif channel == "artifact" or mara_channel == "artifact":
            self.artifact = mara_content

    def as_response_kwargs(
        self, answer: str = "", references_text: str = ""
    ) -> dict[str, Any]:
        if self.execution is not None:
            return _execution_response_kwargs(
                self.request,
                self.agent_trace,
                self.evidence_metadata,
                self.execution,
                self.artifact,
                answer,
                references_text,
            )
        evidence_metadata = _metadata_with_reference_evidence(
            self.request,
            self.evidence_metadata,
            references_text,
        )
        payload = {
            "agent_trace": self.agent_trace,
            "evidence_metadata": evidence_metadata,
            "backend_metadata": _backend_metadata(self.request, evidence_metadata),
            "artifact": self.artifact,
        }
        payload.update(
            build_controller_outputs(
                self.request,
                self.agent_trace,
                evidence_metadata,
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
    answer: str = "",
    references_text: str = "",
) -> dict[str, Any]:
    evidence_bundle = _dict_field(execution, "evidence_bundle")
    evidence_metadata = dict(captured_evidence_metadata)
    bundle_metadata = evidence_bundle.get("metadata")
    if isinstance(bundle_metadata, dict):
        evidence_metadata.update(bundle_metadata)
    aligned_metadata = _metadata_with_reference_evidence(
        request,
        evidence_metadata,
        references_text,
    )
    rebuilt_outputs = {}
    if not _evidence_bundle_has_items(evidence_bundle) and _has_concrete_evidence(
        aligned_metadata
    ):
        rebuilt_outputs = build_controller_outputs(
            request,
            agent_trace,
            aligned_metadata,
            answer,
        )

    payload = {
        "agent_trace": agent_trace,
        "evidence_metadata": aligned_metadata,
        "backend_metadata": _backend_metadata(request, aligned_metadata),
        "artifact": artifact,
        "controller_trace": _list_field(execution, "controller_trace"),
        "controller_decision": _dict_field(execution, "controller_decision"),
        "route_decision": _dict_field(execution, "route_decision"),
        "retrieve_decision": _dict_field(execution, "retrieve_decision"),
        "verify_decision": _dict_field(execution, "verify_decision"),
        "guardrail_decision": _dict_field(execution, "guardrail_decision"),
        "evidence_bundle": evidence_bundle,
        "workflow_plan": _dict_field(execution, "workflow_plan"),
        "engine_terminal_answer": str(execution.get("engine_terminal_answer") or ""),
        "engine_terminal_state": _terminal_dict_field(
            execution, "engine_terminal_state"
        ),
        "engine_verify_decision": _terminal_dict_field(
            execution, "engine_verify_decision"
        ),
        "engine_terminal_guardrail_decision": _terminal_dict_field(
            execution, "engine_terminal_guardrail_decision"
        ),
        "engine_terminal_evidence_bundle": _terminal_dict_field(
            execution, "engine_terminal_evidence_bundle"
        ),
        "engine_terminal_projection_hash": str(
            execution.get("engine_terminal_projection_hash") or ""
        ),
        "engine_terminal_commit": _terminal_dict_field(
            execution, "engine_terminal_commit"
        )
        or _terminal_dict_field(execution, "terminal_semantic_commit"),
        "terminal_semantic_commit": _terminal_dict_field(
            execution, "terminal_semantic_commit"
        )
        or _terminal_dict_field(execution, "engine_terminal_commit"),
    }
    payload.update(rebuilt_outputs)
    if not payload["route_decision"]:
        payload["route_decision"] = _route_decision_from_controller(
            payload["controller_decision"]
        )
    return payload


def _dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return dict(value) if isinstance(value, dict) else {}


def _terminal_dict_field(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return deepcopy(value) if isinstance(value, dict) else {}


def _list_field(payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
    value = payload.get(key)
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _evidence_bundle_has_items(evidence_bundle: dict[str, Any]) -> bool:
    items = evidence_bundle.get("items")
    return isinstance(items, list) and bool(items)


def _metadata_with_reference_evidence(
    request: Any | None,
    evidence_metadata: dict[str, Any],
    references_text: str,
) -> dict[str, Any]:
    if _has_concrete_evidence(evidence_metadata):
        return evidence_metadata

    text = str(references_text or "").strip()
    if not text:
        return evidence_metadata

    bridged = dict(evidence_metadata)
    bridged["evidence"] = [_reference_evidence_item(request, text)]
    return bridged


def _has_concrete_evidence(evidence_metadata: dict[str, Any]) -> bool:
    for key in (
        "evidence",
        "graph_evidence",
        "page_image_index",
        "element_index",
        "elements",
    ):
        value = evidence_metadata.get(key)
        if isinstance(value, list) and value:
            return True
    return False


def _reference_evidence_item(request: Any | None, text: str) -> dict[str, Any]:
    source_id = str(getattr(request, "active_file_id", "") or "").strip()
    source_name = str(getattr(request, "active_file_name", "") or "").strip()
    page_number = getattr(request, "page_number", None)
    page_label = str(page_number or "").strip()
    return {
        "evidence_id": "citation-refs",
        "source_id": source_id or "refs",
        "source_name": source_name or "Generated citations",
        "page_label": page_label,
        "modality": "text",
        "element_id": "",
        "bbox": None,
        "caption": "",
        "text": text,
        "ocr_text": "",
        "vlm_text": "",
        "source_backrefs": (
            [f"{source_id}#page:{page_label}"] if source_id and page_label else []
        ),
        "evidence_level": "citation",
        "metadata": {"source": "references_html"},
    }


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
    pipeline.controller_question = str(
        getattr(request, "controller_question", "") or ""
    ).strip()
    pipeline.retrieval_query = str(
        getattr(request, "retrieval_query", "") or ""
    ).strip()
    pipeline.selected_file_ids = list(getattr(request, "selected_file_ids", None) or [])
    pipeline.selected_source_title = " ".join(
        str(getattr(request, "selected_source_title", "") or "").split()
    )
    pipeline.dataset_family = str(getattr(request, "dataset_family", "") or "").strip()
    pipeline.task_type = request.task_type or ""
    pipeline.answer_type = request.answer_type or pipeline.task_type
    pipeline.modality = str(getattr(request, "modality", "") or "").strip()
    pipeline.agent_mode = request.agent_mode or getattr(pipeline, "agent_mode", "auto")
    pipeline.artifact_type = request.artifact_type or ""
    pipeline.controller_mode = request.controller_mode or "off"
    pipeline.route_policy = request.route_policy or "auto"
    pipeline.planner_backend = request.planner_backend or ""
    pipeline.planner_model = (
        ""
        if pipeline.planner_backend == "heuristic_local"
        else request.planner_model or ""
    )
    pipeline.allowed_routes = list(request.allowed_routes or [])
    pipeline.verification_mode = request.verification_mode or "off"
    pipeline.verification_domain = request.verification_domain or ""
    if not pipeline.dataset_family:
        pipeline.dataset_family = pipeline.verification_domain
    pipeline.graph_mode = str(getattr(request, "graph_mode", "") or "").strip()
    pipeline.route_timeout_seconds = getattr(
        request,
        "route_timeout_seconds",
        None,
    )
    route_deadline = getattr(request, "route_deadline_monotonic", None)
    if route_deadline is None and pipeline.route_timeout_seconds:
        route_deadline = monotonic() + float(pipeline.route_timeout_seconds)
    pipeline.route_deadline_monotonic = route_deadline
    pipeline.route_terminal_reserve_seconds = getattr(
        request,
        "route_terminal_reserve_seconds",
        None,
    )
    _apply_visual_backends(pipeline, request)
    configure_semantic_proposition_runtime(pipeline, request)
    pipeline.docqa_request = request


def configure_semantic_proposition_runtime(pipeline: Any, request: Any) -> None:
    """Give strict QASPER benchmark runs an independent audit instance."""

    release_mode = (
        str(getattr(request, "origin", "") or "").strip().casefold() == "benchmark"
        and str(getattr(request, "verification_domain", "") or "").strip().casefold()
        == "qasper"
        and str(getattr(request, "verification_mode", "") or "").strip().casefold()
        == "strict"
    )
    pipeline.semantic_proposition_release_mode = release_mode
    if not release_mode:
        return
    configured = getattr(pipeline, "semantic_entailment_auditor_llm", None)
    answering = getattr(getattr(pipeline, "answering_pipeline", None), "llm", None)
    if callable(configured) and configured is not answering:
        return
    auditor = _configured_qasper_auditor() or copy(answering)
    if callable(auditor) and auditor is not answering:
        pipeline.semantic_entailment_auditor_llm = auditor


def _configured_qasper_auditor() -> Any | None:
    base_url = os.environ.get("MARA_QASPER_CONTRACT_AUDITOR_BASE_URL", "").strip()
    model = os.environ.get("MARA_QASPER_CONTRACT_AUDITOR_MODEL", "").strip()
    if not base_url and not model:
        return None
    if not base_url or not model:
        raise ValueError(
            "QASPER auditor configuration requires both base URL and model"
        )

    from kotaemon.llms import ChatOpenAI

    return ChatOpenAI(
        api_key=os.environ.get("OPENAI_API_KEY") or "local",
        base_url=base_url,
        model=model,
        temperature=0,
        timeout=float(os.environ.get("MARA_SEMANTIC_EVALUATOR_TIMEOUT_SECONDS", "60")),
        max_retries=0,
    )


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

    planner_backend = str(getattr(request, "planner_backend", "") or "").strip()
    planner_model = str(getattr(request, "planner_model", "") or "").strip()
    if planner_backend:
        metadata["planner_backend"] = planner_backend
    elif planner_model:
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
    target.controller_question = getattr(source, "controller_question", "")
    target.retrieval_query = getattr(source, "retrieval_query", "")
    target.selected_source_title = getattr(source, "selected_source_title", "")
    target.dataset_family = getattr(source, "dataset_family", "")
    target.source_identity_crosswalk = getattr(
        source, "source_identity_crosswalk", None
    )
    target.reranker_name = getattr(source, "reranker_name", None)
    target.task_type = source.task_type
    target.answer_type = source.answer_type
    target.modality = source.modality
    target.agent_mode = source.agent_mode
    target.artifact_type = source.artifact_type
    target.note_ids = source.note_ids
    target.controller_mode = source.controller_mode
    target.route_policy = source.route_policy
    target.planner_backend = source.planner_backend
    target.planner_model = source.planner_model
    target.allowed_routes = source.allowed_routes
    target.verification_mode = source.verification_mode
    target.verification_domain = source.verification_domain
    target.graph_mode = source.graph_mode
    target.visual_retriever_backend = source.visual_retriever_backend
    target.visual_generator_backend = source.visual_generator_backend
    target.page_image_records = source.page_image_records
    target.element_index_records = source.element_index_records
    target.max_context_length = source.max_context_length
    target.route_timeout_seconds = source.route_timeout_seconds
    target.route_deadline_monotonic = source.route_deadline_monotonic
    target.route_terminal_reserve_seconds = source.route_terminal_reserve_seconds
    target.generation_temperature = source.generation_temperature
    target.generation_top_p = source.generation_top_p
    target.generation_seed = source.generation_seed
    target.trace_context = dict(getattr(source, "trace_context", {}) or {})


def selected_ids(runtime: Any, user_id: Any, selected_inputs: dict[int, Any]):
    file_index = runtime.file_index
    if file_index is None or file_index.id not in selected_inputs:
        return None
    return file_index.resolve_selected_ids(user_id, selected_inputs[file_index.id])
