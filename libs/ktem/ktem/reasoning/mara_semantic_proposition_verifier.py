from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.semantic_evidence_set_authority import PropositionVerifier

from .mara_qasper_semantic_pack import (
    qasper_canonical_evidence_plans,
    qasper_canonical_selector_bindings,
)
from .mara_semantic_candidate_policy import candidate_bound_response
from .mara_semantic_contract_probe import (
    ControlledContractProbeIdentityError,
    controlled_contract_probe_proposal,
)
from .mara_semantic_proposition_contract import insufficient_semantic_result
from .mara_semantic_proposition_debug import (
    SemanticPropositionDebugRecorder,
    semantic_proposition_debug_enabled,
)
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS,
    SemanticPropositionEvidencePacking,
    semantic_proposition_verifier_prompt,
)
from .mara_semantic_proposition_trace import candidate_verification_trace_status
from .mara_semantic_proposition_trace import record_verifier_trace as _trace
from .mara_semantic_proposition_transaction import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    run_semantic_proposition_transaction,
)
from .mara_semantic_runtime_repair import reject_runtime_contract_without_reverify
from .mara_semantic_verifier_context import answering_llm as _answering_llm
from .mara_semantic_verifier_context import (
    auditor_semantic_pack_identity as _auditor_semantic_pack_identity,
)
from .mara_semantic_verifier_context import candidate_context as _candidate_context
from .mara_semantic_verifier_context import (
    execution_identity_free_diagnostics as _execution_identity_free_diagnostics,
)
from .mara_semantic_verifier_context import (
    execution_identity_free_semantic_judgment as _execution_identity_free_judgment,
)
from .mara_semantic_verifier_context import model_name as _model_name
from .mara_semantic_verifier_context import (
    rebind_cached_semantic_diagnostics as _rebind_cached_semantic_diagnostics,
)
from .mara_semantic_verifier_context import (
    rebind_cached_semantic_judgment as _rebind_cached_semantic_judgment,
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
        pack_failure_reason = context["pack_failure_reason"]
        if pack_failure_reason:
            _record_pack_failure(self, bundle, context)
            return None
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
        cached = _rebind_cached_semantic_judgment(
            self.cache[cache_key],
            bundle=bundle,
            packing=packing,
        )
        diagnostics = _rebind_cached_semantic_diagnostics(
            self.cache_diagnostics.get(cache_key, {}),
            bundle=bundle,
            packing=packing,
        )
        auditor_pack_identity = _auditor_semantic_pack_identity(cached)
        if auditor_pack_identity:
            diagnostics["auditor_semantic_pack_identity"] = auditor_pack_identity
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
            candidate_verification_status=candidate_verification_trace_status(
                cached,
                diagnostics,
                audit_call_count=0,
            ),
            cache_hit=True,
            cache_source="route_local_semantic_pack",
            cache_source_event_index=self.debug_recorder.cache_event_indices.get(
                cache_key
            ),
            **diagnostics,
        )
        return deepcopy(cached)


def _record_pack_failure(
    verifier: Any,
    bundle: EvidenceBundle,
    context: dict[str, Any],
) -> None:
    _trace(
        verifier,
        bundle,
        "failed",
        context["pack_failure_reason"],
        context["packing"],
        context["slots"],
        context["model"],
        context["seed"],
        candidate_label=context["candidate"],
        candidate_verification_status="pre_audit_failed",
        audit_status="not_started",
        verifier_execution_status="not_started",
        auditor_execution_status="not_started",
        canonical_pack_continuity_status="failed",
    )


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
        prompt = semantic_proposition_verifier_prompt(
            question,
            slots,
            packed,
            candidate=candidate,
        )
        return controlled_contract_probe_proposal(
            prompt,
            bundle=bundle,
            packing=packing,
            slots=slots,
            candidate=candidate,
        )
    except ControlledContractProbeIdentityError:
        _prompt_failure(
            verifier,
            bundle,
            question,
            packing,
            slots,
            cache_key,
            model,
            seed,
            candidate,
            reason="controlled_payload_schema_parser_identity_failed",
        )
        return None
    except ValueError:
        _prompt_failure(
            verifier,
            bundle,
            question,
            packing,
            slots,
            cache_key,
            model,
            seed,
            candidate,
            reason="prompt_bound_exceeded",
        )
        return None


def _prompt_failure(
    verifier: Any,
    bundle: EvidenceBundle,
    question: str,
    packing: SemanticPropositionEvidencePacking,
    slots: list[dict[str, str]],
    cache_key: str,
    model: str,
    seed: int,
    candidate: str,
    *,
    reason: str,
) -> None:
    verifier.cache[cache_key] = None
    verifier.failure_reasons[cache_key] = reason
    verifier.debug_recorder.record_pre_model(
        "prompt_rejected",
        cache_key,
        question,
        packing,
        slots,
        reason=reason,
    )
    _trace(
        verifier,
        bundle,
        "failed",
        reason,
        packing,
        slots,
        model,
        seed,
        candidate_label=candidate,
        candidate_verification_status="pre_audit_failed",
        audit_status="not_started",
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
        canonical_span_universe_digest=str(
            identity.get("canonical_span_universe_digest") or ""
        ),
        candidate_transaction_id=str(identity.get("candidate_transaction_id") or ""),
        allowed_proposition_slot_bindings=(
            qasper_canonical_selector_bindings(packing.records) or None
        ),
        allowed_proposition_evidence_plans=qasper_canonical_evidence_plans(bundle),
        capture_debug_trace=verifier.debug_recorder.enabled,
        transaction_id=transaction_id,
        attempt_namespace="initial",
    )
    return reject_runtime_contract_without_reverify(
        outcome,
        request=request,
        question=question,
        bundle=bundle,
        packing=packing,
        slots=slots,
        release_mode=verifier.release_mode,
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
    verifier.cache[cache_key] = _execution_identity_free_judgment(parsed)
    verifier.cache_diagnostics[cache_key] = _execution_identity_free_diagnostics(
        diagnostics
    )
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
    candidate_verification_status = candidate_verification_trace_status(
        parsed,
        diagnostics,
        audit_call_count=outcome.audit_call_count,
    )
    auditor_pack_identity = _auditor_semantic_pack_identity(parsed)
    if auditor_pack_identity:
        diagnostics["auditor_semantic_pack_identity"] = auditor_pack_identity
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
        candidate_verification_status=candidate_verification_status,
        **diagnostics,
    )
    return deepcopy(parsed)
