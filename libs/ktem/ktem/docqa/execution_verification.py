from __future__ import annotations

from typing import Any, Callable

from .claim_aggregation import aggregate_answer_claims
from .claim_revision import revise_to_supported_claims
from .controller import RetrieveDecision, VerifyDecision
from .evidence_identity import identity_of
from .evidence_schema import EvidenceBundle
from .evidence_text import extract_final_answer_text
from .pipeline_stage_timings import PipelineStageTimings

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
            verify_decision = timings.measure(
                "verification_seconds",
                _empty_answer_verify_decision,
                request,
                bundle,
            )
            return (
                abstain_message,
                verify_decision,
                verification_guardrail(
                    verify_decision,
                    request,
                    guardrail_factory=guardrail_factory,
                ),
                list(trace_prefix or []),
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
    trace = [
        *list(trace_prefix or []),
        {"stage": "claim_aggregation", **aggregation_trace},
    ]
    verify_decision = _timed_verify(
        timings,
        verify,
        request,
        retrieve_decision,
        bundle,
        answer,
    )
    if verify_decision.action == "revise" and rewrite is not None:
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
    if verify_decision.action == "revise":
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
    guardrail = timings.measure(
        "finalization_seconds",
        verification_guardrail,
        verify_decision,
        request,
        guardrail_factory=guardrail_factory,
    )
    return (
        abstain_message if guardrail.action == "abstain" else answer,
        verify_decision,
        guardrail,
        trace,
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
        rewrite,
        request,
        decision,
        bundle,
        answer,
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
        verify,
        request,
        retrieve_decision,
        bundle,
        answer,
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
