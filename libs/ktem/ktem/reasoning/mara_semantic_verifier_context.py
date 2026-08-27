from __future__ import annotations

from dataclasses import replace
from typing import Any

from ktem.docqa.boolean_candidate_authority import structured_boolean_candidate_label
from ktem.docqa.evidence_schema import EvidenceBundle

from .mara_qasper_candidate import qasper_typed_candidate_request
from .mara_qasper_semantic_pack import (
    load_qasper_canonical_semantic_pack,
    qasper_canonical_span_universe_digest,
)
from .mara_semantic_candidate_policy import CANDIDATE_VERIFICATION_CONTRACT
from .mara_semantic_local_consistency import (
    DETERMINISTIC_LOCAL_PREMISE_CONSISTENCY_CONTRACT,
)
from .mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)
from .mara_semantic_proposition_trace import (
    SEMANTIC_PROPOSITION_VERIFIER_SEED,
    digest,
    semantic_transaction_identity,
)


def candidate_context(
    verifier: Any,
    request: Any,
    question: str,
    answer: str,
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    candidate = structured_boolean_candidate_label(answer)
    slots = required_semantic_proposition_slots(request)
    candidate_trace = bundle.metadata.get("qasper_candidate_generation")
    candidate_trace = candidate_trace if isinstance(candidate_trace, dict) else {}
    candidate_transaction_id = str(candidate_trace.get("transaction_id") or "")
    packing, pack_failure_reason = _candidate_packing(
        request,
        question,
        slots,
        bundle,
        candidate_transaction_id,
    )
    seed = verifier_seed(request)
    proposal_model = model_name(verifier.llm)
    audit_model = model_name(verifier.audit_llm)
    identity = semantic_transaction_identity(
        request,
        bundle,
        question=question,
        candidate=candidate,
        semantic_pack_digest=packing.semantic_pack_digest,
        seed=seed,
    )
    identity.update(
        candidate_transaction_id=candidate_transaction_id,
        canonical_span_universe_digest=(
            qasper_canonical_span_universe_digest(packing.records)
            if packing.records
            else ""
        ),
        canonical_pack_continuity_status=(
            "failed" if pack_failure_reason else "preserved"
        ),
    )
    bundle.metadata["semantic_candidate_transaction_identity"] = identity
    return {
        "candidate": candidate,
        "slots": slots,
        "packing": packing,
        "seed": seed,
        "model": proposal_model,
        "cache_key": semantic_cache_key(
            packing.semantic_pack_digest,
            candidate=candidate,
            proposal_model=proposal_model,
            audit_model=audit_model,
            seed=seed,
            release_mode=verifier.release_mode,
        ),
        "pack_failure_reason": pack_failure_reason,
    }


def _candidate_packing(
    request: Any,
    question: str,
    slots: list[dict[str, str]],
    bundle: EvidenceBundle,
    candidate_transaction_id: str,
) -> tuple[Any, str]:
    if not qasper_typed_candidate_request(request):
        return pack_semantic_proposition_evidence(request, question, slots, bundle), ""
    packing, reason = load_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        candidate_transaction_id=candidate_transaction_id,
    )
    if packing is not None:
        return packing, reason
    diagnostic = pack_semantic_proposition_evidence(request, question, slots, bundle)
    raw_pack = bundle.metadata.get("qasper_canonical_semantic_pack")
    raw_pack = raw_pack if isinstance(raw_pack, dict) else {}
    return (
        replace(
            diagnostic,
            records=[],
            estimated_input_tokens=0,
            semantic_pack_digest=str(raw_pack.get("semantic_pack_digest") or ""),
        ),
        reason,
    )


def auditor_semantic_pack_identity(
    response: dict[str, Any] | None,
) -> dict[str, Any]:
    value = response or {}
    audit = (
        value.get("candidate_verification_audit")
        if value.get("verdict") == "insufficient_evidence"
        else value.get("entailment_audit")
    )
    audit = audit if isinstance(audit, dict) else {}
    identity = audit.get("semantic_pack_identity")
    return dict(identity) if isinstance(identity, dict) else {}


def answering_llm(pipeline: Any) -> Any | None:
    answering_pipeline = getattr(pipeline, "answering_pipeline", None)
    llm = getattr(answering_pipeline, "llm", None)
    return llm if callable(llm) else None


def verifier_seed(request: Any) -> int:
    seed = getattr(request, "generation_seed", None)
    return SEMANTIC_PROPOSITION_VERIFIER_SEED if seed is None else int(seed)


def semantic_cache_key(
    semantic_pack_digest: str,
    *,
    candidate: str,
    proposal_model: str,
    audit_model: str,
    seed: int,
    release_mode: bool,
) -> str:
    payload = {
        "semantic_pack_digest": semantic_pack_digest,
        "candidate": candidate,
        "candidate_contract": CANDIDATE_VERIFICATION_CONTRACT,
        "proposal_model": proposal_model,
        "audit_model": audit_model,
        "seed": seed,
        "release_mode": release_mode,
        "proposal_contract": "semantic_proposition_verdict.v4",
        "audit_contract": "semantic_entailment_audit.v3",
        "local_premise_consistency_contract": (
            DETERMINISTIC_LOCAL_PREMISE_CONSISTENCY_CONTRACT
        ),
        "proof_repair_policy": "state_change_only_reaudit.v3",
        "runtime_repair_policy": "stop_without_semantic_state_change.v1",
        "polarity_check_contract": "polarity_contradiction_check.v1",
    }
    return digest(payload)


def model_name(llm: Any) -> str:
    for key in ("model_name", "model", "model_id"):
        value = str(getattr(llm, key, "") or "").strip()
        if value:
            return value
    return f"{type(llm).__module__}.{type(llm).__name__}"
