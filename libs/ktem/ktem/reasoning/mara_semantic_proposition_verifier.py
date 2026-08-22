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
from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_phrase_extraction import source_page_locator
from ktem.docqa.semantic_evidence_set_authority import PropositionVerifier

from kotaemon.base import HumanMessage, SystemMessage

from .mara_semantic_proposition_schema import (
    parse_semantic_proposition_result,
    semantic_proposition_response_format,
)

SEMANTIC_PROPOSITION_VERIFIER_RUNTIME_CONTRACT = (
    "semantic_proposition_verifier_runtime.v1"
)
SEMANTIC_PROPOSITION_VERIFIER_SEED = 20260724
SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS = 768
SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS = 12
SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS = 2000
SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS = 30000

LOGGER = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are a conservative document-grounded proposition verifier. Decide the "
    "complete yes/no proposition in the question from the labeled retrieved "
    "evidence excerpts only. Return yes or no only when two to four distinct "
    "premises from one source are jointly sufficient, every selected premise is "
    "necessary, and no selected premise alone establishes the complete "
    "proposition. Otherwise return insufficient_evidence. For every premise, "
    "copy one exact contiguous quote, state the proposition fragment entailed by "
    "that quote, and bind it to the verification slots it supports. Treat actor, "
    "scope, modality, comparison direction, negation, quantifiers, and time as "
    "strict. Do not use outside knowledge. Missing mentions or incomplete "
    "retrieval never prove no; an explicit negative or contradiction is required. "
    "For questions about the authors or current study, at least one premise must "
    "explicitly anchor their action. For questions about a named subject, the "
    "premise set must explicitly anchor that subject. Conflicting evidence is "
    "insufficient. Never copy the excerpt delimiters."
)


def build_semantic_proposition_verifier(pipeline: Any) -> PropositionVerifier | None:
    """Build one cached semantic verifier for a controller-route execution."""

    llm = _answering_llm(pipeline)
    return _SemanticPropositionVerifier(llm) if llm is not None else None


class _SemanticPropositionVerifier:
    def __init__(self, llm: Any) -> None:
        self.llm = llm
        self.cache: dict[str, dict[str, Any] | None] = {}
        self.actual_model_call_count = 0

    def __call__(
        self,
        request: Any,
        question: str,
        _answer: str,
        bundle: EvidenceBundle,
    ) -> dict[str, Any] | None:
        slots = _required_slots(request)
        packed = _packed_evidence(request, bundle)
        seed = _verifier_seed(request)
        model = _model_name(self.llm)
        if not slots or not packed:
            return self._skipped_response(bundle, packed, slots, model, seed)
        try:
            prompt = _verifier_prompt(question, slots, packed)
        except ValueError:
            self.cache[_cache_key(question, slots, packed)] = None
            self._trace(
                bundle,
                "failed",
                "prompt_bound_exceeded",
                packed,
                slots,
                model,
                seed,
            )
            return None
        cache_key = _cache_key(question, slots, packed)
        if cache_key in self.cache:
            return self._cached_response(
                bundle, cache_key, packed, slots, model, seed, len(prompt)
            )
        response = self._model_response(prompt, packed, slots, seed)
        if response is None:
            self.cache[cache_key] = None
            self._trace(
                bundle,
                "failed",
                "model_call_failed",
                packed,
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
        self._trace(
            bundle,
            "parsed" if parsed is not None else "failed",
            "strict_schema_parsed" if parsed is not None else "invalid_model_json",
            packed,
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
    ) -> Any | None:
        self.actual_model_call_count += 1
        try:
            return self.llm(
                [
                    SystemMessage(content=_SYSTEM_PROMPT),
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
            )
        except Exception:
            LOGGER.exception("Semantic proposition verifier model call failed")
            return None

    def _cached_response(
        self,
        bundle: EvidenceBundle,
        cache_key: str,
        packed: list[dict[str, str]],
        slots: list[dict[str, str]],
        model: str,
        seed: int,
        prompt_chars: int,
    ) -> dict[str, Any] | None:
        cached = self.cache[cache_key]
        self._trace(
            bundle,
            "cache_hit" if cached is not None else "cached_failure",
            "evidence_signature_reused",
            packed,
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
        packed: list[dict[str, str]],
        slots: list[dict[str, str]],
        model: str,
        seed: int,
    ) -> dict[str, Any]:
        self._trace(
            bundle,
            "skipped",
            "required_slots_missing" if not slots else "no_canonical_evidence_items",
            packed,
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
        packed: list[dict[str, str]],
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
            packed=packed,
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


def _packed_evidence(request: Any, bundle: EvidenceBundle) -> list[dict[str, str]]:
    preferred = _preferred_evidence_ids(request)
    records: list[tuple[int, int, dict[str, str]]] = []
    seen: set[str] = set()
    for index, item in enumerate(bundle.items):
        try:
            identity = identity_of(item)
        except ValueError:
            continue
        evidence_id = identity.key
        text = evidence_item_text(item).strip()
        if not text or evidence_id in seen:
            continue
        seen.add(evidence_id)
        source_id, page_label = source_page_locator(item)
        records.append(
            (
                0 if evidence_id in preferred else 1,
                index,
                {
                    "evidence_id": evidence_id,
                    "source_id": source_id or identity.source_id,
                    "page_label": page_label,
                    "section_id": str(item.get("section_id") or "").strip(),
                    "text": text[:SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS],
                },
            )
        )
    selected = [value for _priority, _index, value in sorted(records)]
    selected = selected[:SEMANTIC_PROPOSITION_VERIFIER_MAX_ITEMS]
    for index, record in enumerate(selected, start=1):
        record["label"] = f"E{index}"
    return selected


def _preferred_evidence_ids(request: Any) -> set[str]:
    plan = getattr(request, "query_plan", None)
    raw_slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, dict)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    return {
        str(evidence_id).strip()
        for slot in raw_slots
        for evidence_id in (
            slot.get("evidence_ids", [])
            if isinstance(slot, dict)
            else getattr(slot, "evidence_ids", ()) or ()
        )
        if str(evidence_id).strip()
    }


def _verifier_prompt(
    question: str,
    slots: list[dict[str, str]],
    packed: list[dict[str, str]],
) -> str:
    slot_text = "\n".join(
        f"- {value['slot_id']}: {value['description'] or 'complete proposition support'}"
        for value in slots
    )
    evidence_text = "\n\n".join(
        "\n".join(
            (
                f"[{value['label']}] source={value['source_id']} "
                f"page={value['page_label'] or '-'} section={value['section_id'] or '-'}",
                "<evidence>",
                value["text"],
                "</evidence>",
            )
        )
        for value in packed
    )
    prompt = (
        "/no_think\n"
        f"QUESTION:\n{question.strip()}\n\n"
        f"REQUIRED VERIFICATION SLOTS:\n{slot_text}\n\n"
        f"RETRIEVED EVIDENCE EXCERPTS:\n{evidence_text}\n\n"
        "Return exactly one JSON object. For yes or no, jointly_complete and "
        "each_premise_required must both be true and premises must contain two "
        "to four records. For insufficient_evidence, use false for both flags "
        "and an empty premises array."
    )
    if len(prompt) > SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS:
        raise ValueError("Semantic proposition verifier prompt exceeded its bound.")
    return prompt


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


def _response_text(response: Any) -> str:
    return str(
        getattr(response, "text", "") or getattr(response, "content", "") or response
    )


def _record_trace(
    bundle: EvidenceBundle,
    *,
    status: str,
    reason: str,
    packed: list[dict[str, str]],
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
        "packed_evidence_count": len(packed),
        "required_slot_count": len(slots),
        "prompt_chars": prompt_chars,
        "verdict": verdict,
        "evidence_label_map": {
            value["label"]: value["evidence_id"] for value in packed
        },
    }
