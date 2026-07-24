from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

ALCE_ANSWER_GROUNDING_CONTRACT = "alce_short_answer_grounding.v1"
ALCE_ANSWER_GROUNDING_SEED = 20260724
ALCE_MAX_GROUNDING_EVIDENCE = 8
ALCE_MAX_EVIDENCE_CHARS = 1800

ALCE_ANSWER_GROUNDING_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "alce_short_answer_grounding",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["supported", "corrected", "insufficient_evidence"],
                },
                "answer": {"type": "string"},
                "evidence_index": {"type": "integer"},
            },
            "required": ["verdict", "answer", "evidence_index"],
            "additionalProperties": False,
        },
    },
}

_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "answer",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "the",
    "to",
    "was",
    "were",
}


@dataclass(frozen=True)
class AlceGroundingResult:
    answer: str
    trace: dict[str, Any]


def apply_alce_answer_grounding(
    *,
    suite_name: str,
    llm_factory: Callable[[], Any],
    question: str,
    candidate_answer: str,
    evidence_items: list[dict[str, Any]],
) -> tuple[str, dict[str, Any], float]:
    normalized_suite = str(suite_name or "").lower()
    if "alce" not in normalized_suite or "qampari" in normalized_suite:
        return candidate_answer, {}, 0.0
    start = time.perf_counter()
    result = ground_alce_short_answer(
        llm_factory(),
        question=question,
        candidate_answer=candidate_answer,
        evidence_items=evidence_items,
    )
    return result.answer, result.trace, time.perf_counter() - start


def alce_grounding_stage_event(
    trace: dict[str, Any],
    seconds: float,
) -> dict[str, Any]:
    return {
        "stage": "alce_answer_grounding",
        "status": trace.get("status", ""),
        "seconds": round(seconds, 4),
    }


def ground_alce_short_answer(
    llm: Any,
    *,
    question: str,
    candidate_answer: str,
    evidence_items: list[dict[str, Any]],
) -> AlceGroundingResult:
    evidence = list(evidence_items[:ALCE_MAX_GROUNDING_EVIDENCE])
    if not evidence:
        return AlceGroundingResult(
            answer=candidate_answer,
            trace=_trace("not_required"),
        )
    response = llm(
        _grounding_prompt(
            question=question,
            candidate_answer=candidate_answer,
            evidence_items=evidence,
        ),
        max_tokens=192,
        response_format=ALCE_ANSWER_GROUNDING_RESPONSE_FORMAT,
        temperature=0,
        seed=ALCE_ANSWER_GROUNDING_SEED,
    )
    payload = _grounding_payload(getattr(response, "text", "") or str(response))
    if payload is None:
        return AlceGroundingResult(
            answer=candidate_answer,
            trace=_trace("error"),
        )
    verdict = str(payload["verdict"])
    if verdict == "insufficient_evidence":
        return AlceGroundingResult(
            answer="unanswerable",
            trace=_trace(
                "ok",
                verdict=verdict,
                answer_changed=_normalized(candidate_answer) != "unanswerable",
            ),
        )
    evidence_index = int(payload["evidence_index"])
    grounded_answer = str(payload["answer"]).strip()
    if (
        evidence_index < 0
        or evidence_index >= len(evidence)
        or not grounded_answer
        or not _answer_traceable(
            grounded_answer, _evidence_text(evidence[evidence_index])
        )
    ):
        return AlceGroundingResult(
            answer=candidate_answer,
            trace=_trace("rejected_ungrounded_answer"),
        )
    evidence_id = str(
        evidence[evidence_index].get("evidence_id")
        or evidence[evidence_index].get("canonical_id")
        or ""
    )
    return AlceGroundingResult(
        answer=grounded_answer,
        trace=_trace(
            "ok",
            verdict=verdict,
            evidence_id=evidence_id,
            answer_changed=_normalized(grounded_answer)
            != _normalized(candidate_answer),
        ),
    )


def _grounding_prompt(
    *,
    question: str,
    candidate_answer: str,
    evidence_items: list[dict[str, Any]],
) -> str:
    evidence = "\n\n".join(
        f"[{index}] {_evidence_text(item)[:ALCE_MAX_EVIDENCE_CHARS]}"
        for index, item in enumerate(evidence_items)
    )
    return (
        "/no_think\n"
        "You are a short factual answer grounding verifier. Resolve every "
        "entity, role, date range, episode, location, quantity, qualifier, and "
        "list constraint in the question against one selected evidence item. "
        "Do not prefer a prominent competing entity that matches only part of "
        "the question. If the candidate is fully supported, return supported. "
        "If a selected item directly resolves the question but binds it to a "
        "different answer, return corrected. If no selected item directly "
        "resolves all required constraints, return insufficient_evidence. The "
        "answer must be the shortest complete value copied or directly "
        "extractable from the chosen evidence item. evidence_index is zero "
        "based; use -1 only for insufficient_evidence.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"CANDIDATE ANSWER:\n{candidate_answer}\n\n"
        f"SELECTED EVIDENCE:\n{evidence}\n\n"
        "Return only the required JSON object."
    )


def _grounding_payload(answer: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    verdict = str(payload.get("verdict") or "")
    if verdict not in {"supported", "corrected", "insufficient_evidence"}:
        return None
    if not isinstance(payload.get("answer"), str):
        return None
    if not isinstance(payload.get("evidence_index"), int):
        return None
    return payload


def _answer_traceable(answer: str, evidence: str) -> bool:
    answer_tokens = {token for token in _tokens(answer) if token not in _STOPWORDS}
    evidence_tokens = set(_tokens(evidence))
    return bool(answer_tokens) and answer_tokens <= evidence_tokens


def _evidence_text(item: dict[str, Any]) -> str:
    return " ".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _WORD_RE.findall(str(text or ""))]


def _normalized(text: str) -> str:
    return " ".join(_tokens(text))


def _trace(
    status: str,
    *,
    verdict: str = "",
    evidence_id: str = "",
    answer_changed: bool = False,
) -> dict[str, Any]:
    return {
        "contract_id": ALCE_ANSWER_GROUNDING_CONTRACT,
        "status": status,
        "verdict": verdict,
        "evidence_id": evidence_id,
        "answer_changed": answer_changed,
    }
