from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from typing import Any

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.semantic_evidence_set_authority import PropositionVerifier

from kotaemon.base import HumanMessage, SystemMessage

from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS,
    SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT,
    SemanticPropositionEvidencePacking,
    pack_semantic_proposition_evidence,
    semantic_proposition_verifier_prompt,
)
from .mara_semantic_proposition_schema import (
    parse_semantic_proposition_result,
    semantic_proposition_response_format,
)

SEMANTIC_PROPOSITION_VERIFIER_RUNTIME_CONTRACT = (
    "semantic_proposition_verifier_runtime.v1"
)
SEMANTIC_PROPOSITION_VERIFIER_SEED = 20260724
SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS = 512

LOGGER = logging.getLogger(__name__)


def build_semantic_proposition_verifier(pipeline: Any) -> PropositionVerifier | None:
    """Build one cached semantic verifier for a controller-route execution."""

    llm = _answering_llm(pipeline)
    return _SemanticPropositionVerifier(llm) if llm is not None else None


class _SemanticPropositionVerifier:
    def __init__(self, llm: Any) -> None:
        self.llm = llm
        self.cache: dict[str, dict[str, Any] | None] = {}
        self.failure_reasons: dict[str, str] = {}
        self.actual_model_call_count = 0

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
            return self._skipped_response(bundle, packing, slots, model, seed)
        try:
            prompt = semantic_proposition_verifier_prompt(question, slots, packed)
        except ValueError:
            cache_key = _cache_key(question, slots, packed)
            self.cache[cache_key] = None
            self.failure_reasons[cache_key] = "prompt_bound_exceeded"
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
                bundle, cache_key, packing, slots, model, seed, len(prompt)
            )
        response, failure_reason = self._model_response(prompt, packed, slots, seed)
        if response is None:
            self.cache[cache_key] = None
            self.failure_reasons[cache_key] = failure_reason
            self._trace(
                bundle,
                "failed",
                failure_reason,
                packing,
                slots,
                model,
                seed,
                prompt_chars=len(prompt),
            )
            return None
        parsed = parse_semantic_proposition_result(
            _response_text(response),
            packed=packed,
            slot_ids={value["slot_id"] for value in slots},
            model=model,
            seed=seed,
        )
        self.cache[cache_key] = deepcopy(parsed)
        if parsed is None:
            self.failure_reasons[cache_key] = "invalid_model_json"
        self._trace(
            bundle,
            "parsed" if parsed is not None else "failed",
            "strict_schema_parsed" if parsed is not None else "invalid_model_json",
            packing,
            slots,
            model,
            seed,
            prompt_chars=len(prompt),
            verdict=str((parsed or {}).get("verdict") or ""),
        )
        return deepcopy(parsed)

    def _model_response(
        self,
        prompt: str,
        packed: list[dict[str, str]],
        slots: list[dict[str, str]],
        seed: int,
    ) -> tuple[Any | None, str]:
        self.actual_model_call_count += 1
        try:
            return (
                self.llm(
                    [
                        SystemMessage(
                            content=SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT
                        ),
                        HumanMessage(content=prompt),
                    ],
                    max_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                    response_format=semantic_proposition_response_format(
                        [value["label"] for value in packed],
                        [value["slot_id"] for value in slots],
                    ),
                    temperature=0,
                    top_p=1,
                    seed=seed,
                ),
                "",
            )
        except Exception as exc:
            LOGGER.exception("Semantic proposition verifier model call failed")
            return None, _provider_failure_reason(exc)

    def _cached_response(
        self,
        bundle: EvidenceBundle,
        cache_key: str,
        packing: SemanticPropositionEvidencePacking,
        slots: list[dict[str, str]],
        model: str,
        seed: int,
        prompt_chars: int,
    ) -> dict[str, Any] | None:
        cached = self.cache[cache_key]
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
        )
        return deepcopy(cached)

    def _skipped_response(
        self,
        bundle: EvidenceBundle,
        packing: SemanticPropositionEvidencePacking,
        slots: list[dict[str, str]],
        model: str,
        seed: int,
    ) -> dict[str, Any]:
        self._trace(
            bundle,
            "skipped",
            "required_slots_missing" if not slots else "no_canonical_evidence_items",
            packing,
            slots,
            model,
            seed,
        )
        return _insufficient_result(model, seed)

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
            prompt_chars=prompt_chars,
            verdict=verdict,
            cache_hit=cache_hit,
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


def _insufficient_result(model: str, seed: int) -> dict[str, Any]:
    return {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "verdict": "insufficient_evidence",
        "support_mode": "evidence_set",
        "jointly_complete": False,
        "each_premise_required": False,
        "premises": [],
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": model,
            "seed": seed,
        },
    }


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


def _provider_failure_reason(exc: Exception) -> str:
    message = str(exc).casefold()
    if "maximum context length" in message or "context length exceeded" in message:
        return "provider_context_length_exceeded"
    if "grammar error" in message or "unimplemented keys" in message:
        return "provider_response_schema_unsupported"
    return "provider_call_failed"


def _response_text(response: Any) -> str:
    return str(
        getattr(response, "text", "") or getattr(response, "content", "") or response
    )


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
    prompt_chars: int = 0,
    verdict: str = "",
    cache_hit: bool = False,
) -> None:
    bundle.metadata["semantic_proposition_verifier"] = {
        "contract_id": SEMANTIC_PROPOSITION_VERIFIER_RUNTIME_CONTRACT,
        "status": status,
        "reason": reason,
        "model": model,
        "seed": seed,
        "cache_hit": cache_hit,
        "actual_model_call_count": actual_model_call_count,
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
    }
