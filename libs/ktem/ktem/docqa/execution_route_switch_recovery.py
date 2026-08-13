from __future__ import annotations

from typing import Any

from .controller import (
    RetrieveDecision,
    RouteDecision,
    VerifyDecision,
    evaluate_retrieval_quality,
)
from .evidence import EvidenceBundle
from .execution_models import RetrieveFn
from .execution_planning import controller_decision
from .execution_recovery_events import (
    build_retrieval_switch_event as _retrieval_switch_event,
)
from .execution_recovery_events import (
    build_verifier_switch_event as _verifier_switch_event,
)
from .execution_retrieval import retrieve_and_evaluate
from .retrieval_rounds import retrieve_for_verifier_recovery
from .route_budget import optional_stage_allowed, route_budget_metadata
from .route_capabilities import route_switch_candidate_evaluation
from .route_selection import ControllerDecision, mark_route_switch_recovery


def switch_after_failed_verification(
    request: Any,
    decision: ControllerDecision,
    failed_verification: VerifyDecision,
    failed_bundle: EvidenceBundle,
    retrieve: RetrieveFn,
) -> tuple[ControllerDecision, EvidenceBundle, RetrieveDecision, dict[str, Any]] | None:
    candidates, rejected = route_switch_candidate_evaluation(
        request,
        decision.legacy_route,
    )
    if not candidates:
        if rejected:
            failed_bundle.metadata["rejected_route_switch_candidates"] = list(rejected)
        return None
    route = candidates[0]
    switched_decision = _verifier_switch_decision(decision, route, candidates)
    recovered = retrieve_for_verifier_recovery(
        request,
        switched_decision,
        retrieve,
        failed_bundle,
        evaluate=evaluate_retrieval_quality,
        retry_reason="required_boolean_authority_missing",
    )
    if recovered is None:
        return None
    bundle, retrieve_decision, focused_query = recovered
    event = _verifier_switch_event(
        request,
        decision,
        route,
        candidates,
        focused_query,
        failed_verification,
        failed_bundle,
        bundle,
        rejected,
    )
    return switched_decision, bundle, retrieve_decision, event


def _verifier_switch_decision(
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
) -> ControllerDecision:
    switched = controller_decision(
        RouteDecision(
            route=route,
            policy="route_switch",
            controller_mode=decision.controller_mode,
            requires_retrieval=True,
            reason=(
                f"Switched from {decision.legacy_route} after required Boolean "
                "authority was not established."
            ),
        )
    )
    return mark_route_switch_recovery(
        switched,
        initial_decision=decision,
        candidates=candidates,
        override_reason="Route switch used after required Boolean authority failure.",
    )


def switch_after_failed_retrieval(
    request: Any,
    decision: ControllerDecision,
    failed_decision: RetrieveDecision,
    failed_bundle: EvidenceBundle,
    retrieve: RetrieveFn,
) -> tuple[
    ControllerDecision,
    EvidenceBundle,
    RetrieveDecision,
    list[dict[str, Any]],
] | None:
    if not optional_stage_allowed(request):
        failed_bundle.metadata.update(route_budget_metadata(request))
        failed_bundle.metadata[
            "route_switch_skipped_reason"
        ] = "insufficient_remaining_time"
        return None
    candidates, rejected = route_switch_candidate_evaluation(
        request,
        decision.legacy_route,
    )
    if rejected:
        failed_bundle.metadata["rejected_route_switch_candidates"] = list(rejected)
    attempts: list[dict[str, Any]] = []
    for attempt, route in enumerate(candidates, start=1):
        switched = _retrieval_switch_decision(decision, route, candidates)
        bundle, retrieve_decision = retrieve_and_evaluate(
            request,
            switched,
            retrieve,
            max_rounds=1,
        )
        event = _retrieval_switch_event(
            decision,
            route,
            candidates,
            failed_decision,
            failed_bundle,
            bundle,
            rejected,
        )
        if retrieve_decision.status == "good":
            event.update(
                {
                    "attempt": attempt,
                    "transition_committed": True,
                    "attempt_status": retrieve_decision.status,
                }
            )
            return switched, bundle, retrieve_decision, [*attempts, event]
        event.update(
            {
                "stage": "route_switch_attempt",
                "attempt": attempt,
                "route_switch_used": False,
                "transition_committed": False,
                "attempt_status": retrieve_decision.status,
                "attempt_reason": retrieve_decision.reason,
            }
        )
        attempts.append(event)
    if attempts:
        return decision, failed_bundle, failed_decision, attempts
    return None


def _retrieval_switch_decision(
    decision: ControllerDecision,
    route: str,
    candidates: list[str],
) -> ControllerDecision:
    switched = controller_decision(
        RouteDecision(
            route=route,
            policy="route_switch",
            controller_mode=decision.controller_mode,
            requires_retrieval=True,
            reason=f"Switched from {decision.legacy_route} after failed retrieval.",
        )
    )
    return mark_route_switch_recovery(
        switched,
        initial_decision=decision,
        candidates=candidates,
    )
