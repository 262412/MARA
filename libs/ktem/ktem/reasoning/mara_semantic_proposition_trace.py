from __future__ import annotations

import hashlib
import json
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle

from .mara_semantic_candidate_policy import candidate_bound_audit
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SemanticPropositionEvidencePacking,
    SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS,
)
from .mara_semantic_proposition_transaction import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
)

SEMANTIC_PROPOSITION_VERIFIER_RUNTIME_CONTRACT = (
    "semantic_proposition_verifier_runtime.v2"
)
SEMANTIC_PROPOSITION_VERIFIER_SEED = 20260724


def semantic_transaction_identity(
    request: Any,
    bundle: EvidenceBundle,
    *,
    question: str,
    candidate: str,
    semantic_pack_digest: str,
    seed: int,
) -> dict[str, Any]:
    context = dict(getattr(request, "trace_context", {}) or {})
    group_id = str(context.get("trace_group_id") or "")
    if not group_id:
        group_id = digest(
            {
                "dataset": str(getattr(request, "dataset_family", "") or ""),
                "question": question,
            }
        )
    benchmark_route_id = str(
        context.get("benchmark_route_id")
        or getattr(request, "benchmark_route_id", "")
        or ""
    )
    input_digest = digest(
        {
            "candidate": candidate,
            "question": question,
            "semantic_pack_digest": semantic_pack_digest,
            "seed": seed,
        }
    )
    transaction_id = digest(
        {
            "trace_group_id": group_id,
            "benchmark_route_id": benchmark_route_id,
            "route": str(bundle.route or ""),
            "stage": "candidate_verification",
            "input_digest": input_digest,
        }
    )
    return {
        "trace_group_id": group_id,
        "benchmark_route_id": benchmark_route_id,
        "internal_route": str(bundle.route or ""),
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:initial:proposal:1",
        "auditor_attempt_id": f"{transaction_id}:initial:audit:1",
        "effective_seed": seed,
        "input_digest": input_digest,
    }


def digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_trace(
    bundle: EvidenceBundle,
    *,
    status: str,
    reason: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    model: str,
    seed: int,
    actual_model_call_count: int,
    proposal_model_call_count: int,
    audit_model_call_count: int,
    prompt_chars: int = 0,
    verdict: str = "",
    cache_hit: bool = False,
    cache_source: str = "model_transaction",
    debug_trace: dict[str, Any] | None = None,
    **diagnostics: Any,
) -> None:
    identity = bundle.metadata.get("semantic_candidate_transaction_identity")
    identity = identity if isinstance(identity, dict) else {}
    trace = _base_trace(
        bundle,
        identity=identity,
        status=status,
        reason=reason,
        packing=packing,
        slots=slots,
        model=model,
        seed=seed,
        actual_model_call_count=actual_model_call_count,
        proposal_model_call_count=proposal_model_call_count,
        audit_model_call_count=audit_model_call_count,
        prompt_chars=prompt_chars,
        verdict=verdict,
        cache_hit=cache_hit,
        cache_source=cache_source,
        diagnostics=diagnostics,
    )
    trace["candidate_verification_audit"] = _candidate_audit(
        trace, status, verdict, reason
    )
    relation = str(trace.get("candidate_verification_status") or "unknown")
    trace.update(
        {
            "explicit_contradiction": relation == "contradicted",
            "candidate_verifier_disagreement": relation == "contradicted",
            "unknown": relation == "unknown",
        }
    )
    trace["output_digest"] = digest(
        {
            "status": status,
            "reason": reason,
            "verdict": verdict,
            "candidate_verification_status": relation,
            "candidate_verification_audit": trace["candidate_verification_audit"],
            "replacement_candidate_allowed": False,
            "explicit_contradiction": trace["explicit_contradiction"],
            "candidate_verifier_disagreement": trace["candidate_verifier_disagreement"],
            "unknown": trace["unknown"],
        }
    )
    if debug_trace is not None:
        trace["debug_trace"] = debug_trace
    bundle.metadata["semantic_proposition_verifier"] = trace


def _base_trace(
    bundle: EvidenceBundle,
    *,
    identity: dict[str, Any],
    status: str,
    reason: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    model: str,
    seed: int,
    actual_model_call_count: int,
    proposal_model_call_count: int,
    audit_model_call_count: int,
    prompt_chars: int,
    verdict: str,
    cache_hit: bool,
    cache_source: str,
    diagnostics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_id": SEMANTIC_PROPOSITION_VERIFIER_RUNTIME_CONTRACT,
        "status": status,
        "reason": reason,
        "model": model,
        "seed": seed,
        "cache_hit": cache_hit,
        "cache_source": cache_source,
        "internal_route": str(bundle.route or ""),
        "benchmark_route_id": str(identity.get("benchmark_route_id") or ""),
        "semantic_pack_digest": packing.semantic_pack_digest,
        "question_proposition": dict(packing.question_proposition),
        "question_proposition_resolution": dict(
            packing.question_proposition_resolution
        ),
        "release_mode": bool(diagnostics.get("release_mode", False)),
        "actual_model_call_count": actual_model_call_count,
        "proposal_model_call_count": proposal_model_call_count,
        "audit_model_call_count": audit_model_call_count,
        "available_evidence_count": len(bundle.items),
        "packed_evidence_count": len(packing.records),
        "evidence_item_char_limit": packing.item_char_limit,
        "estimated_input_token_budget": packing.input_token_budget,
        "estimated_input_tokens": packing.estimated_input_tokens,
        "minimum_model_context_tokens": SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS,
        "packed_evidence_chars": packing.packed_chars,
        "dropped_evidence_count": packing.dropped_count,
        "truncated_evidence_count": packing.truncated_count,
        "required_slot_count": len(slots),
        "prompt_chars": prompt_chars,
        "max_prompt_chars": SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
        "max_output_tokens": SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
        "verdict": verdict,
        "evidence_label_map": {
            value["label"]: value["evidence_id"] for value in packing.records
        },
        **diagnostics,
        **identity,
        "replacement_candidate_allowed": False,
    }


def _candidate_audit(
    trace: dict[str, Any],
    status: str,
    verdict: str,
    reason: str,
) -> dict[str, Any]:
    audit_status = str(trace.get("audit_status") or "")
    candidate = str(trace.get("candidate_label") or "")
    judgment = str(trace.get("candidate_verification_status") or "unknown")
    audit = candidate_bound_audit(candidate, verdict, candidate_status=judgment)
    if status not in {"parsed", "proposition_incomplete", "skipped", "cache_hit"}:
        audit["status"] = "failed"
    if audit_status in {"failed", "rejected"}:
        audit["status"] = "failed"
    audit["reason"] = str(
        audit.get("classification") or trace.get("audit_reason") or reason
    )
    return audit
