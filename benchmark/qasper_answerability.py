from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .qasper_boolean import (
    boolean_quote_supports_relation as _boolean_quote_supports_relation,
)
from .qasper_boolean import boolean_relation_lemmas as _boolean_relation_lemmas
from .qasper_boolean import is_boolean_question as _is_boolean_question
from .qasper_boolean import stemmed_content_tokens as _stemmed_content_tokens

QASPER_ANSWERABILITY_CONTRACT = "qasper_answerability.v10"
QASPER_ANSWERABILITY_SEED = 20260724
QASPER_ANSWERABILITY_MAX_TOKENS = 192
QASPER_EVIDENCE_QUOTE_MAX_LENGTH = 640
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
                },
                "evidence_quote": {
                    "type": "string",
                    "maxLength": QASPER_EVIDENCE_QUOTE_MAX_LENGTH,
                },
            },
            "required": ["verdict", "evidence_quote"],
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
                    "enum": [
                        "yes_complete",
                        "no_complete",
                        "yes_partial",
                        "no_partial",
                        "insufficient_evidence",
                    ],
                },
                "evidence_quote": {
                    "type": "string",
                    "maxLength": QASPER_EVIDENCE_QUOTE_MAX_LENGTH,
                },
            },
            "required": ["verdict", "evidence_quote"],
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
    if not candidate:
        return QasperAnswerabilityResult(
            answer="",
            trace=_trace(
                "not_required",
                "",
                action="preserved_primary_answer",
            ),
        )
    if _UNANSWERABLE_RE.match(candidate):
        if _is_boolean_question(question):
            return _verify_boolean_candidate(
                llm,
                question=question,
                evidence=evidence,
                candidate_answer="unanswerable",
                candidate="",
            )
        return QasperAnswerabilityResult(
            answer="unanswerable",
            trace=_trace(
                "not_required",
                "unanswerable",
                action="preserved_primary_answer",
                primary_answer="unanswerable",
            ),
        )
    if candidate.lower() in {"yes", "no", "true", "false"}:
        return _verify_boolean_candidate(
            llm,
            question=question,
            evidence=evidence,
            candidate_answer=candidate_answer,
            candidate=candidate,
        )
    return _verify_free_text_candidate(
        llm,
        question=question,
        evidence=evidence,
        candidate_answer=candidate_answer,
        candidate=candidate,
    )


def _verify_boolean_candidate(
    llm: Any,
    *,
    question: str,
    evidence: str,
    candidate_answer: str,
    candidate: str,
) -> QasperAnswerabilityResult:
    candidate_polarity = (
        "yes" if candidate.lower() in {"yes", "true"} else "no" if candidate else ""
    )
    verdict, quote, parse_trace = _call_verifier(
        llm,
        _boolean_answerability_prompt(question=question, evidence=evidence),
        response_format=QASPER_BOOLEAN_ANSWERABILITY_RESPONSE_FORMAT,
        parser=_boolean_verdict,
        allowed_values=(
            "yes_complete",
            "no_complete",
            "yes_partial",
            "no_partial",
            "insufficient_evidence",
        ),
    )
    if not verdict:
        return QasperAnswerabilityResult(
            answer=candidate_answer,
            trace=_trace(
                "error",
                "",
                action="preserved_primary_answer",
                parse_trace=parse_trace,
                primary_answer=candidate_polarity or "unanswerable",
            ),
        )
    (
        verdict,
        raw_verdict,
        quote_grounded,
        quote_supports_relation,
        reason,
        relation_trace,
    ) = _ground_boolean_verdict(
        question=question,
        evidence=evidence,
        verdict=verdict,
        quote=quote,
    )
    action, answer = _boolean_answer_action(candidate_polarity, verdict)
    return QasperAnswerabilityResult(
        answer=answer,
        trace=_trace(
            "ok",
            verdict,
            action=action,
            evidence_quote=quote,
            quote_grounded=quote_grounded,
            quote_supports_relation=quote_supports_relation,
            parse_trace={**parse_trace, **relation_trace},
            primary_answer=candidate_polarity or "unanswerable",
            adjudicated_polarity=verdict,
            raw_verifier_verdict=raw_verdict,
            reason=reason,
        ),
    )


def _ground_boolean_verdict(
    *,
    question: str,
    evidence: str,
    verdict: str,
    quote: str,
) -> tuple[str, str, bool, bool, str, dict[str, str]]:
    raw_verdict = verdict
    relation_trace = {
        "question_relation_terms": ",".join(sorted(_boolean_relation_lemmas(question))),
        "quote_relation_terms": ",".join(sorted(_boolean_relation_lemmas(quote))),
    }
    quote_grounded = _quote_is_grounded(quote, evidence)
    complete = {
        "yes_complete": "yes",
        "no_complete": "no",
    }
    if raw_verdict in complete:
        quote_supports_relation = quote_grounded
        verdict = complete[raw_verdict] if quote_grounded else "insufficient_evidence"
        reason = (
            "grounded_complete_proposition" if quote_grounded else "ungrounded_quote"
        )
    elif raw_verdict in {"yes_partial", "no_partial"}:
        quote_supports_relation = False
        verdict = "insufficient_evidence"
        reason = (
            "grounded_partial_proposition" if quote_grounded else "ungrounded_quote"
        )
    elif raw_verdict == "insufficient_evidence":
        quote_supports_relation = False
        reason = "insufficient_evidence"
    else:
        quote_supports_relation = quote_grounded and _boolean_quote_supports_relation(
            quote,
            question,
            verdict,
        )
        if not quote_supports_relation:
            verdict = "insufficient_evidence"
        if not quote_grounded:
            reason = "ungrounded_quote"
        elif not quote_supports_relation:
            reason = "grounded_quote_incomplete_relation"
        else:
            reason = "grounded_complete_relation"
    return (
        verdict,
        raw_verdict,
        quote_grounded,
        quote_supports_relation,
        reason,
        relation_trace,
    )


def _boolean_answer_action(candidate_polarity: str, verdict: str) -> tuple[str, str]:
    if verdict not in {"yes", "no"}:
        action = (
            "preserved_insufficient_candidate"
            if candidate_polarity
            else "preserved_boolean_abstention"
        )
        return action, candidate_polarity or "unanswerable"
    if not candidate_polarity:
        return "recovered_boolean_from_abstention", verdict
    if verdict == candidate_polarity:
        return "confirmed_candidate", verdict
    return "polarity_conflict_preserved", candidate_polarity


def _verify_free_text_candidate(
    llm: Any,
    *,
    question: str,
    evidence: str,
    candidate_answer: str,
    candidate: str,
) -> QasperAnswerabilityResult:
    verdict, quote, parse_trace = _call_verifier(
        llm,
        _answerability_prompt(
            question=question,
            evidence=evidence,
            candidate_answer=candidate,
        ),
        response_format=QASPER_ANSWERABILITY_RESPONSE_FORMAT,
        parser=_verdict,
        allowed_values=("supported", "unsupported"),
    )
    if not verdict:
        return QasperAnswerabilityResult(
            answer=candidate_answer,
            trace=_trace(
                "error",
                "",
                action="preserved_primary_answer",
                parse_trace=parse_trace,
            ),
        )
    quote_grounded = _quote_is_grounded(quote, evidence)
    quote_supports_relation = quote_grounded and _quote_supports_relation(
        quote,
        question,
        candidate,
    )
    if verdict == "supported" and not quote_supports_relation:
        return QasperAnswerabilityResult(
            answer="unanswerable",
            trace=_trace(
                "ok",
                "unsupported",
                action="abstained_ungrounded_quote",
                evidence_quote=quote,
                quote_grounded=quote_grounded,
                quote_supports_relation=False,
                parse_trace=parse_trace,
            ),
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
            evidence_quote=quote,
            quote_grounded=quote_grounded,
            quote_supports_relation=quote_supports_relation,
            parse_trace=parse_trace,
        ),
    )


def _call_verifier(
    llm: Any,
    prompt: str,
    *,
    response_format: dict[str, Any],
    parser: Any,
    allowed_values: tuple[str, ...],
) -> tuple[str, str, dict[str, str]]:
    response = llm(
        prompt,
        max_tokens=QASPER_ANSWERABILITY_MAX_TOKENS,
        response_format=response_format,
        temperature=0,
        seed=QASPER_ANSWERABILITY_SEED,
    )
    initial_response = getattr(response, "text", "") or str(response)
    verdict, quote = parser(initial_response)
    if verdict:
        return (
            verdict,
            quote,
            {
                "parser_status": "ok",
                "repair_attempted": "false",
            },
        )
    if not _has_repairable_verdict(initial_response, allowed_values):
        return (
            "",
            "",
            {
                "parser_status": "error",
                "repair_attempted": "false",
                "repair_status": "not_repairable",
                "initial_response": str(initial_response),
            },
        )

    repair_response = llm(
        _json_structure_repair_prompt(
            initial_response,
            allowed_values=allowed_values,
        ),
        max_tokens=QASPER_ANSWERABILITY_MAX_TOKENS,
        response_format=response_format,
        temperature=0,
        seed=QASPER_ANSWERABILITY_SEED,
    )
    repaired_text = getattr(repair_response, "text", "") or str(repair_response)
    verdict, quote = parser(repaired_text)
    return (
        verdict,
        quote,
        {
            "parser_status": "ok" if verdict else "error",
            "repair_attempted": "true",
            "repair_status": "ok" if verdict else "error",
            "initial_response": str(initial_response),
            "repair_response": str(repaired_text),
        },
    )


def _has_repairable_verdict(
    response: str,
    allowed_values: tuple[str, ...],
) -> bool:
    lowered = str(response or "").lower()
    return any(
        re.search(rf'["\']?verdict["\']?\s*[:=]\s*["\']?{re.escape(value)}\b', lowered)
        for value in allowed_values
    )


def _json_structure_repair_prompt(
    response: str,
    *,
    allowed_values: tuple[str, ...],
) -> str:
    values = ", ".join(f'"{value}"' for value in allowed_values)
    return (
        "/no_think\n"
        "Repair only the JSON structure of the verifier response below. "
        "Do not reconsider the evidence, question, candidate, verdict, or "
        "evidence quote. Preserve the original verdict and quote exactly when "
        "they are present. Return one JSON object with exactly the keys "
        '"verdict" and "evidence_quote". The allowed verdict values are: '
        f"{values}.\n\n"
        f"VERIFIER RESPONSE:\n{response}"
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
        "paper merely mentions related facts. For a supported verdict, quote "
        "the shortest exact evidence span, at most 20 words, that states the "
        "question-candidate "
        "relation. If no such exact span exists, return unsupported with an "
        "empty evidence_quote.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"RETRIEVED PAPER EVIDENCE:\n{evidence}\n\n"
        f"CANDIDATE ANSWER:\n{candidate_answer}\n\n"
        'Return exactly {"verdict":"supported","evidence_quote":"..."} or '
        '{"verdict":"unsupported","evidence_quote":""}.'
    )


def _boolean_answerability_prompt(*, question: str, evidence: str) -> str:
    return (
        "/no_think\n"
        "You are a QASPER proposition verifier. Compare the complete yes/no "
        "question proposition with the retrieved paper evidence. A complete "
        "match requires the same subject, relation, object, scope, qualifiers, "
        "and polarity. Distinguish a process from its outcome, mentioning from "
        "performing, creating from experimenting, and controlling experimental "
        "collection from validating the quality of the resulting data.\n\n"
        "Return yes_complete or no_complete only when one polarity of that "
        "complete proposition is explicitly established. Return yes_partial "
        "or no_partial when the evidence supports that polarity only for a "
        "related or incomplete proposition. Return insufficient_evidence when "
        "neither polarity is established. Absence of a statement never proves "
        "no. For complete or partial verdicts, include the shortest exact "
        "contiguous evidence span, at most 60 words, that supports the verdict. "
        "Use an empty evidence_quote only for insufficient_evidence.\n\n"
        f"QUESTION:\n{question}\n\n"
        f"RETRIEVED PAPER EVIDENCE:\n{evidence}\n\n"
        'Return exactly {"verdict":"yes_complete","evidence_quote":"..."}, '
        '{"verdict":"no_complete","evidence_quote":"..."}, '
        '{"verdict":"yes_partial","evidence_quote":"..."}, '
        '{"verdict":"no_partial","evidence_quote":"..."}, or '
        '{"verdict":"insufficient_evidence","evidence_quote":""}.'
    )


def _clean_candidate(answer: str) -> str:
    return _THINK_BLOCK_RE.sub("", str(answer or "")).strip().rstrip(".")


def _verdict(answer: str) -> tuple[str, str]:
    try:
        payload = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(payload, dict):
        return "", ""
    value = str(payload.get("verdict") or "")
    quote = str(payload.get("evidence_quote") or "").strip()
    return (value, quote) if value in {"supported", "unsupported"} else ("", "")


def _boolean_verdict(answer: str) -> tuple[str, str]:
    try:
        payload = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return "", ""
    if not isinstance(payload, dict):
        return "", ""
    value = str(payload.get("verdict") or "")
    quote = str(payload.get("evidence_quote") or "").strip()
    allowed = {
        "yes_complete",
        "no_complete",
        "yes_partial",
        "no_partial",
        "yes",
        "no",
        "insufficient_evidence",
    }
    return (value, quote) if value in allowed else ("", "")


def _quote_supports_relation(quote: str, question: str, candidate: str) -> bool:
    quote_tokens = _stemmed_content_tokens(quote)
    candidate_tokens = _stemmed_content_tokens(candidate)
    if not candidate_tokens:
        return False
    candidate_coverage = len(quote_tokens & candidate_tokens) / len(candidate_tokens)
    question_anchors = _stemmed_content_tokens(question) - candidate_tokens
    required_anchors = min(2, len(question_anchors))
    return (
        candidate_coverage >= 0.5
        and required_anchors > 0
        and len(quote_tokens & question_anchors) >= required_anchors
    )


def _quote_is_grounded(quote: str, evidence: str) -> bool:
    normalized_quote = _normalized_quote(quote)
    normalized_evidence = _normalized_quote(evidence)
    return len(normalized_quote) >= 8 and normalized_quote in normalized_evidence


def _normalized_quote(value: str) -> str:
    return " ".join(str(value or "").lower().split())


def _trace(
    status: str,
    verdict: str,
    *,
    action: str = "",
    evidence_quote: str = "",
    quote_grounded: bool | None = None,
    quote_supports_relation: bool | None = None,
    parse_trace: dict[str, str] | None = None,
    primary_answer: str = "",
    adjudicated_polarity: str = "",
    raw_verifier_verdict: str = "",
    reason: str = "",
) -> dict[str, str]:
    trace = {
        "contract_id": QASPER_ANSWERABILITY_CONTRACT,
        "status": status,
        "verdict": verdict,
        "action": action,
    }
    if evidence_quote:
        trace["evidence_quote"] = evidence_quote
    if quote_grounded is not None:
        trace["quote_grounded"] = str(quote_grounded).lower()
    if quote_supports_relation is not None:
        trace["quote_supports_relation"] = str(quote_supports_relation).lower()
    if primary_answer:
        trace["primary_answer"] = primary_answer
    if adjudicated_polarity:
        trace["adjudicated_polarity"] = adjudicated_polarity
    if raw_verifier_verdict:
        trace["raw_verifier_verdict"] = raw_verifier_verdict
    if reason:
        trace["reason"] = reason
    trace.update(parse_trace or {})
    return trace
