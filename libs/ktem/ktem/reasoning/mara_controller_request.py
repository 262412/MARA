from __future__ import annotations

from types import SimpleNamespace
from typing import Any


def controller_routing_message(pipeline: Any, message: str) -> str:
    return str(
        getattr(pipeline, "controller_question", None)
        or getattr(pipeline, "retrieval_query", None)
        or message
    ).strip()


def controller_execution_request(
    pipeline: Any,
    message: str,
) -> SimpleNamespace:
    controller_mode = str(getattr(pipeline, "controller_mode", "") or "").strip()
    docqa_request = getattr(pipeline, "docqa_request", None)
    planning_question = controller_routing_message(pipeline, message)
    task_type = str(
        getattr(pipeline, "task_type", None)
        or getattr(docqa_request, "task_type", None)
        or ""
    ).strip()
    answer_type = str(
        getattr(pipeline, "answer_type", None)
        or getattr(docqa_request, "answer_type", None)
        or task_type
    ).strip()
    return SimpleNamespace(
        prompt=message,
        controller_question=str(
            getattr(pipeline, "controller_question", None) or planning_question
        ).strip(),
        retrieval_query=str(
            getattr(pipeline, "retrieval_query", None) or planning_question
        ).strip(),
        task_type=task_type,
        answer_type=answer_type,
        route_timeout_seconds=getattr(pipeline, "route_timeout_seconds", None),
        route_deadline_monotonic=getattr(
            pipeline,
            "route_deadline_monotonic",
            None,
        ),
        origin=str(
            getattr(docqa_request, "origin", None)
            or getattr(pipeline, "origin", "")
            or ""
        ),
        controller_mode=controller_mode or "llm",
        generation_temperature=getattr(
            docqa_request,
            "generation_temperature",
            getattr(pipeline, "generation_temperature", None),
        ),
        generation_top_p=getattr(
            docqa_request,
            "generation_top_p",
            getattr(pipeline, "generation_top_p", None),
        ),
        generation_seed=getattr(
            docqa_request,
            "generation_seed",
            getattr(pipeline, "generation_seed", None),
        ),
        route_policy=getattr(pipeline, "route_policy", None) or "auto",
        allowed_routes=list(getattr(pipeline, "allowed_routes", None) or []),
        verification_mode=getattr(pipeline, "verification_mode", None) or "light",
        verification_domain=(
            getattr(pipeline, "verification_domain", None)
            or getattr(pipeline, "dataset_family", None)
            or ""
        ),
        active_file_id=getattr(pipeline, "active_file_id", "") or "",
        active_file_name=getattr(pipeline, "active_file_name", "") or "",
        page_number=getattr(pipeline, "page_number", None),
        selected_text=getattr(pipeline, "selected_text", "") or "",
        selected_file_ids=list(getattr(pipeline, "selected_file_ids", None) or []),
        graph_context=getattr(pipeline, "graph_context", None) or {},
        visual_generator_backend=str(
            getattr(pipeline, "visual_generator_backend", "") or ""
        ).strip(),
        vlm_generator=getattr(pipeline, "vlm_generator", None),
    )
