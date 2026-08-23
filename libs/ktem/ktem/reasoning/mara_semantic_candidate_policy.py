from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.candidate_verification_policy import CANDIDATE_VERIFICATION_CONTRACT

from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS,
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    semantic_entailment_audit_prompt,
    semantic_entailment_rejection_reason,
)
from .mara_semantic_proposition_stages import (
    ParsedSemanticStage,
    audit_diagnostics,
    audit_stage,
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
        "contract_id": "candidate_verifier_audit.v1",
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
    bounded.update(
        candidate_verification_contract=CANDIDATE_VERIFICATION_CONTRACT,
        verifier_input_candidate=candidate,
        candidate_verification_status=status,
        replacement_candidate_allowed=False,
        candidate_verification_audit=candidate_bound_audit(
            candidate,
            verdict,
            candidate_status=status,
        ),
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
    audit = audit_stage(
        context.audit_llm,
        candidate_bound_audit_prompt(candidate, "insufficient_evidence"),
        0,
        seed=context.seed + 1,
    )
    diagnostics.update(audit_diagnostics(audit, model=context.audit_model))
    rejection_reason = candidate_bound_audit_rejection_reason(audit)
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
    value = candidate_bound_response(proposal.value or {}, candidate)
    candidate_audit = dict(value["candidate_verification_audit"])
    diagnostics.update(
        {
            "audit_status": "candidate_bound",
            "audit_reason": str(candidate_audit.get("classification") or "unknown"),
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
