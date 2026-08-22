from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.semantic_evidence_set_authority import PropositionVerifier

from .mara_semantic_proposition_debug import (
    SemanticPropositionDebugRecorder,
    semantic_proposition_debug_enabled,
)
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS,
    SemanticPropositionEvidencePacking,
    pack_semantic_proposition_evidence,
    semantic_proposition_verifier_prompt,
)
from .mara_semantic_proposition_transaction import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    insufficient_semantic_result,
    run_semantic_proposition_transaction,
)

SEMANTIC_PROPOSITION_VERIFIER_RUNTIME_CONTRACT = (
    "semantic_proposition_verifier_runtime.v1"
)
SEMANTIC_PROPOSITION_VERIFIER_SEED = 20260724


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
    )


class _SemanticPropositionVerifier:
    def __init__(self, llm: Any, audit_llm: Any, *, debug_trace: bool) -> None:
        self.llm = llm
        self.audit_llm = audit_llm
        self.debug_recorder = SemanticPropositionDebugRecorder(debug_trace)
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
        _answer: str,
        bundle: EvidenceBundle,
    ) -> dict[str, Any] | None:
        slots = _required_slots(request)
        packing = pack_semantic_proposition_evidence(
            request,
            question,
            slots,
            bundle,
        )
        packed = packing.records
        seed = _verifier_seed(request)
        model = _model_name(self.llm)
        if not slots or not packed:
            return self._skipped_response(bundle, question, packing, slots, model, seed)
        try:
            prompt = semantic_proposition_verifier_prompt(question, slots, packed)
        except ValueError:
            cache_key = _cache_key(question, slots, packed)
            self.cache[cache_key] = None
            self.failure_reasons[cache_key] = "prompt_bound_exceeded"
            self.debug_recorder.record_pre_model(
                "prompt_rejected",
                cache_key,
                question,
                packing,
                slots,
                reason="prompt_bound_exceeded",
            )
            self._trace(
                bundle,
                "failed",
                "prompt_bound_exceeded",
                packing,
                slots,
                model,
                seed,
            )
            return None
        cache_key = _cache_key(question, slots, packed)
        if cache_key in self.cache:
            return self._cached_response(
                bundle,
                cache_key,
                question,
                packing,
                slots,
                model,
                seed,
                len(prompt),
            )
        return self._model_response(
            bundle,
            cache_key,
            question,
            prompt,
            packing,
            slots,
            model,
            seed,
        )

    def _model_response(
        self,
        bundle: EvidenceBundle,
        cache_key: str,
        question: str,
        prompt: str,
        packing: SemanticPropositionEvidencePacking,
        slots: list[dict[str, str]],
        model: str,
        seed: int,
    ) -> dict[str, Any] | None:
        outcome = run_semantic_proposition_transaction(
            self.llm,
            self.audit_llm,
            prompt,
            question=question,
            packed=packing.records,
            slots=slots,
            proposal_model=model,
            audit_model=_model_name(self.audit_llm),
            seed=seed,
            capture_debug_trace=self.debug_recorder.enabled,
        )
        self.proposal_model_call_count += outcome.proposal_call_count
        self.audit_model_call_count += outcome.audit_call_count
        self.actual_model_call_count += (
            outcome.proposal_call_count + outcome.audit_call_count
        )
        parsed = outcome.value
        status = outcome.status
        reason = outcome.reason
        diagnostics = outcome.diagnostics
        self.cache[cache_key] = deepcopy(parsed)
        self.cache_diagnostics[cache_key] = deepcopy(diagnostics)
        if parsed is None:
            self.failure_reasons[cache_key] = reason
        self.debug_recorder.record_model_transaction(
            cache_key,
            question,
            packing,
            slots,
            status=status,
            reason=reason,
            verdict=str((parsed or {}).get("verdict") or ""),
            diagnostics=diagnostics,
            transaction=outcome.debug_trace,
        )
        self._trace(
            bundle,
            status,
            reason,
            packing,
            slots,
            model,
            seed,
            prompt_chars=len(prompt),
            verdict=str((parsed or {}).get("verdict") or ""),
            **diagnostics,
        )
        return deepcopy(parsed)

    def _cached_response(
        self,
        bundle: EvidenceBundle,
        cache_key: str,
        question: str,
        packing: SemanticPropositionEvidencePacking,
        slots: list[dict[str, str]],
        model: str,
        seed: int,
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
        self._trace(
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
            cache_hit=True,
            **diagnostics,
        )
        return deepcopy(cached)

    def _skipped_response(
        self,
        bundle: EvidenceBundle,
        question: str,
        packing: SemanticPropositionEvidencePacking,
        slots: list[dict[str, str]],
        model: str,
        seed: int,
    ) -> dict[str, Any]:
        reason = (
            "required_slots_missing" if not slots else "no_canonical_evidence_items"
        )
        self.debug_recorder.record_pre_model(
            "skipped",
            "",
            question,
            packing,
            slots,
            reason=reason,
        )
        self._trace(
            bundle,
            "skipped",
            reason,
            packing,
            slots,
            model,
            seed,
        )
        return insufficient_semantic_result(model, seed)

    def _trace(
        self,
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
        **diagnostics: Any,
    ) -> None:
        _record_trace(
            bundle,
            status=status,
            reason=reason,
            packing=packing,
            slots=slots,
            model=model,
            seed=seed,
            actual_model_call_count=self.actual_model_call_count,
            proposal_model_call_count=self.proposal_model_call_count,
            audit_model_call_count=self.audit_model_call_count,
            prompt_chars=prompt_chars,
            verdict=verdict,
            cache_hit=cache_hit,
            debug_trace=self.debug_recorder.snapshot(),
            **diagnostics,
        )


def _answering_llm(pipeline: Any) -> Any | None:
    answering_pipeline = getattr(pipeline, "answering_pipeline", None)
    llm = getattr(answering_pipeline, "llm", None)
    return llm if callable(llm) else None


def _required_slots(request: Any) -> list[dict[str, str]]:
    plan = getattr(request, "query_plan", None)
    raw_slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, dict)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    slots: list[dict[str, str]] = []
    for slot in raw_slots:
        required = (
            slot.get("required_for_verification", False)
            if isinstance(slot, dict)
            else getattr(slot, "required_for_verification", False)
        )
        slot_id = _slot_value(slot, "slot_id")
        if required and slot_id:
            slots.append(
                {
                    "slot_id": slot_id,
                    "description": _slot_description(slot),
                }
            )
    return slots


def _slot_value(slot: Any, key: str) -> str:
    value = slot.get(key) if isinstance(slot, dict) else getattr(slot, key, "")
    return str(value or "").strip()


def _slot_description(slot: Any) -> str:
    fields = [
        (key, _slot_value(slot, key))
        for key in ("role", "entity", "metric", "period", "statement_kind", "query")
    ]
    return "; ".join(f"{key}={value}" for key, value in fields if value)


def _cache_key(
    question: str,
    slots: list[dict[str, str]],
    packed: list[dict[str, str]],
) -> str:
    payload = {
        "question": question,
        "slot_ids": [value["slot_id"] for value in slots],
        "evidence": [
            (value["evidence_id"], value["source_id"], value["text"])
            for value in packed
        ],
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verifier_seed(request: Any) -> int:
    seed = getattr(request, "generation_seed", None)
    return SEMANTIC_PROPOSITION_VERIFIER_SEED if seed is None else int(seed)


def _model_name(llm: Any) -> str:
    for key in ("model_name", "model", "model_id"):
        value = str(getattr(llm, key, "") or "").strip()
        if value:
            return value
    return f"{type(llm).__module__}.{type(llm).__name__}"


def _record_trace(
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
    debug_trace: dict[str, Any] | None = None,
    **diagnostics: Any,
) -> None:
    trace = {
        "contract_id": SEMANTIC_PROPOSITION_VERIFIER_RUNTIME_CONTRACT,
        "status": status,
        "reason": reason,
        "model": model,
        "seed": seed,
        "cache_hit": cache_hit,
        "actual_model_call_count": actual_model_call_count,
        "proposal_model_call_count": proposal_model_call_count,
        "audit_model_call_count": audit_model_call_count,
        "available_evidence_count": len(bundle.items),
        "packed_evidence_count": len(packing.records),
        "evidence_item_char_limit": packing.item_char_limit,
        "estimated_input_token_budget": packing.input_token_budget,
        "estimated_input_tokens": packing.estimated_input_tokens,
        "minimum_model_context_tokens": (
            SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS
        ),
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
    }
    if debug_trace is not None:
        trace["debug_trace"] = debug_trace
    bundle.metadata["semantic_proposition_verifier"] = trace
