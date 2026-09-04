from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any

from .controller import RetrieveDecision
from .evidence import EvidenceBundle
from .execution_models import GenerateFn, RouteExecutionResult
from .pipeline_stage_timings import PipelineStageTimings
from .qasper_semantic_pack_contract import QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY
from .route_budget import run_blocking_route_stage
from .route_selection import ControllerDecision


@dataclass(frozen=True)
class _CandidateState:
    semantic_digest: str
    span_digest: str
    transaction_id: str
    generation_sequence: int


def regenerate_qasper_candidate(
    request: Any,
    initial_result: RouteExecutionResult,
    decision: ControllerDecision,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    candidate_answer: str,
    generate: GenerateFn | None,
    recovery_trace: list[dict[str, Any]],
    terminal_event: dict[str, Any],
    timings: PipelineStageTimings,
) -> tuple[EvidenceBundle, str, RouteExecutionResult | None]:
    if (
        not _candidate_transaction_required(
            request,
            initial_result.evidence_bundle,
        )
        or retrieve_decision.status != "good"
    ):
        return bundle, candidate_answer, None
    old_state, reason = _candidate_state(initial_result.evidence_bundle)
    if old_state is None:
        return _stopped(
            bundle,
            candidate_answer,
            initial_result,
            recovery_trace,
            terminal_event,
            reason=reason,
        )
    if generate is None:
        return _stopped(
            bundle,
            candidate_answer,
            initial_result,
            recovery_trace,
            terminal_event,
            reason="candidate_regeneration_not_configured",
        )
    candidate_bundle, regenerated, new_state, reason = _next_candidate_transaction(
        request,
        decision,
        bundle,
        generate,
        timings,
        old_state,
    )
    if not regenerated or new_state is None:
        return _stopped(
            bundle,
            candidate_answer,
            initial_result,
            recovery_trace,
            terminal_event,
            reason=reason or "candidate_regeneration_failed",
        )
    _record_candidate_transition(
        terminal_event,
        old_state,
        new_state,
        candidate_before=candidate_answer,
        candidate_after=str(regenerated),
    )
    stop_reason = _candidate_adoption_stop_reason(old_state, new_state)
    if stop_reason:
        return _stopped(
            bundle,
            candidate_answer,
            initial_result,
            recovery_trace,
            terminal_event,
            reason=stop_reason,
        )
    terminal_event.update(
        recovery_action="new_candidate_transaction",
        canonical_semantic_pack_changed=True,
    )
    request.route_last_evidence_bundle = candidate_bundle
    return candidate_bundle, str(regenerated), None


def _next_candidate_transaction(
    request: Any,
    decision: ControllerDecision,
    bundle: EvidenceBundle,
    generate: GenerateFn,
    timings: PipelineStageTimings,
    old_state: _CandidateState,
) -> tuple[EvidenceBundle, str, _CandidateState | None, str]:
    candidate_bundle = _candidate_bundle_for_next_generation(bundle, old_state)
    regenerated = _generate_candidate_transaction(
        request,
        decision,
        candidate_bundle,
        generate,
        timings,
    )
    new_state, reason = _candidate_state(
        candidate_bundle,
        expected_sequence=old_state.generation_sequence + 1,
        expected_predecessor=old_state.transaction_id,
    )
    return candidate_bundle, regenerated, new_state, reason


def _generate_candidate_transaction(
    request: Any,
    decision: ControllerDecision,
    bundle: EvidenceBundle,
    generate: GenerateFn,
    timings: PipelineStageTimings,
) -> str:
    return timings.measure(
        "generation_seconds",
        run_blocking_route_stage,
        request,
        "candidate_regeneration",
        generate,
        request,
        decision,
        bundle,
        configured_timeout_seconds=getattr(request, "generation_timeout_seconds", None),
    )


def _candidate_state(
    bundle: EvidenceBundle,
    *,
    expected_sequence: int | None = None,
    expected_predecessor: str | None = None,
) -> tuple[_CandidateState | None, str]:
    pack = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    trace = bundle.metadata.get("qasper_candidate_generation")
    if not isinstance(pack, dict) or not isinstance(trace, dict):
        return None, "canonical_semantic_pack_missing_before_recovery"
    sequence = trace.get("generation_sequence", 0)
    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        return None, "candidate_generation_sequence_invalid"
    predecessor = str(trace.get("predecessor_transaction_id") or "")
    if expected_sequence is not None and (
        sequence != expected_sequence or predecessor != str(expected_predecessor or "")
    ):
        return None, "candidate_transaction_identity_invalid_after_recovery"
    if not _pack_trace_identity_valid(trace, pack):
        suffix = (
            "after_recovery" if expected_sequence is not None else "before_recovery"
        )
        return None, f"candidate_transaction_identity_invalid_{suffix}"
    return (
        _CandidateState(
            semantic_digest=str(pack["semantic_pack_digest"]),
            span_digest=str(pack["span_universe_digest"]),
            transaction_id=str(pack["candidate_transaction_id"]),
            generation_sequence=sequence,
        ),
        "",
    )


def _pack_trace_identity_valid(
    trace: dict[str, Any],
    pack: dict[str, Any],
) -> bool:
    transaction_id = str(pack.get("candidate_transaction_id") or "")
    semantic_digest = str(pack.get("semantic_pack_digest") or "")
    span_digest = str(pack.get("span_universe_digest") or "")
    return bool(
        transaction_id
        and semantic_digest
        and span_digest
        and trace.get("transaction_id") == transaction_id
        and trace.get("canonical_pack_candidate_transaction_id") == transaction_id
        and trace.get("canonical_semantic_pack_digest") == semantic_digest
        and trace.get("canonical_span_universe_digest") == span_digest
    )


def _candidate_bundle_for_next_generation(
    bundle: EvidenceBundle,
    old_state: _CandidateState,
) -> EvidenceBundle:
    candidate_bundle = deepcopy(bundle)
    candidate_bundle.metadata["qasper_candidate_generation_sequence"] = (
        old_state.generation_sequence + 1
    )
    candidate_bundle.metadata[
        "qasper_candidate_predecessor_transaction_id"
    ] = old_state.transaction_id
    return candidate_bundle


def _candidate_adoption_stop_reason(
    old_state: _CandidateState,
    new_state: _CandidateState,
) -> str:
    if (
        new_state.semantic_digest == old_state.semantic_digest
        and new_state.span_digest == old_state.span_digest
    ):
        return "canonical_semantic_pack_unchanged"
    if new_state.transaction_id == old_state.transaction_id:
        return "candidate_transaction_not_advanced"
    return ""


def _record_candidate_transition(
    event: dict[str, Any],
    old_state: _CandidateState,
    new_state: _CandidateState,
    *,
    candidate_before: str,
    candidate_after: str,
) -> None:
    event.update(
        candidate_answer_before=candidate_before,
        candidate_answer_after=candidate_after,
        candidate_changed=candidate_after != candidate_before,
        candidate_transaction_id_before=old_state.transaction_id,
        candidate_transaction_id_after=new_state.transaction_id,
        candidate_transaction_changed=(
            new_state.transaction_id != old_state.transaction_id
        ),
        canonical_semantic_pack_digest_before=old_state.semantic_digest,
        canonical_semantic_pack_digest_after=new_state.semantic_digest,
        canonical_span_universe_digest_before=old_state.span_digest,
        canonical_span_universe_digest_after=new_state.span_digest,
    )


def _stopped(
    bundle: EvidenceBundle,
    candidate_answer: str,
    initial_result: RouteExecutionResult,
    recovery_trace: list[dict[str, Any]],
    terminal_event: dict[str, Any],
    *,
    reason: str,
) -> tuple[EvidenceBundle, str, RouteExecutionResult]:
    terminal_event.update(
        recovery_action="stop_without_reverify",
        stop_reason=reason,
        authority_changed=False,
        canonical_semantic_pack_changed=False,
    )
    stopped = replace(
        initial_result,
        controller_trace=[*initial_result.controller_trace, *recovery_trace],
    )
    return bundle, candidate_answer, stopped


def _candidate_transaction_required(request: Any, bundle: EvidenceBundle) -> bool:
    domain = str(getattr(request, "verification_domain", "") or "").casefold()
    if domain != "qasper" and not domain.startswith("qasper_"):
        return False
    trace = bundle.metadata.get("qasper_candidate_generation")
    pack = bundle.metadata.get(QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY)
    return isinstance(pack, dict) or (
        isinstance(trace, dict)
        and trace.get("contract_id") == "qasper_typed_candidate_generation.v2"
    )
