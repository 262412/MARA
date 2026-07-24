from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

QASPER_ANSWERABILITY_CONTRACT = "qasper_answerability.v5"
QASPER_ANSWERABILITY_SEED = 20260724
QASPER_ANSWERABILITY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "qasper_answerability",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["supported", "unsupported"],
                }
            },
            "required": ["verdict"],
            "additionalProperties": False,
        },
    },
}
QASPER_BOOLEAN_ANSWERABILITY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "qasper_boolean_answerability",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["yes", "no", "insufficient_evidence"],
                }
            },
            "required": ["verdict"],
            "additionalProperties": False,
        },
    },
}

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_UNANSWERABLE_RE = re.compile(
    r"^(?:unanswerable|insufficient evidence|not enough evidence|"
    r"unable to answer|cannot answer)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QasperAnswerabilityResult:
    answer: str
    trace: dict[str, str]


def verify_qasper_answerability(
    llm: Any,
    *,
    question: str,
    evidence: str,
    candidate_answer: str,
) -> QasperAnswerabilityResult:
    candidate = _clean_candidate(candidate_answer)
    if not candidate or _UNANSWERABLE_RE.match(candidate):
        return QasperAnswerabilityResult(
            answer="unanswerable" if candidate else "",
            trace=_trace(
                "not_required",
                "unanswerable" if candidate else "",
                action="preserved_primary_answer",
            ),
        )
    if candidate.lower() in {"yes", "no", "true", "false"}:
        candidate_polarity = "yes" if candidate.lower() in {"yes", "true"} else "no"
        response = llm(
            _boolean_answerability_prompt(
                question=question,
                evidence=evidence,
            ),
            max_tokens=64,
            response_format=QASPER_BOOLEAN_ANSWERABILITY_RESPONSE_FORMAT,
            temperature=0,
            seed=QASPER_ANSWERABILITY_SEED,
        )
        verdict = _boolean_verdict(getattr(response, "text", "") or str(response))
        if not verdict:
            return QasperAnswerabilityResult(
                answer=candidate_answer,
                trace=_trace("error", "", action="preserved_primary_answer"),
            )
        if verdict == candidate_polarity:
            action = "confirmed_candidate"
        elif verdict == "insufficient_evidence":
            action = "preserved_insufficient_candidate"
        else:
            action = "preserved_conflicting_candidate"
        return QasperAnswerabilityResult(
            answer=candidate_polarity,
            trace=_trace("ok", verdict, action=action),
        )

    response = llm(
        _answerability_prompt(
            question=question,
            evidence=evidence,
            candidate_answer=candidate,
        ),
        max_tokens=64,
        response_format=QASPER_ANSWERABILITY_RESPONSE_FORMAT,
        temperature=0,
        seed=QASPER_ANSWERABILITY_SEED,
    )
    verdict = _verdict(getattr(response, "text", "") or str(response))
    if not verdict:
        return QasperAnswerabilityResult(
            answer=candidate_answer,
            trace=_trace("error", "", action="preserved_primary_answer"),
        )
    return QasperAnswerabilityResult(
        answer=candidate_answer if verdict == "supported" else "unanswerable",
        trace=_trace(
            "ok",
            verdict,
            action=(
                "confirmed_candidate"
                if verdict == "supported"
                else "abstained_unsupported_candidate"
            ),
        ),
    )


def _answerability_prompt(
    *,
    question: str,
    evidence: str,
    candidate_answer: str,
) -> str:
    return (
        "/no_think\n"
        "You are a QASPER evidence-sufficiency verifier. Decide whether the "
        "retrieved paper evidence explicitly supports the complete candidate "
        "answer to the question. Topic overlap or a plausible answer is not "
        "sufficient. Every entity, relation, metric, qualifier, polarity, and "
        "number in the candidate must be entailed. For yes/no candidates, the "
        "evidence must support that polarity. Return unsupported when the "
        "paper merely mentions related facts.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"RETRIEVED PAPER EVIDENCE:\n{evidence}\n\n"
        f"CANDIDATE ANSWER:\n{candidate_answer}\n\n"
        'Return exactly {"verdict":"supported"} or '
        '{"verdict":"unsupported"}.'
    )


def _boolean_answerability_prompt(*, question: str, evidence: str) -> str:
    return (
        "/no_think\n"
        "You are a QASPER boolean evidence verifier. Use the retrieved paper "
        "evidence to determine the supported polarity of the yes/no question. "
        'Return "yes" only when the evidence entails yes, "no" only when it '
        "entails no, and insufficient_evidence when neither polarity is "
        "established. Topic overlap, a related experiment, or the absence of "
        "a statement is insufficient evidence.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"RETRIEVED PAPER EVIDENCE:\n{evidence}\n\n"
        'Return exactly {"verdict":"yes"}, {"verdict":"no"}, or '
        '{"verdict":"insufficient_evidence"}.'
    )


def _clean_candidate(answer: str) -> str:
    return _THINK_BLOCK_RE.sub("", str(answer or "")).strip().rstrip(".")


def _verdict(answer: str) -> str:
    try:
        payload = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    value = str(payload.get("verdict") or "")
    return value if value in {"supported", "unsupported"} else ""


def _boolean_verdict(answer: str) -> str:
    try:
        payload = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return ""
    if not isinstance(payload, dict):
        return ""
    value = str(payload.get("verdict") or "")
    return value if value in {"yes", "no", "insufficient_evidence"} else ""


def _trace(status: str, verdict: str, *, action: str = "") -> dict[str, str]:
    return {
        "contract_id": QASPER_ANSWERABILITY_CONTRACT,
        "status": status,
        "verdict": verdict,
        "action": action,
    }
