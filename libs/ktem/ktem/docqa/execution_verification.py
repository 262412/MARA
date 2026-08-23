from __future__ import annotations

import hashlib
from typing import Any, Callable

from .boolean_evidence_scope import evidence_item_text
from .claim_aggregation import aggregate_answer_claims
from .claim_revision import revise_to_supported_claims
from .controller import RetrieveDecision, VerifyDecision
from .evidence_identity import identity_of
from .evidence_schema import EvidenceBundle
from .evidence_text import extract_final_answer_text
from .pipeline_stage_timings import PipelineStageTimings
from .qasper_answer_revision import (
    ANSWER_REVISION_CONTRACT,
    AnswerRevisionAssessment,
    assess_qasper_answer_revision,
    proposal_matches_verified_authority,
)
from .route_budget import run_blocking_route_stage
from .visual_time_series import revise_visual_time_series_answer

GuardrailFactory = Callable[[str, str, str], Any]
RewriteFn = Callable[[Any, Any, EvidenceBundle, str], str]
VerifyFn = Callable[[Any, RetrieveDecision, EvidenceBundle, str], VerifyDecision]


def verify_generated_answer(
    request: Any,
    decision: Any,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    answer: str,
    rewrite: RewriteFn | None,
    trace_prefix: list[dict[str, Any]] | None,
    timings: PipelineStageTimings,
    *,
    verify: VerifyFn,
    guardrail_factory: GuardrailFactory,
    abstain_message: str,
    ragtruth_empty_answer: str,
) -> tuple[str, VerifyDecision, Any, list[dict[str, Any]]]:
    if bundle.metadata.get("generation_backend") == "evidence_only_without_vlm":
        verify_decision = timings.measure(
            "verification_seconds",
            _evidence_only_verify_decision,
            request,
            bundle,
        )
        return (
            answer,
            verify_decision,
            verification_guardrail(
                verify_decision,
                request,
                guardrail_factory=guardrail_factory,
            ),
            list(trace_prefix or []),
        )
    if not extract_final_answer_text(answer).strip():
        if ragtruth_contract_request(request):
            bundle.metadata["task_contract_fallback"] = "ragtruth_empty_generation"
            answer = ragtruth_empty_answer
        else:
            return _handle_empty_generated_answer(
                request,
                bundle,
                answer,
                trace_prefix,
                timings,
                verify=verify,
                guardrail_factory=guardrail_factory,
                abstain_message=abstain_message,
            )
    return _verify_nonempty_answer(
        request,
        decision,
        retrieve_decision,
        bundle,
        answer,
        rewrite,
        trace_prefix,
        timings,
        verify=verify,
        guardrail_factory=guardrail_factory,
        abstain_message=abstain_message,
    )


def _typed_boolean_request(request: Any, verify: VerifyFn) -> bool:
    plan = getattr(request, "query_plan", None)
    answer_type = (
        plan.get("answer_type")
        if isinstance(plan, dict)
        else getattr(plan, "answer_type", "")
    )
    boolean_request = (
        str(answer_type or getattr(request, "task_type", "")).casefold() == "boolean"
    )
    domain = str(getattr(request, "verification_domain", "") or "").casefold()
    return boolean_request and (
        domain == "qasper"
        or domain.startswith("qasper_")
        or bool(getattr(verify, "_semantic_proposition_preflight", False))
    )


def _verify_nonempty_answer(
    request: Any,
    decision: Any,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    answer: str,
    rewrite: RewriteFn | None,
    trace_prefix: list[dict[str, Any]] | None,
    timings: PipelineStageTimings,
    *,
    verify: VerifyFn,
    guardrail_factory: GuardrailFactory,
    abstain_message: str,
) -> tuple[str, VerifyDecision, Any, list[dict[str, Any]]]:
    answer, aggregation_trace = timings.measure(
        "finalization_seconds",
        aggregate_answer_claims,
        answer,
    )
    bundle.metadata["pre_verification_answer"] = answer
    trace = [
        *list(trace_prefix or []),
        {"stage": "claim_aggregation", **aggregation_trace},
    ]
    answer, verify_decision, revision_trace = _verify_with_answer_revision(
        request,
        retrieve_decision,
        bundle,
        answer,
        verify,
        timings,
    )
    if revision_trace:
        trace.append(revision_trace)
    candidate_bound = _qasper_typed_candidate_request(request)
    if (
        verify_decision.action == "revise"
        and rewrite is not None
        and not candidate_bound
    ):
        answer, verify_decision = _rewrite_and_verify(
            request,
            decision,
            retrieve_decision,
            bundle,
            answer,
            rewrite,
            verify,
            timings,
            trace,
        )
    if verify_decision.action == "revise" and not candidate_bound:
        answer, verify_decision, revision_trace = timings.measure(
            "verification_seconds",
            revise_to_supported_claims,
            request,
            retrieve_decision,
            bundle,
            answer,
            verify_decision,
            verify=verify,
        )
        if revision_trace:
            trace.append(revision_trace)
    answer, guardrail = _finalize_nonempty_answer(
        request,
        bundle,
        answer,
        verify_decision,
        timings,
        guardrail_factory=guardrail_factory,
        abstain_message=abstain_message,
    )
    return (
        answer,
        verify_decision,
        guardrail,
        trace,
    )


def _handle_empty_generated_answer(
    request: Any,
    bundle: EvidenceBundle,
    answer: str,
    trace_prefix: list[dict[str, Any]] | None,
    timings: PipelineStageTimings,
    *,
    verify: VerifyFn,
    guardrail_factory: GuardrailFactory,
    abstain_message: str,
) -> tuple[str, VerifyDecision, Any, list[dict[str, Any]]]:
    verify_decision = timings.measure(
        "verification_seconds",
        _empty_answer_verify_decision,
        request,
        bundle,
    )
    trace = list(trace_prefix or [])
    if _typed_boolean_request(request, verify):
        bundle.metadata["typed_boolean_generation_recovery"] = (
            "empty_generation_rejected_without_verifier_call"
        )
        trace.append(
            {
                "stage": "typed_boolean_generation_recovery",
                "candidate_before": extract_final_answer_text(answer).strip(),
                "candidate_after": "",
                "reason": "empty_generation_rejected_without_verifier_call",
                "action": "fail_closed_abstention",
            }
        )
    return (
        abstain_message,
        verify_decision,
        verification_guardrail(
            verify_decision,
            request,
            guardrail_factory=guardrail_factory,
        ),
        trace,
    )


def _finalize_nonempty_answer(
    request: Any,
    bundle: EvidenceBundle,
    answer: str,
    verify_decision: VerifyDecision,
    timings: PipelineStageTimings,
    *,
    guardrail_factory: GuardrailFactory,
    abstain_message: str,
) -> tuple[str, Any]:
    answer = _verified_boolean_answer(answer, verify_decision)
    guardrail = timings.measure(
        "finalization_seconds",
        verification_guardrail,
        verify_decision,
        request,
        guardrail_factory=guardrail_factory,
    )
    bundle.metadata["pre_guardrail_answer"] = answer
    if verify_decision.status == "verified_conflict":
        answer = "unanswerable"
    elif guardrail.action == "abstain":
        answer = abstain_message
    return answer, guardrail


def _verify_with_answer_revision(
    request: Any,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    answer: str,
    verify: VerifyFn,
    timings: PipelineStageTimings,
) -> tuple[str, VerifyDecision, dict[str, Any] | None]:
    answer, visual_revision_trace = revise_visual_time_series_answer(
        request,
        bundle,
        answer,
    )
    verify_decision = _timed_verify(
        timings,
        verify,
        request,
        retrieve_decision,
        bundle,
        answer,
    )
    if _qasper_typed_candidate_request(request):
        return answer, verify_decision, visual_revision_trace
    answer, verify_decision, qasper_revision_trace = _revise_qasper_answer_relation(
        request,
        retrieve_decision,
        bundle,
        answer,
        verify_decision,
        verify,
        timings,
    )
    return (
        answer,
        verify_decision,
        qasper_revision_trace or visual_revision_trace,
    )


def _revise_qasper_answer_relation(
    request: Any,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    answer: str,
    verify_decision: VerifyDecision,
    verify: VerifyFn,
    timings: PipelineStageTimings,
) -> tuple[str, VerifyDecision, dict[str, Any] | None]:
    evidence_signature = _answer_revision_evidence_signature(bundle)
    attempted = bundle.metadata.setdefault(
        "qasper_answer_revision_attempted_evidence_signatures",
        [],
    )
    if evidence_signature in attempted:
        return answer, verify_decision, None
    assessment = assess_qasper_answer_revision(
        request,
        verify_decision,
        list(bundle.items),
    )
    if not assessment.eligible:
        return answer, verify_decision, None
    attempted.append(evidence_signature)
    proposal = assessment.proposal
    if proposal is None:
        return (
            answer,
            verify_decision,
            _answer_revision_event(
                answer,
                assessment,
                verify_decision,
                verify_decision,
                verified=False,
            ),
        )
    revised = proposal.revised_answer
    fresh = _timed_verify(
        timings,
        verify,
        request,
        retrieve_decision,
        bundle,
        revised,
    )
    verified = proposal_matches_verified_authority(proposal, fresh)
    event = _answer_revision_event(
        answer,
        assessment,
        verify_decision,
        fresh,
        verified=verified,
    )
    return (revised, fresh, event) if verified else (answer, verify_decision, event)


def _answer_revision_event(
    original_answer: str,
    assessment: AnswerRevisionAssessment,
    before: VerifyDecision,
    after: VerifyDecision,
    *,
    verified: bool,
) -> dict[str, Any]:
    proposal = assessment.proposal
    return {
        "stage": "answer_revision",
        "contract_id": ANSWER_REVISION_CONTRACT,
        "original_candidate": original_answer,
        "revised_candidate": proposal.revised_answer if proposal else "",
        "authority_evidence_id": proposal.canonical_evidence_id if proposal else "",
        "authority_evidence_ids": list(assessment.candidate_evidence_ids),
        "authority_evidence_ref": proposal.evidence_ref if proposal else "",
        "authority_span_id": proposal.span_id if proposal else "",
        "authority_quote": proposal.quote if proposal else "",
        "actor": proposal.actor if proposal else "",
        "relation": proposal.relation if proposal else "",
        "object": proposal.object if proposal else "",
        "qualifier": proposal.qualifier if proposal else "",
        "scope": proposal.scope if proposal else "",
        "revision_reason": (
            proposal.revision_reason if proposal else assessment.reason
        ),
        "ambiguity_status": assessment.ambiguity_status,
        "conflict_status": assessment.conflict_status,
        "authority_state_before": str(
            (before.typed_authority or {}).get("state") or ""
        ),
        "authority_state_after": str((after.typed_authority or {}).get("state") or ""),
        "authority_changed": verified,
        "verification_status": after.status,
        "stop_reason": (
            "answer_revision_verified"
            if verified
            else (
                "answer_revision_verification_failed"
                if proposal
                else f"answer_revision_{assessment.reason}"
            )
        ),
    }


def _answer_revision_evidence_signature(bundle: EvidenceBundle) -> str:
    authorities = sorted(
        {
            f"{identity_of(item).key}\x1f{evidence_item_text(item)}"
            for item in bundle.items
            if identity_of(item).key
        }
    )
    return hashlib.sha256("\x1e".join(authorities).encode("utf-8")).hexdigest()


def _verified_boolean_answer(answer: str, decision: VerifyDecision) -> str:
    polarity = str(getattr(decision, "canonical_answer_polarity", "") or "")
    if decision.status == "supported" and polarity in {"yes", "no"}:
        return polarity
    return answer


def _qasper_typed_candidate_request(request: Any | None) -> bool:
    if request is None:
        return False
    domain = str(getattr(request, "verification_domain", "") or "").casefold()
    origin = str(getattr(request, "origin", "") or "").casefold()
    plan = getattr(request, "query_plan", None)
    answer_type = (
        plan.get("answer_type")
        if isinstance(plan, dict)
        else getattr(plan, "answer_type", "")
    )
    answer_type = str(answer_type or getattr(request, "task_type", "")).casefold()
    return (
        origin == "benchmark"
        and (domain == "qasper" or domain.startswith("qasper_"))
        and answer_type == "boolean"
    )


def ragtruth_contract_request(request: Any | None) -> bool:
    if request is None:
        return False
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    return domain == "ragtruth"


def verification_guardrail(
    verify_decision: VerifyDecision,
    request: Any | None,
    *,
    guardrail_factory: GuardrailFactory,
) -> Any:
    if verify_decision.status in {"supported", "not_requested", "not_required"}:
        return guardrail_factory("ok", "return", verify_decision.reason)
    if verify_decision.action == "revise":
        action = "revise" if _finance_benchmark_request(request) else "abstain"
        return guardrail_factory("unsupported", action, verify_decision.reason)
    return guardrail_factory(
        verify_decision.status,
        verify_decision.action,
        verify_decision.reason,
    )


def _rewrite_and_verify(
    request: Any,
    decision: Any,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    answer: str,
    rewrite: RewriteFn,
    verify: VerifyFn,
    timings: PipelineStageTimings,
    trace: list[dict[str, Any]],
) -> tuple[str, VerifyDecision]:
    answer = timings.measure(
        "retry_seconds",
        run_blocking_route_stage,
        request,
        "answer_rewrite",
        rewrite,
        request,
        decision,
        bundle,
        answer,
        configured_timeout_seconds=getattr(request, "rewrite_timeout_seconds", None),
    )
    answer, aggregation_trace = timings.measure(
        "finalization_seconds",
        aggregate_answer_claims,
        answer,
    )
    trace.append(
        {
            "stage": "claim_aggregation",
            "rewrite": True,
            **aggregation_trace,
        }
    )
    return answer, _timed_verify(
        timings,
        verify,
        request,
        retrieve_decision,
        bundle,
        answer,
    )


def _timed_verify(
    timings: PipelineStageTimings,
    verify: VerifyFn,
    request: Any,
    retrieve_decision: RetrieveDecision,
    bundle: EvidenceBundle,
    answer: str,
) -> VerifyDecision:
    return timings.measure(
        "verification_seconds",
        run_blocking_route_stage,
        request,
        "verification",
        verify,
        request,
        retrieve_decision,
        bundle,
        answer,
        configured_timeout_seconds=getattr(
            request, "verification_timeout_seconds", None
        ),
    )


def _finance_benchmark_request(request: Any | None) -> bool:
    if request is None:
        return False
    origin = str(getattr(request, "origin", "") or "").strip().lower()
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    return origin == "benchmark" and domain in {"finance", "financial"}


def _evidence_only_verify_decision(
    request: Any,
    bundle: EvidenceBundle,
) -> VerifyDecision:
    mode = _verification_mode(request)
    return VerifyDecision(
        mode=mode,
        status="not_required",
        reason="Evidence-only visual route did not invoke a VLM generator.",
        verified_citations=_bundle_citation_ids(bundle),
    )


def _empty_answer_verify_decision(
    request: Any,
    bundle: EvidenceBundle,
) -> VerifyDecision:
    mode = _verification_mode(request)
    return VerifyDecision(
        mode=mode,
        status="not_enough_evidence",
        reason=f"{mode.title()} verification found no final answer to verify.",
        action="abstain",
        verified_citations=_bundle_citation_ids(bundle),
    )


def _verification_mode(request: Any) -> str:
    mode = str(getattr(request, "verification_mode", None) or "off").strip().lower()
    return mode if mode in {"off", "light", "strict"} else "off"


def _bundle_citation_ids(bundle: EvidenceBundle) -> list[str]:
    return list(
        dict.fromkeys(
            identity_of(item).key for item in bundle.items if identity_of(item).key
        )
    )
