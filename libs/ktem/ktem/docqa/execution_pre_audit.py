from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from .controller import VerifyDecision
from .evidence_schema import EvidenceBundle

GuardrailFactory = Callable[[str, str, str], Any]


def qasper_typed_candidate_request(request: Any | None) -> bool:
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


def qasper_pre_audit_failure_reason(
    request: Any | None,
    bundle: EvidenceBundle,
) -> str:
    """Return an upstream candidate failure without classifying it as unknown."""

    if not qasper_typed_candidate_request(request):
        return ""
    generation = bundle.metadata.get("qasper_candidate_generation")
    if (
        isinstance(generation, dict)
        and generation.get("status") == "failed"
        and not str(
            generation.get("verifier_input_candidate")
            if "verifier_input_candidate" in generation
            else generation.get("typed_candidate") or ""
        ).strip()
    ):
        return str(
            generation.get("failure_reason")
            or generation.get("raw_candidate_failure_reason")
            or "qasper_candidate_generation_failed"
        )
    trace = bundle.metadata.get("semantic_proposition_verifier")
    if not isinstance(trace, dict):
        return ""
    audit = trace.get("candidate_verification_audit")
    if not (
        trace.get("candidate_verification_status") == "pre_audit_failed"
        and trace.get("audit_status") == "not_started"
        and trace.get("audit_model_call_count") == 0
        and isinstance(audit, dict)
        and audit.get("status") == "not_started"
        and audit.get("classification") == "pre_audit_failed"
    ):
        return ""
    return str(
        trace.get("reason")
        or trace.get("parse_failure_reason")
        or trace.get("initial_parse_failure_reason")
        or "qasper_candidate_pre_audit_failed"
    )


def qasper_pre_audit_verify_decision(
    request: Any,
    bundle: EvidenceBundle,
    verify_decision: VerifyDecision,
) -> VerifyDecision:
    reason = qasper_pre_audit_failure_reason(request, bundle)
    if not reason:
        return verify_decision
    return replace(
        verify_decision,
        status="execution_failed",
        reason=reason,
        action="error",
        unsupported_claims=[],
        unknown_claims=[],
        claim_results=[],
    )


def qasper_pre_audit_failure_result(
    request: Any,
    trace_prefix: list[dict[str, Any]] | None,
    reason: str,
    *,
    guardrail_factory: GuardrailFactory,
    abstain_message: str,
) -> tuple[str, VerifyDecision, Any, list[dict[str, Any]]]:
    verify_decision = VerifyDecision(
        mode=_verification_mode(request),
        status="execution_failed",
        reason=reason,
        action="error",
        verifier_candidate_status="pre_audit_failed",
    )
    trace = [
        *list(trace_prefix or []),
        {
            "stage": "terminal_outcome",
            "outcome": "execution_failed",
            "reason": reason,
            "failure_type": "qasper_candidate_pre_audit_failed",
            "candidate_verification_status": "pre_audit_failed",
            "audit_status": "not_started",
            "audit_model_call_count": 0,
        },
    ]
    return (
        abstain_message,
        verify_decision,
        guardrail_factory("execution_failed", "error", reason),
        trace,
    )


def _verification_mode(request: Any) -> str:
    mode = str(getattr(request, "verification_mode", None) or "off").strip().lower()
    return mode if mode in {"off", "light", "strict"} else "off"
