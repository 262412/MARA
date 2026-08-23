from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.semantic_evidence_set_authority import PropositionVerifier
from ktem.docqa.boolean_candidate_authority import structured_boolean_candidate_label

from .mara_semantic_local_consistency import (
    DETERMINISTIC_LOCAL_PREMISE_CONSISTENCY_CONTRACT,
)
from .mara_semantic_proposition_contract import insufficient_semantic_result
from .mara_semantic_candidate_policy import (
    CANDIDATE_VERIFICATION_CONTRACT,
    candidate_bound_response,
)
from .mara_semantic_proposition_debug import (
    SemanticPropositionDebugRecorder,
    semantic_proposition_debug_enabled,
)
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS,
    SemanticPropositionEvidencePacking,
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
    semantic_proposition_verifier_prompt,
)
from .mara_semantic_proposition_transaction import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    run_semantic_proposition_transaction,
)
from .mara_semantic_runtime_repair import repair_runtime_contract_rejection
from .mara_semantic_proposition_trace import (
    SEMANTIC_PROPOSITION_VERIFIER_SEED,
    digest,
    record_trace,
    semantic_transaction_identity,
)

__all__ = [
    "SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS",
    "SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS",
    "SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS",
    "build_semantic_proposition_verifier",
]


def build_semantic_proposition_verifier(
    pipeline: Any,
    *,
    audit_llm: Any | None = None,
) -> PropositionVerifier | None:
    """Build one cached semantic verifier for a controller-route execution."""

    llm = _answering_llm(pipeline)
    if llm is None:
        return None
    configured_auditor = getattr(pipeline, "semantic_entailment_auditor_llm", None)
    return _SemanticPropositionVerifier(
        llm,
        audit_llm or configured_auditor or llm,
        debug_trace=semantic_proposition_debug_enabled(pipeline),
        release_mode=bool(
            getattr(pipeline, "semantic_proposition_release_mode", False)
        ),
    )


class _SemanticPropositionVerifier:
    def __init__(
        self,
        llm: Any,
        audit_llm: Any,
        *,
        debug_trace: bool,
        release_mode: bool,
    ) -> None:
        self.llm = llm
        self.audit_llm = audit_llm
        self.debug_recorder = SemanticPropositionDebugRecorder(debug_trace)
        self.release_mode = release_mode
        self.cache: dict[str, dict[str, Any] | None] = {}
        self.cache_diagnostics: dict[str, dict[str, Any]] = {}
        self.failure_reasons: dict[str, str] = {}
        self.actual_model_call_count = 0
        self.proposal_model_call_count = 0
        self.audit_model_call_count = 0

    def __call__(
        self,
        request: Any,
        question: str,
        answer: str,
        bundle: EvidenceBundle,
    ) -> dict[str, Any] | None:
        context = _candidate_context(self, request, question, answer, bundle)
        candidate = context["candidate"]
        slots = context["slots"]
        packing = context["packing"]
        packed = packing.records
        seed = context["seed"]
        model = context["model"]
        cache_key = context["cache_key"]
        if not candidate:
            _trace(
                self,
                bundle,
                "skipped",
                "structured_candidate_invalid",
                packing,
                slots,
                model,
                seed,
                candidate_label="",
                candidate_verification_status="unknown",
            )
            return None
        if not slots or not packed:
            return _skipped_response(
                self, bundle, question, packing, slots, model, seed, candidate
            )
        prompt = _candidate_prompt_or_none(
            self,
            bundle,
            question,
            packed,
            slots,
            packing,
            cache_key,
            model,
            seed,
            candidate,
        )
        if prompt is None:
            return None
        if cache_key in self.cache:
            return self._cached_response(
                bundle,
                cache_key,
                question,
                packing,
                slots,
                model,
                seed,
                candidate,
                len(prompt),
            )
        return _model_response(
            self,
            request,
            bundle,
            cache_key,
            question,
            prompt,
            packing,
            slots,
            model,
            seed,
            candidate,
        )

    def _cached_response(
        self,
        bundle: EvidenceBundle,
        cache_key: str,
        question: str,
        packing: SemanticPropositionEvidencePacking,
        slots: list[dict[str, str]],
        model: str,
        seed: int,
        candidate: str,
        prompt_chars: int,
    ) -> dict[str, Any] | None:
        cached = self.cache[cache_key]
        diagnostics = self.cache_diagnostics.get(cache_key, {})
        self.debug_recorder.record_cache_reuse(
            cache_key,
            question,
            packing,
            slots,
            cached=cached,
            diagnostics=diagnostics,
            failure_reason=self.failure_reasons.get(
                cache_key, "cached_provider_call_failed"
            ),
        )
        _trace(
            self,
            bundle,
            "cache_hit" if cached is not None else "cached_failure",
            (
                "evidence_signature_reused"
                if cached is not None
                else self.failure_reasons.get(cache_key, "cached_provider_call_failed")
            ),
            packing,
            slots,
            model,
            seed,
            prompt_chars=prompt_chars,
            verdict=str((cached or {}).get("verdict") or ""),
            candidate_label=candidate,
            candidate_verification_status=str(
                (cached or {}).get("candidate_verification_status") or "unknown"
            ),
            cache_hit=True,
            cache_source="route_local_semantic_pack",
            cache_source_event_index=self.debug_recorder.cache_event_indices.get(
                cache_key
            ),
            **diagnostics,
        )
        return deepcopy(cached)


def _candidate_context(
    verifier: Any,
    request: Any,
    question: str,
    answer: str,
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    candidate = structured_boolean_candidate_label(answer)
    slots = required_semantic_proposition_slots(request)
    packing = pack_semantic_proposition_evidence(request, question, slots, bundle)
    seed = _verifier_seed(request)
    model = _model_name(verifier.llm)
    audit_model = _model_name(verifier.audit_llm)
    bundle.metadata["semantic_candidate_transaction_identity"] = (
        semantic_transaction_identity(
            request,
            bundle,
            question=question,
            candidate=candidate,
            semantic_pack_digest=packing.semantic_pack_digest,
            seed=seed,
        )
    )
    return {
        "candidate": candidate,
        "slots": slots,
        "packing": packing,
        "seed": seed,
        "model": model,
        "cache_key": _semantic_cache_key(
            packing.semantic_pack_digest,
            candidate=candidate,
            proposal_model=model,
            audit_model=audit_model,
            seed=seed,
            release_mode=verifier.release_mode,
        ),
    }


def _candidate_prompt_or_none(
    verifier: Any,
    bundle: EvidenceBundle,
    question: str,
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    packing: SemanticPropositionEvidencePacking,
    cache_key: str,
    model: str,
    seed: int,
    candidate: str,
) -> str | None:
    try:
        return semantic_proposition_verifier_prompt(
            question,
            slots,
            packed,
            candidate=candidate,
        )
    except ValueError:
        verifier.cache[cache_key] = None
        verifier.failure_reasons[cache_key] = "prompt_bound_exceeded"
        verifier.debug_recorder.record_pre_model(
            "prompt_rejected",
            cache_key,
            question,
            packing,
            slots,
            reason="prompt_bound_exceeded",
        )
        _trace(
            verifier,
            bundle,
            "failed",
            "prompt_bound_exceeded",
            packing,
            slots,
            model,
            seed,
            candidate_label=candidate,
            candidate_verification_status="unknown",
        )
        return None


def _skipped_response(
    verifier: Any,
    bundle: EvidenceBundle,
    question: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    model: str,
    seed: int,
    candidate: str,
) -> dict[str, Any]:
    reason = "required_slots_missing" if not slots else "no_canonical_evidence_items"
    verifier.debug_recorder.record_pre_model(
        "skipped", "", question, packing, slots, reason=reason
    )
    response = candidate_bound_response(
        insufficient_semantic_result(model, seed, question), candidate
    )
    _trace(
        verifier,
        bundle,
        "skipped",
        reason,
        packing,
        slots,
        model,
        seed,
        candidate_label=candidate,
        candidate_verification_status=str(
            response.get("candidate_verification_status") or "unknown"
        ),
    )
    return response


def _model_response(
    verifier: Any,
    request: Any,
    bundle: EvidenceBundle,
    cache_key: str,
    question: str,
    prompt: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    model: str,
    seed: int,
    candidate: str,
) -> dict[str, Any] | None:
    outcome = _run_model_transaction(
        verifier,
        request,
        bundle,
        question,
        prompt,
        packing,
        slots,
        model,
        seed,
    )
    return _store_model_response(
        verifier,
        outcome,
        bundle,
        cache_key,
        question,
        prompt,
        packing,
        slots,
        model,
        seed,
        candidate,
    )


def _run_model_transaction(
    verifier: Any,
    request: Any,
    bundle: EvidenceBundle,
    question: str,
    prompt: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    model: str,
    seed: int,
) -> Any:
    identity = bundle.metadata.get("semantic_candidate_transaction_identity")
    identity = identity if isinstance(identity, dict) else {}
    transaction_id = str(identity.get("transaction_id") or "")
    outcome = run_semantic_proposition_transaction(
        verifier.llm,
        verifier.audit_llm,
        prompt,
        question=question,
        packed=packing.records,
        slots=slots,
        proposal_model=model,
        audit_model=_model_name(verifier.audit_llm),
        seed=seed,
        release_mode=verifier.release_mode,
        semantic_pack_digest=packing.semantic_pack_digest,
        capture_debug_trace=verifier.debug_recorder.enabled,
        transaction_id=transaction_id,
        attempt_namespace="initial",
    )
    return repair_runtime_contract_rejection(
        outcome,
        request=request,
        question=question,
        bundle=bundle,
        proposal_llm=verifier.llm,
        audit_llm=verifier.audit_llm,
        prompt=prompt,
        packing=packing,
        slots=slots,
        proposal_model=model,
        audit_model=_model_name(verifier.audit_llm),
        seed=seed,
        release_mode=verifier.release_mode,
        capture_debug_trace=verifier.debug_recorder.enabled,
        transaction_id=transaction_id,
    )


def _store_model_response(
    verifier: Any,
    outcome: Any,
    bundle: EvidenceBundle,
    cache_key: str,
    question: str,
    prompt: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    model: str,
    seed: int,
    candidate: str,
) -> dict[str, Any] | None:
    verifier.proposal_model_call_count += outcome.proposal_call_count
    verifier.audit_model_call_count += outcome.audit_call_count
    verifier.actual_model_call_count += (
        outcome.proposal_call_count + outcome.audit_call_count
    )
    parsed = (
        candidate_bound_response(outcome.value, candidate) if outcome.value else None
    )
    diagnostics = outcome.diagnostics
    verifier.cache[cache_key] = deepcopy(parsed)
    verifier.cache_diagnostics[cache_key] = deepcopy(diagnostics)
    if parsed is None:
        verifier.failure_reasons[cache_key] = outcome.reason
    verifier.debug_recorder.record_model_transaction(
        cache_key,
        question,
        packing,
        slots,
        status=outcome.status,
        reason=outcome.reason,
        verdict=str((parsed or {}).get("verdict") or ""),
        diagnostics=diagnostics,
        transaction=outcome.debug_trace,
    )
    _trace(
        verifier,
        bundle,
        outcome.status,
        outcome.reason,
        packing,
        slots,
        model,
        seed,
        prompt_chars=len(prompt),
        verdict=str((parsed or {}).get("verdict") or ""),
        candidate_label=candidate,
        candidate_verification_status=str(
            (parsed or {}).get("candidate_verification_status") or "unknown"
        ),
        **diagnostics,
    )
    return deepcopy(parsed)


def _trace(
    verifier: Any,
    bundle: EvidenceBundle,
    status: str,
    reason: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    model: str,
    seed: int,
    *,
    prompt_chars: int = 0,
    verdict: str = "",
    cache_hit: bool = False,
    cache_source: str = "model_transaction",
    **diagnostics: Any,
) -> None:
    record_trace(
        bundle,
        status=status,
        reason=reason,
        packing=packing,
        slots=slots,
        model=model,
        seed=seed,
        actual_model_call_count=verifier.actual_model_call_count,
        proposal_model_call_count=verifier.proposal_model_call_count,
        audit_model_call_count=verifier.audit_model_call_count,
        prompt_chars=prompt_chars,
        verdict=verdict,
        cache_hit=cache_hit,
        cache_source=cache_source,
        debug_trace=verifier.debug_recorder.snapshot(),
        release_mode=verifier.release_mode,
        **diagnostics,
    )


def _answering_llm(pipeline: Any) -> Any | None:
    answering_pipeline = getattr(pipeline, "answering_pipeline", None)
    llm = getattr(answering_pipeline, "llm", None)
    return llm if callable(llm) else None


def _verifier_seed(request: Any) -> int:
    seed = getattr(request, "generation_seed", None)
    return SEMANTIC_PROPOSITION_VERIFIER_SEED if seed is None else int(seed)


def _semantic_cache_key(
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
        "proposal_contract": "semantic_proposition_verdict.v3",
        "audit_contract": "semantic_entailment_audit.v2",
        "local_premise_consistency_contract": (
            DETERMINISTIC_LOCAL_PREMISE_CONSISTENCY_CONTRACT
        ),
        "proof_repair_policy": "full_rebuild_and_reaudit.v2",
        "polarity_check_contract": "polarity_contradiction_check.v1",
    }
    return digest(payload)


def _model_name(llm: Any) -> str:
    for key in ("model_name", "model", "model_id"):
        value = str(getattr(llm, key, "") or "").strip()
        if value:
            return value
    return f"{type(llm).__module__}.{type(llm).__name__}"
