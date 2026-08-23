from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
)
from .mara_semantic_proposition_stages import ParsedSemanticStage, proposal_stage


def repair_deterministic_rejection(
    context: Any,
    proposal: ParsedSemanticStage,
    audit: ParsedSemanticStage,
    diagnostics: dict[str, Any],
    initial_result: Any,
    *,
    reason: str,
    audit_transaction: Callable[..., Any],
    repair_debug: Callable[..., dict[str, Any] | None],
) -> Any:
    """Rebuild a deterministic rejection and run a complete fresh audit."""

    transition = _begin_repair(diagnostics, reason)
    prompt = _deterministic_rebuild_prompt(context.proposal_prompt, reason)
    if prompt is None:
        transition["outcome"] = "rebuild_prompt_bound_exceeded"
        return initial_result
    repaired = proposal_stage(
        context.proposal_llm,
        prompt,
        packed=context.packed,
        slots=context.slots,
        model=context.proposal_model,
        seed=context.seed + 20,
    )
    diagnostics["proof_rebuild_count"] = (
        int(diagnostics.get("proof_rebuild_count") or 0) + 1
    )
    if repaired.value is None:
        transition["outcome"] = "rebuild_failed"
        return replace(
            initial_result,
            proposal_call_count=proposal.call_count + repaired.call_count,
        )
    repaired_result = audit_transaction(
        replace(
            context,
            seed=context.seed + 20,
            attempt_namespace="deterministic_repair",
        ),
        repaired,
        diagnostics,
        allow_proof_repair=False,
    )
    diagnostics["proof_reaudit_count"] = (
        int(diagnostics.get("proof_reaudit_count") or 0) + 1
    )
    diagnostics["full_reaudit"] = True
    transition["outcome"] = (
        "verified" if repaired_result.status == "parsed" else "rejected"
    )
    return replace(
        repaired_result,
        proposal_call_count=proposal.call_count + repaired_result.proposal_call_count,
        audit_call_count=audit.call_count + repaired_result.audit_call_count,
        debug_trace=repair_debug(
            initial_result,
            repaired_result.debug_trace,
            transition,
            repaired.value,
            "rebuilt",
        ),
    )


def _begin_repair(
    diagnostics: dict[str, Any],
    reason: str,
) -> dict[str, Any]:
    transition = {
        "from": "runtime_contract",
        "to": "proof_repair",
        "reason": reason,
        "outcome": "rebuild_required",
    }
    diagnostics.setdefault("recovery_transitions", []).append(transition)
    for key in (
        "runtime_contract_rejection_count",
        "audit_verified_but_runtime_rejected_count",
        "proof_repair_count",
    ):
        diagnostics[key] = int(diagnostics.get(key) or 0) + 1
    return transition


def _deterministic_rebuild_prompt(prompt: str, reason: str) -> str | None:
    instruction = (
        "\n\nRUNTIME PROOF REPAIR: deterministic validation rejected the "
        f"audited conclusion ({reason}). Rebuild the proof and polarity from the "
        "canonical spans. Do not repeat the rejected conclusion. Return "
        "insufficient_evidence unless the rebuilt atomic proof or genuine "
        "conjunction satisfies every required slot."
    )
    if len(prompt) + len(instruction) > (
        SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS
    ):
        return None
    return prompt + instruction
