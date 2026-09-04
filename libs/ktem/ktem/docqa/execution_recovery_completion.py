from __future__ import annotations

from typing import Any

from .boolean_authoritative_conflict import authoritative_conflict_complete
from .controller import RetrieveDecision
from .evidence import EvidenceBundle
from .execution_authority_policy import required_typed_authority_missing
from .execution_models import RewriteFn, RouteExecutionResult, VerifyFn
from .execution_recovery_events import (
    authority_state,
    bundle_evidence_ids,
    typed_slot_states,
)
from .execution_results import guarded_result, verified_result
from .pipeline_stage_timings import PipelineStageTimings
from .route_selection import ControllerDecision


def complete_verifier_recovery(
    request: Any,
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    candidate_answer: str,
    rewrite: RewriteFn | None,
    workflow_plan: dict[str, Any],
    trace_prefix: list[dict[str, Any]],
    timings: PipelineStageTimings,
    verify: VerifyFn,
    *,
    terminal_event: dict[str, Any],
) -> RouteExecutionResult:
    if retrieve_decision.status != "good":
        terminal_event.update(
            verification_status="not_enough_evidence",
            slot_states_after=typed_slot_states(bundle),
            recovered_evidence_ids=bundle_evidence_ids(bundle),
            authority_state_after=str(
                terminal_event.get("authority_state_before") or ""
            ),
            authority_atoms_after=list(
                terminal_event.get("authority_atoms_before") or []
            ),
            authority_changed=False,
            stop_reason="authority_recovery_exhausted",
        )
        return guarded_result(
            request,
            decision,
            retrieve_decision,
            bundle,
            workflow_plan,
            trace_prefix,
            timings,
            verify=verify,
        )
    result = verified_result(
        request,
        decision,
        retrieve_decision,
        bundle,
        candidate_answer,
        rewrite,
        workflow_plan,
        trace_prefix,
        timings,
        verify=verify,
    )
    _record_recovery_outcome(request, result, terminal_event)
    return result


def _record_recovery_outcome(
    request: Any,
    result: RouteExecutionResult,
    terminal_event: dict[str, Any],
) -> None:
    recovered = not required_typed_authority_missing(request, result.verify_decision)
    conflict_resolved = (
        result.verify_decision.status == "verified_conflict"
        and authoritative_conflict_complete(
            result.verify_decision.authoritative_conflict
        )
    )
    authority_state_after, authority_atoms_after = authority_state(
        result.verify_decision
    )
    authority_state_before = str(terminal_event.get("authority_state_before") or "")
    authority_atoms_before = list(terminal_event.get("authority_atoms_before") or [])
    candidate_before = str(terminal_event.get("candidate_answer_before") or "")
    candidate_after = str(result.answer or "")
    if conflict_resolved:
        stop_reason = "authority_conflict_resolved"
    elif recovered:
        stop_reason = "authority_recovered"
    else:
        stop_reason = "authority_recovery_exhausted"
    terminal_event.update(
        verification_status=result.verify_decision.status,
        slot_states_after=typed_slot_states(result.evidence_bundle),
        recovered_evidence_ids=bundle_evidence_ids(result.evidence_bundle),
        authority_state_after=authority_state_after,
        authority_atoms_after=authority_atoms_after,
        authority_changed=(
            authority_state_before != authority_state_after
            or authority_atoms_before != authority_atoms_after
        ),
        candidate_answer_after=candidate_after,
        candidate_changed=candidate_before.strip() != candidate_after.strip(),
        stop_reason=stop_reason,
    )
