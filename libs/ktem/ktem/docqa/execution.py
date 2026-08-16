from __future__ import annotations

import logging
from typing import Any

from .controller import RetrieveDecision, VerifyDecision
from .engine_terminal_projection import (
    engine_terminal_projection as _engine_terminal_projection,
)
from .engine_terminal_projection import (
    normalized_candidate_label as _normalized_candidate_label,
)
from .evidence import EvidenceBundle
from .execution_contracts import ABSTAIN_MESSAGE
from .execution_contracts import CANONICAL_ROUTES as _CANONICAL_ROUTES
from .execution_contracts import (
    DIRECT_ANSWER_MESSAGE,
    ENGINE_TERMINAL_STATE_CONTRACT,
    RAGTRUTH_EMPTY_ANSWER,
)
from .execution_models import (
    GenerateFn,
    GuardrailDecision,
    RetrieveFn,
    RewriteFn,
    RouteExecutionResult,
)
from .execution_planning import (
    build_execution_workflow_plan as _build_execution_workflow_plan,
)
from .execution_planning import controller_decision as _controller_decision
from .execution_planning import planned_execution as _planned_execution
from .execution_recovery import (
    complete_verifier_recovery as _complete_verifier_recovery,
)
from .execution_recovery import (
    recover_after_failed_retrieval as _recover_after_failed_retrieval,
)
from .execution_recovery import (
    recover_after_failed_verification as _recover_after_failed_verification,
)
from .execution_recovery import (
    required_typed_authority_missing as _required_typed_authority_missing,
)
from .execution_recovery import (
    same_route_verifier_recovery_trace as _same_route_verifier_recovery_trace,
)
from .execution_recovery import (
    switch_after_failed_retrieval as _switch_after_failed_retrieval,
)
from .execution_recovery import (
    switch_after_failed_verification as _switch_after_failed_verification,
)
from .execution_recovery import verifier_recovery_policy as _verifier_recovery_policy
from .execution_results import deadline_exhausted_result as _deadline_exhausted_result
from .execution_results import guarded_result as _guarded_result
from .execution_results import operational_failure_result as _operational_failure_result
from .execution_results import result as _result
from .execution_results import static_result as _static_result
from .execution_results import verified_result as _verified_result
from .execution_retrieval import retrieve_and_evaluate as _retrieve_and_evaluate
from .pipeline_stage_timings import PipelineStageTimings
from .route_budget import RouteDeadlineExhausted, run_blocking_route_stage
from .route_capabilities import (
    route_switch_candidate_evaluation as _route_switch_candidate_evaluation,
)
from .route_capabilities import route_switch_candidates as _route_switch_candidates
from .route_selection import ControllerDecision

_controller_decision_from_payload = _controller_decision
LOGGER = logging.getLogger(__name__)

__all__ = [
    "ABSTAIN_MESSAGE",
    "DIRECT_ANSWER_MESSAGE",
    "ENGINE_TERMINAL_STATE_CONTRACT",
    "RAGTRUTH_EMPTY_ANSWER",
    "ControllerDecision",
    "EvidenceBundle",
    "GenerateFn",
    "GuardrailDecision",
    "RetrieveDecision",
    "RetrieveFn",
    "RewriteFn",
    "RouteExecutionResult",
    "VerifyDecision",
    "_CANONICAL_ROUTES",
    "_build_execution_workflow_plan",
    "_complete_verifier_recovery",
    "_controller_decision",
    "_controller_decision_from_payload",
    "_engine_terminal_projection",
    "_guarded_result",
    "_normalized_candidate_label",
    "_planned_execution",
    "_recover_after_failed_retrieval",
    "_recover_after_failed_verification",
    "_required_typed_authority_missing",
    "_result",
    "_retrieve_and_evaluate",
    "_route_switch_candidate_evaluation",
    "_route_switch_candidates",
    "_same_route_verifier_recovery_trace",
    "_static_result",
    "_switch_after_failed_retrieval",
    "_switch_after_failed_verification",
    "_verified_result",
    "_verifier_recovery_policy",
    "execute_controller_turn",
    "deadline_exhausted_controller_result",
]


def deadline_exhausted_controller_result(
    request: Any,
    error: RouteDeadlineExhausted,
    *,
    agent_trace: list[dict[str, Any]] | None = None,
) -> RouteExecutionResult:
    timings = PipelineStageTimings()
    decision, workflow_plan = timings.measure(
        "planning_seconds",
        _planned_execution,
        request,
        agent_trace or [],
    )
    return _deadline_exhausted_result(
        request,
        decision,
        workflow_plan,
        error,
        timings,
    )


def execute_controller_turn(
    request: Any,
    *,
    retrieve: RetrieveFn,
    generate: GenerateFn,
    rewrite: RewriteFn | None = None,
    agent_trace: list[dict[str, Any]] | None = None,
) -> RouteExecutionResult:
    timings = PipelineStageTimings()
    try:
        decision, workflow_plan = timings.measure(
            "planning_seconds",
            _planned_execution,
            request,
            agent_trace or [],
        )
    except Exception as error:
        LOGGER.exception("DocQA planning failed before terminal commit")
        return _operational_failure_result(
            request,
            None,
            {},
            error,
            "planning",
            timings,
        )
    if decision.route in {"direct_answer", "abstain"}:
        answer = (
            DIRECT_ANSWER_MESSAGE
            if decision.route == "direct_answer"
            else ABSTAIN_MESSAGE
        )
        return _static_result(request, decision, answer, workflow_plan, timings)
    try:
        return _execute_retrieval_turn(
            request,
            decision,
            workflow_plan,
            retrieve,
            generate,
            rewrite,
            timings,
        )
    except RouteDeadlineExhausted as error:
        return _deadline_exhausted_result(
            request,
            decision,
            workflow_plan,
            error,
            timings,
        )
    except Exception as error:
        LOGGER.exception("DocQA backend failed before terminal commit")
        return _operational_failure_result(
            request,
            decision,
            workflow_plan,
            error,
            "backend",
            timings,
        )


def _execute_retrieval_turn(
    request: Any,
    decision: ControllerDecision,
    workflow_plan: dict[str, Any],
    retrieve: RetrieveFn,
    generate: GenerateFn,
    rewrite: RewriteFn | None,
    timings: PipelineStageTimings,
) -> RouteExecutionResult:
    bundle, retrieve_decision = timings.measure(
        "retrieval_seconds",
        _retrieve_and_evaluate,
        request,
        decision,
        retrieve,
    )
    (
        decision,
        bundle,
        retrieve_decision,
        workflow_plan,
        route_switch_trace,
    ) = _recover_after_failed_retrieval(
        request,
        decision,
        retrieve_decision,
        bundle,
        workflow_plan,
        retrieve,
        timings,
    )
    if retrieve_decision.status != "good":
        return _guarded_result(
            request,
            decision,
            retrieve_decision,
            bundle,
            workflow_plan,
            route_switch_trace,
            timings,
        )
    answer = timings.measure(
        "generation_seconds",
        run_blocking_route_stage,
        request,
        "generation",
        generate,
        request,
        decision,
        bundle,
        configured_timeout_seconds=getattr(request, "generation_timeout_seconds", None),
    )
    initial_result = _verified_result(
        request,
        decision,
        retrieve_decision,
        bundle,
        answer,
        rewrite,
        workflow_plan,
        route_switch_trace,
        timings,
    )
    return _recover_after_failed_verification(
        request,
        initial_result,
        retrieve,
        rewrite,
        workflow_plan,
        route_switch_trace,
        timings,
    )
