from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from .controller import RouteDecision


@dataclass(frozen=True)
class ControllerDecision:
    route: str
    legacy_route: str
    policy: str
    controller_mode: str
    requires_retrieval: bool
    reason: str
    initial_route: str = ""
    final_route: str = ""
    planner_route: str = ""
    scored_route: str = ""
    route_selection_policy: str = ""
    route_switch_used: bool = False
    routing_features: dict[str, Any] = field(default_factory=dict)
    route_scores: dict[str, Any] = field(default_factory=dict)
    route_confidences: dict[str, Any] = field(default_factory=dict)
    route_confidence_by_modality: dict[str, Any] = field(default_factory=dict)
    expected_route_quality: dict[str, Any] = field(default_factory=dict)
    expected_route_cost: dict[str, Any] = field(default_factory=dict)
    skipped_expensive_routes: list[str] = field(default_factory=list)
    cost_gate_decision: str = ""
    required_evidence_route_available: bool | None = None
    route_probe: dict[str, Any] = field(default_factory=dict)
    route_switch_candidates: list[str] = field(default_factory=list)
    override_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "route": self.route,
            "legacy_route": self.legacy_route,
            "policy": self.policy,
            "controller_mode": self.controller_mode,
            "requires_retrieval": self.requires_retrieval,
            "reason": self.reason,
        }
        if self._has_route_selection_metadata():
            payload.update(
                {
                    "initial_route": self.initial_route or self.legacy_route,
                    "final_route": self.final_route or self.legacy_route,
                    "planner_route": self.planner_route,
                    "scored_route": self.scored_route,
                    "route_selection_policy": self.route_selection_policy,
                    "route_switch_used": self.route_switch_used,
                }
            )
            _put_if_present(payload, "routing_features", self.routing_features)
            _put_if_present(payload, "route_scores", self.route_scores)
            _put_if_present(payload, "route_confidences", self.route_confidences)
            _put_if_present(
                payload,
                "route_confidence_by_modality",
                self.route_confidence_by_modality,
            )
            _put_if_present(
                payload,
                "expected_route_quality",
                self.expected_route_quality,
            )
            _put_if_present(payload, "expected_route_cost", self.expected_route_cost)
            _put_if_present(
                payload,
                "skipped_expensive_routes",
                self.skipped_expensive_routes,
            )
            _put_if_present(payload, "cost_gate_decision", self.cost_gate_decision)
            if self.required_evidence_route_available is not None:
                payload[
                    "required_evidence_route_available"
                ] = self.required_evidence_route_available
            _put_if_present(payload, "route_probe", self.route_probe)
            _put_if_present(
                payload, "route_switch_candidates", self.route_switch_candidates
            )
            _put_if_present(payload, "override_reason", self.override_reason)
        return payload

    def _has_route_selection_metadata(self) -> bool:
        return bool(
            self.route_selection_policy
            or self.route_switch_used
            or self.routing_features
            or self.route_confidences
            or self.required_evidence_route_available is not None
        )


def controller_decision_from_route(
    route_decision: RouteDecision,
    *,
    canonical_routes: dict[str, str],
    planner_payload: Any = None,
) -> ControllerDecision:
    route_metadata = _route_selection_metadata(planner_payload, route_decision.route)
    return ControllerDecision(
        route=canonical_routes[route_decision.route],
        legacy_route=route_decision.route,
        policy=route_decision.policy,
        controller_mode=route_decision.controller_mode,
        requires_retrieval=route_decision.requires_retrieval,
        reason=route_decision.reason,
        **route_metadata,
    )


def mark_route_switch_recovery(
    decision: ControllerDecision,
    *,
    initial_decision: ControllerDecision,
    candidates: list[str],
) -> ControllerDecision:
    return replace(
        decision,
        initial_route=initial_decision.initial_route or initial_decision.legacy_route,
        final_route=decision.legacy_route,
        planner_route=initial_decision.planner_route,
        scored_route=initial_decision.scored_route,
        route_selection_policy=(
            initial_decision.route_selection_policy or "route_switch_recovery"
        ),
        route_switch_used=True,
        routing_features=initial_decision.routing_features,
        route_scores=initial_decision.route_scores,
        route_confidences=initial_decision.route_confidences,
        route_confidence_by_modality=initial_decision.route_confidence_by_modality,
        expected_route_quality=initial_decision.expected_route_quality,
        expected_route_cost=initial_decision.expected_route_cost,
        skipped_expensive_routes=initial_decision.skipped_expensive_routes,
        cost_gate_decision=initial_decision.cost_gate_decision,
        required_evidence_route_available=(
            initial_decision.required_evidence_route_available
        ),
        route_probe=initial_decision.route_probe,
        route_switch_candidates=list(candidates),
        override_reason="Route switch used only after retrieval failure.",
    )


def _route_selection_metadata(
    planner_payload: Any,
    selected_route: str,
) -> dict[str, Any]:
    payload = planner_payload if isinstance(planner_payload, dict) else {}
    route_selection_policy = str(payload.get("route_selection_policy") or "").strip()
    if not route_selection_policy:
        return {
            "initial_route": selected_route,
            "final_route": selected_route,
        }
    return {
        "initial_route": str(
            payload.get("initial_route_decision")
            or payload.get("initial_route")
            or selected_route
        ),
        "final_route": selected_route,
        "planner_route": str(
            payload.get("planner_route") or payload.get("route") or ""
        ),
        "scored_route": str(payload.get("scored_route") or selected_route),
        "route_selection_policy": route_selection_policy,
        "routing_features": dict(payload.get("routing_features") or {}),
        "route_scores": dict(payload.get("route_scores") or {}),
        "route_confidences": dict(payload.get("route_confidences") or {}),
        "route_confidence_by_modality": dict(
            payload.get("route_confidence_by_modality")
            or payload.get("route_confidences")
            or {}
        ),
        "expected_route_quality": dict(payload.get("expected_route_quality") or {}),
        "expected_route_cost": dict(payload.get("expected_route_cost") or {}),
        "skipped_expensive_routes": [
            str(route)
            for route in payload.get("skipped_expensive_routes") or []
            if str(route).strip()
        ],
        "cost_gate_decision": str(payload.get("cost_gate_decision") or ""),
        "required_evidence_route_available": (
            payload.get("required_evidence_route_available")
            if isinstance(payload.get("required_evidence_route_available"), bool)
            else None
        ),
        "route_probe": dict(payload.get("route_probe") or {}),
        "override_reason": str(payload.get("override_reason") or ""),
    }


def _put_if_present(payload: dict[str, Any], key: str, value: Any) -> None:
    if value not in ({}, [], "", None):
        payload[key] = value
