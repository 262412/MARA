from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def controller_routing_message(pipeline: Any, message: str) -> str:
    return str(
        getattr(pipeline, "controller_question", None)
        or getattr(pipeline, "retrieval_query", None)
        or message
    ).strip()


def _pipeline_or_request_value(
    pipeline: Any,
    docqa_request: Any,
    field_name: str,
    fallback: str = "",
) -> str:
    return str(
        getattr(pipeline, field_name, None)
        or getattr(docqa_request, field_name, None)
        or fallback
    ).strip()


def _selected_source_context(
    pipeline: Any,
    docqa_request: Any,
) -> tuple[list[Any], str]:
    selected_file_ids = list(
        getattr(pipeline, "selected_file_ids", None)
        or getattr(docqa_request, "selected_file_ids", None)
        or []
    )
    selected_source_title = " ".join(
        str(
            getattr(pipeline, "selected_source_title", None)
            or getattr(docqa_request, "selected_source_title", None)
            or ""
        ).split()
    )
    return selected_file_ids, selected_source_title


def controller_execution_request(pipeline: Any, message: str) -> SimpleNamespace:
    controller_mode = str(getattr(pipeline, "controller_mode", "") or "").strip()
    docqa_request = getattr(pipeline, "docqa_request", None)
    planning_question = controller_routing_message(pipeline, message)
    task_type = _pipeline_or_request_value(pipeline, docqa_request, "task_type")
    answer_type = _pipeline_or_request_value(
        pipeline, docqa_request, "answer_type", task_type
    )
    modality = _pipeline_or_request_value(pipeline, docqa_request, "modality")
    selected_file_ids, selected_source_title = _selected_source_context(
        pipeline, docqa_request
    )
    return SimpleNamespace(
        **_controller_request_payload(
            pipeline,
            docqa_request,
            message,
            planning_question,
            task_type,
            answer_type,
            modality,
            controller_mode,
            selected_file_ids,
            selected_source_title,
        )
    )


def _controller_request_payload(
    pipeline: Any,
    docqa_request: Any,
    message: str,
    planning_question: str,
    task_type: str,
    answer_type: str,
    modality: str,
    controller_mode: str,
    selected_file_ids: list[Any],
    selected_source_title: str,
) -> dict[str, Any]:
    return {
        "prompt": message,
        "controller_question": str(
            getattr(pipeline, "controller_question", None) or planning_question
        ).strip(),
        "retrieval_query": str(
            getattr(pipeline, "retrieval_query", None) or planning_question
        ).strip(),
        "task_type": task_type,
        "answer_type": answer_type,
        "modality": modality,
        "route_timeout_seconds": getattr(pipeline, "route_timeout_seconds", None),
        "route_deadline_monotonic": getattr(pipeline, "route_deadline_monotonic", None),
        "route_terminal_reserve_seconds": getattr(
            pipeline, "route_terminal_reserve_seconds", None
        ),
        "origin": str(
            getattr(docqa_request, "origin", None)
            or getattr(pipeline, "origin", "")
            or ""
        ),
        "controller_mode": controller_mode or "llm",
        "generation_temperature": getattr(
            docqa_request,
            "generation_temperature",
            getattr(pipeline, "generation_temperature", None),
        ),
        "generation_top_p": getattr(
            docqa_request,
            "generation_top_p",
            getattr(pipeline, "generation_top_p", None),
        ),
        "generation_seed": getattr(
            docqa_request,
            "generation_seed",
            getattr(pipeline, "generation_seed", None),
        ),
        "trace_context": dict(
            getattr(docqa_request, "trace_context", None)
            or getattr(pipeline, "trace_context", None)
            or {}
        ),
        "route_policy": getattr(pipeline, "route_policy", None) or "auto",
        "allowed_routes": list(getattr(pipeline, "allowed_routes", None) or []),
        "agent_mode": getattr(pipeline, "agent_mode", None) or "auto",
        "verification_mode": getattr(pipeline, "verification_mode", None) or "light",
        "verification_domain": (
            getattr(pipeline, "verification_domain", None)
            or getattr(pipeline, "dataset_family", None)
            or ""
        ),
        "active_file_id": getattr(pipeline, "active_file_id", "") or "",
        "active_file_name": getattr(pipeline, "active_file_name", "") or "",
        "page_number": getattr(pipeline, "page_number", None),
        "selected_text": getattr(pipeline, "selected_text", "") or "",
        "selected_file_ids": selected_file_ids,
        "selected_source_title": selected_source_title,
        "graph_context": getattr(pipeline, "graph_context", None) or {},
        "visual_generator_backend": str(
            getattr(pipeline, "visual_generator_backend", "") or ""
        ).strip(),
        "vlm_generator": getattr(pipeline, "vlm_generator", None),
    }
