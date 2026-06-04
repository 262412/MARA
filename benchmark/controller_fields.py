from __future__ import annotations

from typing import Any


def controller_config_kwargs(config_getter) -> dict[str, Any]:
    return {
        "controller_mode": config_getter("controller_mode"),
        "route_policy": config_getter("route_policy"),
        "planner_model": config_getter("planner_model"),
        "allowed_routes": config_getter("allowed_routes"),
        "verification_mode": config_getter("verification_mode"),
    }


def controller_response_kwargs(response: Any) -> dict[str, Any]:
    return {
        "controller_trace": list(getattr(response, "controller_trace", []) or []),
        "controller_decision": dict(getattr(response, "controller_decision", {}) or {}),
        "route_decision": dict(getattr(response, "route_decision", {}) or {}),
        "retrieve_decision": dict(getattr(response, "retrieve_decision", {}) or {}),
        "verify_decision": dict(getattr(response, "verify_decision", {}) or {}),
        "guardrail_decision": dict(getattr(response, "guardrail_decision", {}) or {}),
        "evidence_bundle": dict(getattr(response, "evidence_bundle", {}) or {}),
    }


def controller_prediction_kwargs(prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        "controller_trace": list(prediction.get("controller_trace") or []),
        "controller_decision": dict(prediction.get("controller_decision") or {}),
        "route_decision": dict(prediction.get("route_decision") or {}),
        "retrieve_decision": dict(prediction.get("retrieve_decision") or {}),
        "verify_decision": dict(prediction.get("verify_decision") or {}),
        "guardrail_decision": dict(prediction.get("guardrail_decision") or {}),
        "evidence_bundle": dict(prediction.get("evidence_bundle") or {}),
    }
