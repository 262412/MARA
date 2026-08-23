from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.candidate_verification_policy import CANDIDATE_VERIFICATION_CONTRACT

from .mara_candidate_unknown_audit import (
    UNKNOWN_AUDIT_MAX_TOKENS,
    candidate_unknown_audit_attestation,
    candidate_unknown_audit_prompt,
    candidate_unknown_audit_rejection_reason,
)
from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS,
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    semantic_entailment_audit_prompt,
    semantic_entailment_rejection_reason,
)
from .mara_semantic_proposition_stages import (
    ParsedSemanticStage,
    audit_diagnostics,
    candidate_unknown_audit_stage,
    invalid_response_reason,
)
from .mara_semantic_transaction_support import (
    bind_semantic_runtime_fields,
    transaction_debug,
    transaction_result,
)

_CANDIDATES = {"yes", "no", "unanswerable"}
_VERDICTS = {"yes", "no", "insufficient_evidence"}


def candidate_bound_audit(
    candidate: str,
    verdict: str,
    *,
    candidate_status: str = "",
) -> dict[str, Any]:
    """Audit only the supplied candidate against the verifier's verdict."""

    candidate = str(candidate or "").strip().casefold()
    verdict = str(verdict or "").strip().casefold()
    expected_status = _candidate_status(candidate, verdict)
    supplied_status = str(candidate_status or "").strip().casefold()
    status = expected_status
    classification = _classification(candidate, verdict)
    valid = (
        candidate in _CANDIDATES
        and verdict in _VERDICTS
        and (not supplied_status or supplied_status == expected_status)
    )
    return {
        "contract_id": "candidate_verifier_audit.v2",
        "status": "passed" if valid else "failed",
        "mode": "candidate_bound_audit",
        "audited_candidate": candidate,
        "audited_verdict": verdict,
        "audited_judgment": status,
        "classification": classification,
        "replacement_candidate_allowed": False,
        "reason": classification,
    }


def candidate_bound_response(
    response: dict[str, Any],
    candidate: str,
) -> dict[str, Any]:
    bounded = deepcopy(response)
    candidate = str(candidate or "").strip().casefold()
    verdict = str(bounded.get("verdict") or "").strip().casefold()
    status = _candidate_status(candidate, verdict)
    existing_audit = bounded.get("candidate_verification_audit")
    existing_audit = existing_audit if isinstance(existing_audit, dict) else {}
    if _candidate_audit_matches(existing_audit, candidate, verdict):
        candidate_audit = deepcopy(existing_audit)
    else:
        candidate_audit = candidate_bound_audit(
            candidate,
            verdict,
            candidate_status=status,
        )
        if verdict == "insufficient_evidence":
            candidate_audit.update(
                {
                    "status": "failed",
                    "mode": "candidate_bound_unknown_audit",
                    "classification": "unknown",
                    "reason": "candidate_unknown_audit_missing",
                }
            )
    bounded.update(
        candidate_verification_contract=CANDIDATE_VERIFICATION_CONTRACT,
        verifier_input_candidate=candidate,
        candidate_verification_status=status,
        replacement_candidate_allowed=False,
        candidate_verification_audit=candidate_audit,
        explicit_contradiction=verdict == "no",
        candidate_verifier_disagreement=status == "contradicted",
        unknown=verdict == "insufficient_evidence",
    )
    return bounded


def candidate_bound_insufficient_result(
    context: Any,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    *,
    candidate: str,
) -> Any:
    bind_semantic_runtime_fields(proposal.value or {}, context)
    value = proposal.value or {}
    assessment = value.get("unknown_assessment")
    assessment = assessment if isinstance(assessment, dict) else {}
    try:
        audit_prompt, audited_conclusion = candidate_unknown_audit_prompt(
            context.proposition,
            candidate,
            assessment,
        )
    except ValueError:
        diagnostics.update(
            {
                "audit_status": "failed",
                "audit_reason": "candidate_unknown_audit_prompt_bound_exceeded",
            }
        )
        return transaction_result(
            None,
            "failed",
            "candidate_unknown_audit_prompt_bound_exceeded",
            diagnostics,
            proposal_calls=proposal.call_count,
            debug_trace=transaction_debug(context, proposal, None),
        )
    if not audited_conclusion:
        return _candidate_unknown_precondition_failure(
            context,
            proposal,
            diagnostics,
            "candidate_unknown_typed_conclusion_missing",
        )
    if not assessment.get("reviewed_evidence"):
        return _candidate_unknown_precondition_failure(
            context,
            proposal,
            diagnostics,
            "candidate_unknown_reviewed_evidence_missing",
        )
    audit = candidate_unknown_audit_stage(
        context.audit_llm,
        audit_prompt,
        candidate=candidate,
        seed=context.seed + 1,
    )
    diagnostics.update(audit_diagnostics(audit, model=context.audit_model))
    diagnostics["audit_contract_id"] = "candidate_verifier_audit.v2"
    rejection_reason = candidate_unknown_audit_stage_rejection_reason(audit)
    debug_trace = transaction_debug(context, proposal, audit)
    if rejection_reason:
        diagnostics.update(
            {"audit_status": "rejected", "audit_reason": rejection_reason}
        )
        return transaction_result(
            None,
            "failed",
            rejection_reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            audit_calls=audit.call_count,
            debug_trace=debug_trace,
        )
    return _candidate_unknown_success(
        proposal,
        audit,
        diagnostics,
        candidate=candidate,
        audited_conclusion=audited_conclusion,
        assessment=assessment,
        debug_trace=debug_trace,
    )


def _candidate_unknown_success(
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    *,
    candidate: str,
    audited_conclusion: dict[str, Any],
    assessment: dict[str, Any],
    debug_trace: dict[str, Any] | None,
) -> Any:
    assert audit.value is not None
    value = proposal.value or {}
    candidate_audit = candidate_unknown_audit_attestation(
        audit.value,
        typed_conclusion_value=audited_conclusion,
        unknown_assessment=assessment,
    )
    value.update(
        audited_typed_conclusion=audited_conclusion,
        candidate_verification_audit=candidate_audit,
    )
    value = candidate_bound_response(value, candidate)
    diagnostics.update(
        {
            "audit_status": "candidate_bound",
            "audit_reason": str(candidate_audit.get("reason") or "unknown"),
            "audited_typed_conclusion": deepcopy(audited_conclusion),
            "candidate_verification_audit": deepcopy(candidate_audit),
            "unknown_assessment": deepcopy(assessment),
        }
    )
    return transaction_result(
        value,
        "parsed",
        "strict_schema_and_candidate_audit",
        diagnostics,
        proposal_calls=proposal.call_count,
        audit_calls=audit.call_count,
        debug_trace=debug_trace,
    )


def candidate_bound_audit_prompt(candidate: str, verdict: str) -> str:
    return (
        "/no_think\nCANDIDATE-BOUND VERIFIER AUDIT:\n"
        f"ORIGINAL CANDIDATE: {candidate}\n"
        f"VERIFIER VERDICT: {verdict}\n\n"
        "Audit only the relationship between this original candidate and this "
        "verifier verdict. Do not answer the question, infer a replacement, "
        "reverse either value, or use outside evidence. An insufficient_evidence "
        "verdict is an uncertainty judgment, not a replacement answer. Return "
        "the required audit JSON with no premise checks and all relationship "
        "checks true only when this supplied pair is internally consistent."
    )


def bind_candidate_audit_prompt(prompt: str, candidate: str, verdict: str) -> str:
    bound = (
        f"{prompt}\n\nREAD-ONLY CANDIDATE BINDING:\n"
        f"original_candidate={str(candidate or '').strip().casefold()}\n"
        f"verifier_judgment={str(verdict or '').strip().casefold()}\n"
        "Audit only the supplied original candidate and verifier judgment. "
        "Do not answer the question, emit a replacement candidate or verdict, "
        "reverse either value, or use proof repair to change the original "
        "candidate."
    )
    if len(bound) > SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS:
        raise ValueError("Candidate-bound audit prompt exceeded its bound.")
    return bound


def candidate_bound_semantic_audit_prompt(
    context: Any,
    conclusion: Any,
    value: dict[str, Any],
) -> str:
    prompt = semantic_entailment_audit_prompt(
        context.proposition,
        conclusion,
        str(value.get("proof_mode") or ""),
        value.get("premises") or [],
    )
    return bind_candidate_audit_prompt(
        prompt,
        candidate_from_prompt(context.proposal_prompt),
        str(value.get("verdict") or ""),
    )


def candidate_bound_audit_rejection_reason(audit: ParsedSemanticStage) -> str:
    if audit.provider_failure_reason:
        return audit.provider_failure_reason
    if audit.value is None:
        return invalid_response_reason(
            audit.response,
            max_tokens=SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
            invalid_reason="invalid_candidate_bound_audit_json",
        )
    return semantic_entailment_rejection_reason(audit.value)


def candidate_unknown_audit_stage_rejection_reason(
    audit: ParsedSemanticStage,
) -> str:
    if audit.provider_failure_reason:
        return audit.provider_failure_reason
    if audit.value is None:
        return invalid_response_reason(
            audit.response,
            max_tokens=UNKNOWN_AUDIT_MAX_TOKENS,
            invalid_reason="invalid_candidate_bound_unknown_audit_json",
        )
    return candidate_unknown_audit_rejection_reason(audit.value)


def candidate_from_prompt(prompt: str) -> str:
    marker = "STRUCTURED CANDIDATE TO VERIFY:\n"
    if marker not in prompt:
        return ""
    candidate = prompt.split(marker, 1)[1].split("\n\n", 1)[0].strip()
    return candidate.casefold()


def _candidate_status(candidate: str, verdict: str) -> str:
    if candidate == "unanswerable":
        if verdict == "insufficient_evidence":
            return "supported"
        if verdict in {"yes", "no"}:
            return "contradicted"
        return "unknown"
    if candidate in {"yes", "no"} and verdict == candidate:
        return "supported"
    if verdict in {"yes", "no"}:
        return "contradicted"
    return "unknown"


def _classification(candidate: str, verdict: str) -> str:
    if candidate not in _CANDIDATES or verdict not in _VERDICTS:
        return "unknown"
    if verdict == "insufficient_evidence":
        return "unknown"
    if candidate == verdict:
        return "supported"
    return "explicit_contradiction"


def _candidate_audit_matches(
    audit: dict[str, Any],
    candidate: str,
    verdict: str,
) -> bool:
    return bool(
        audit
        and audit.get("audited_candidate") == candidate
        and audit.get("audited_verdict") == verdict
        and audit.get("replacement_candidate_allowed") is False
        and audit.get("status") in {"passed", "failed"}
    )


def _candidate_unknown_precondition_failure(
    context: Any,
    proposal: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    reason: str,
) -> Any:
    diagnostics.update({"audit_status": "failed", "audit_reason": reason})
    return transaction_result(
        None,
        "failed",
        reason,
        diagnostics,
        proposal_calls=proposal.call_count,
        debug_trace=transaction_debug(context, proposal, None),
    )
