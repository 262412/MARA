from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from kotaemon.base import HumanMessage, SystemMessage

from .mara_ragtruth_claims import (
    RAGTRUTH_CLAIM_SYSTEM_PROMPT,
    candidate_claim_indices,
    candidate_spans,
    claim_verifier_prompt,
    claim_verifier_response_format,
    hallucination_answer,
    heuristic_unsupported_claim_indices,
    ragtruth_task_blocks,
    ragtruth_task_type,
    response_claims,
    supported_claim_indices,
    unsupported_claim_indices,
)

RAGTRUTH_SYSTEM_PROMPT = (
    "You are a conservative hallucination-span evaluator. A response claim is "
    "supported when the source states it, paraphrases it, or clearly entails it. "
    "Mark a span only when it contradicts the source or adds a concrete fact with "
    "no source support. Copy each unsupported span exactly from the response. "
    "Return an empty list when none are demonstrably unsupported, and return "
    'exactly one JSON object with only the key "hallucination list".'
)
RAGTRUTH_JUDGE_SEED = 20260724
RAGTRUTH_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "ragtruth_hallucination_spans",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "hallucination list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "maxItems": 8,
                }
            },
            "required": ["hallucination list"],
            "additionalProperties": False,
        },
    },
}


def route_ragtruth_answer(pipeline: Any, request: Any, bundle: Any) -> str | None:
    origin = str(getattr(request, "origin", "") or "").strip().lower()
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    if origin != "benchmark" or domain != "ragtruth":
        return None
    answering_pipeline = getattr(pipeline, "answering_pipeline")
    llm = getattr(answering_pipeline, "llm")
    prompt = str(getattr(request, "prompt", "") or "")
    generation_contract = _generation_contract(request)
    candidate_response = llm(
        [
            SystemMessage(content=RAGTRUTH_SYSTEM_PROMPT),
            HumanMessage(content=prompt),
        ],
        max_tokens=768,
        response_format=RAGTRUTH_RESPONSE_FORMAT,
        **generation_contract,
    )
    bundle.metadata["generation_contract"] = generation_contract
    bundle.metadata["ragtruth_task_prompt_chars"] = len(prompt)
    candidate_answer = str(getattr(candidate_response, "text", "") or "")
    blocks = ragtruth_task_blocks(prompt)
    if blocks is None:
        bundle.metadata["generation_backend"] = "ragtruth_task_llm"
        return candidate_answer

    source, response = blocks
    task_type = ragtruth_task_type(prompt)
    claims = response_claims(response)
    if not claims:
        _record_empty_claim_trace(bundle.metadata)
        return '{"hallucination list": []}'

    verifier_response = llm(
        [
            SystemMessage(content=RAGTRUTH_CLAIM_SYSTEM_PROMPT),
            HumanMessage(content=claim_verifier_prompt(source, claims)),
        ],
        max_tokens=256,
        response_format=claim_verifier_response_format(len(claims)),
        **generation_contract,
    )
    candidates = candidate_claim_indices(candidate_answer, claims)
    unsupported = unsupported_claim_indices(
        str(getattr(verifier_response, "text", "") or ""),
        len(claims),
    )
    heuristic_unsupported = heuristic_unsupported_claim_indices(source, claims)
    supported = supported_claim_indices(source, claims)
    answer, filtered_count = hallucination_answer(
        claims,
        candidate_indices=candidates,
        verifier_indices=unsupported,
        heuristic_indices=heuristic_unsupported,
        supported_indices=supported,
        accept_verifier_only=task_type == "data2txt",
    )
    detector_consensus = candidates & unsupported
    detected = detector_consensus | heuristic_unsupported
    if task_type == "data2txt":
        detected |= unsupported
    selected_unsupported = detected - supported
    _record_detector_trace(
        bundle.metadata,
        claims=claims,
        source_evidence_id=_source_evidence_id(
            source,
            list(getattr(bundle, "items", None) or []),
        ),
        task_type=task_type,
        candidate_answer=candidate_answer,
        candidates=candidates,
        unsupported=unsupported,
        detector_consensus=detector_consensus,
        heuristic_unsupported=heuristic_unsupported,
        supported=supported,
        filtered_count=filtered_count,
        selected_unsupported=selected_unsupported,
    )
    return answer


def _generation_contract(request: Any) -> dict[str, float | int]:
    temperature = getattr(request, "generation_temperature", None)
    top_p = getattr(request, "generation_top_p", None)
    seed = getattr(request, "generation_seed", None)
    return {
        "temperature": 0 if temperature is None else float(temperature),
        "top_p": 1 if top_p is None else float(top_p),
        "seed": RAGTRUTH_JUDGE_SEED if seed is None else int(seed),
    }


def _record_detector_trace(
    metadata: dict[str, Any],
    *,
    claims: list[str],
    source_evidence_id: str,
    task_type: str,
    candidate_answer: str,
    candidates: set[int],
    unsupported: set[int],
    detector_consensus: set[int],
    heuristic_unsupported: set[int],
    supported: set[int],
    filtered_count: int,
    selected_unsupported: set[int],
) -> None:
    metadata.update(
        {
            "generation_backend": "ragtruth_claim_verifier_v1",
            "ragtruth_claim_count": len(claims),
            "ragtruth_claims": list(claims),
            "ragtruth_source_evidence_id": source_evidence_id,
            "ragtruth_task_type": task_type,
            "ragtruth_candidate_claim_count": len(candidates),
            "ragtruth_candidate_claim_indices": sorted(candidates),
            "ragtruth_candidate_spans": candidate_spans(candidate_answer),
            "ragtruth_verifier_unsupported_count": len(unsupported),
            "ragtruth_verifier_unsupported_indices": sorted(unsupported),
            "ragtruth_detector_consensus_count": len(detector_consensus),
            "ragtruth_detector_consensus_indices": sorted(detector_consensus),
            "ragtruth_heuristic_unsupported_count": len(heuristic_unsupported),
            "ragtruth_heuristic_unsupported_indices": sorted(heuristic_unsupported),
            "ragtruth_supported_span_filter_count": filtered_count,
            "ragtruth_supported_claim_indices": sorted(supported),
            "ragtruth_unsupported_claim_count": len(selected_unsupported),
            "ragtruth_emitted_claim_indices": sorted(selected_unsupported)[:8],
        }
    )


def _source_evidence_id(source: str, items: list[Any]) -> str:
    normalized_source = _normalized_source_text(source)
    if not normalized_source:
        return ""
    matches: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence_text = " ".join(
            str(item.get(field) or "").strip()
            for field in ("text", "ocr_text", "vlm_text", "caption")
            if str(item.get(field) or "").strip()
        )
        if _normalized_source_text(evidence_text) != normalized_source:
            continue
        try:
            matches[identity_of(item).key] = item
        except (TypeError, ValueError):
            continue
    return next(iter(matches)) if len(matches) == 1 else ""


def _normalized_source_text(value: str) -> str:
    return " ".join(str(value or "").split())


def _record_empty_claim_trace(metadata: dict[str, Any]) -> None:
    metadata.update(
        {
            "generation_backend": "ragtruth_claim_verifier_v1",
            "ragtruth_claim_count": 0,
            "ragtruth_claims": [],
            "ragtruth_supported_claim_indices": [],
            "ragtruth_emitted_claim_indices": [],
        }
    )
