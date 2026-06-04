from __future__ import annotations

import json
from typing import Any

from ktem.docqa.controller import ROUTE_EVIDENCE_TYPES, parse_planner_decision


class LLMPlanner:
    def __init__(self, planner_model: str) -> None:
        self.planner_model = planner_model

    def __call__(self, payload: dict[str, Any]) -> str:
        return _run_planner_model(payload, self.planner_model)


def planner_decision(
    understanding: dict[str, Any],
    *,
    planner: Any = None,
    planner_model: str | None = None,
    question: str = "",
    allowed_routes: Any = None,
) -> dict[str, Any]:
    if planner is not None:
        return _call_structured_planner(
            planner,
            understanding,
            planner_model=planner_model,
            question=question,
            allowed_routes=allowed_routes,
        )
    if planner_model:
        return _call_structured_planner(
            LLMPlanner(planner_model),
            understanding,
            planner_model=planner_model,
            question=question,
            allowed_routes=allowed_routes,
        )
    return _heuristic_planner_decision(understanding)


def planner_trace_payload(
    understanding: dict[str, Any],
    *,
    planner: Any = None,
    planner_model: str | None = None,
    question: str = "",
    allowed_routes: Any = None,
) -> dict[str, Any]:
    payload = {
        "event": "planner_output",
        "decision": planner_decision(
            understanding,
            planner=planner,
            planner_model=planner_model,
            question=question,
            allowed_routes=allowed_routes,
        ),
    }
    if planner_model:
        payload["planner_model"] = planner_model
    return payload


def _heuristic_planner_decision(understanding: dict[str, Any]) -> dict[str, Any]:
    task_type = str(understanding.get("task_type") or "qa")
    modalities = [
        str(modality)
        for modality in understanding.get("modalities", ["text"])
        if modality
    ]
    scope = str(understanding.get("scope") or "document")

    if task_type in {"compare", "study_guide", "summary"} and scope != "page":
        return {
            "route": "graph_global",
            "reason": "Global compare and study tasks use graph evidence.",
            "evidence_types": ["graph"],
            "verify": True,
        }
    if any(
        modality in {"figure", "slide", "table", "formula"} for modality in modalities
    ):
        return {
            "route": "hybrid",
            "reason": "Multimodal document questions use text, page-image, and element evidence.",
            "evidence_types": ["text", "page_image", "element"],
            "verify": True,
        }
    return {
        "route": "doc",
        "reason": "Document text evidence is the default retrieval route.",
        "evidence_types": ["text"],
        "verify": True,
    }


def _call_structured_planner(
    planner: Any,
    understanding: dict[str, Any],
    *,
    planner_model: str | None,
    question: str,
    allowed_routes: Any,
) -> dict[str, Any]:
    payload = {
        "question": question,
        "understanding": dict(understanding),
        "planner_model": planner_model or "",
        "allowed_routes": list(allowed_routes or []),
    }
    try:
        raw_decision = planner(payload)
    except (ImportError, RuntimeError, ValueError) as exc:
        return {
            "route": "abstain",
            "reason": f"Planner model failed; backend unavailable: {exc}",
            "planner_error": str(exc),
            "evidence_types": [],
            "verify": False,
        }
    decision = parse_planner_decision(raw_decision, allowed_routes=allowed_routes)
    return {
        "route": decision.route,
        "reason": decision.reason,
        "evidence_types": _evidence_types_for_route(decision.route),
        "verify": decision.route not in {"direct", "abstain"},
    }


def _evidence_types_for_route(route: str) -> list[str]:
    return list(ROUTE_EVIDENCE_TYPES.get(route, ["text"]))


def _run_planner_model(payload: dict[str, Any], planner_model: str) -> str:
    from kotaemon.modelcli import (
        ModelRequest,
        build_registry,
        load_runtime_config,
        run_completion,
    )

    prompt = json.dumps(payload, ensure_ascii=False, indent=2)
    request = ModelRequest(
        prompt=prompt,
        model=planner_model,
        system_prompt=(
            "Select one route for MARA DocQA. Return only JSON with route and "
            "reason. Allowed route aliases include direct, doc, visual, element, "
            "graph, hybrid, and abstain."
        ),
        temperature=0.0,
        max_tokens=300,
    )
    response = run_completion(
        build_registry(), load_runtime_config("modelcli.yml"), request
    )
    return response.text
