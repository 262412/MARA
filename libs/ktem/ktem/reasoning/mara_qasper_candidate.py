from __future__ import annotations

import hashlib
import json
import logging
from copy import deepcopy
from typing import Any

from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import request_planning_question

from kotaemon.base import HumanMessage, SystemMessage

from .mara_answer_type_contract import request_answer_type
from .mara_semantic_proposition_debug import (
    provider_failure,
    response_completion_tokens,
    response_finish_reason,
    response_text,
)

QASPER_CANDIDATE_GENERATION_CONTRACT = "qasper_typed_candidate_generation.v1"
QASPER_CANDIDATE_RESPONSE_CONTRACT = "qasper_typed_candidate.v1"
QASPER_CANDIDATES = {"yes", "no", "unanswerable"}
QASPER_CANDIDATE_MAX_EVIDENCE_ITEMS = 12
QASPER_CANDIDATE_MAX_EVIDENCE_CHARS = 24_000
QASPER_CANDIDATE_MAX_RESPONSE_CHARS = 16_000
QASPER_CANDIDATE_MAX_TOKENS = 48
QASPER_CANDIDATE_DEFAULT_SEED = 20260724

LOGGER = logging.getLogger(__name__)

_SYSTEM_PROMPT = (
    "You are the sole answer-candidate generator for a QASPER Boolean question. "
    "Use only the labeled retrieved evidence. Return exactly one structured "
    "candidate: yes, no, or unanswerable. Use yes/no only when the complete "
    "question proposition is established; otherwise use unanswerable. Do not "
    "include explanation, citations, or an alternative answer."
)


def qasper_typed_candidate_request(request: Any) -> bool:
    domain = str(getattr(request, "verification_domain", "") or "").casefold()
    origin = str(getattr(request, "origin", "") or "").casefold()
    return (
        origin == "benchmark"
        and (domain == "qasper" or domain.startswith("qasper_"))
        and request_answer_type(request) == "boolean"
    )


def generate_qasper_typed_candidate(
    pipeline: Any,
    request: Any,
    bundle: EvidenceBundle,
) -> str:
    llm = _answering_llm(pipeline)
    question = request_planning_question(request)
    evidence = _packed_evidence(bundle)
    seed = _effective_seed(request)
    route = str(bundle.route or "")
    identity = _transaction_identity(request, route, seed)
    messages = [
        SystemMessage(content=_SYSTEM_PROMPT),
        HumanMessage(content=_candidate_prompt(question, evidence)),
    ]
    serialized_messages = _serialized_messages(messages)
    input_digest = _digest(
        {
            "messages": serialized_messages,
            "seed": seed,
            "route": route,
            "benchmark_route_id": identity.get("benchmark_route_id", ""),
        }
    )
    trace: dict[str, Any] = {
        "contract_id": QASPER_CANDIDATE_GENERATION_CONTRACT,
        **identity,
        "status": "started",
        "failure_reason": "",
        "model": _model_name(llm),
        "route": route,
        "internal_route": route,
        "benchmark_route_id": identity.get("benchmark_route_id", ""),
        "effective_seed": seed,
        "message_stack": serialized_messages,
        "message_stack_digest": _digest(serialized_messages),
        "input_digest": input_digest,
        "evidence_count": len(evidence),
        "evidence_digest": _digest(evidence),
        "attempts": [],
        "raw_response": "",
        "raw_response_truncated": False,
        "cleaned_response": "",
        "typed_candidate": "",
        "output_digest": "",
        "finish_reason": "",
        "completion_tokens": -1,
        "transformation_stages": [],
    }
    bundle.metadata["qasper_candidate_generation"] = trace
    if llm is None:
        trace.update(status="failed", failure_reason="generator_llm_unavailable")
        return ""
    return _generate_candidate_response(
        llm,
        messages,
        trace,
        identity,
        input_digest,
        seed,
    )


def _generate_candidate_response(
    llm: Any,
    messages: list[Any],
    trace: dict[str, Any],
    identity: dict[str, str],
    input_digest: str,
    seed: int,
) -> str:
    try:
        response = llm(
            messages,
            max_tokens=QASPER_CANDIDATE_MAX_TOKENS,
            response_format=qasper_candidate_response_format(),
            temperature=0,
            top_p=1,
            seed=seed,
        )
    except Exception as exc:
        LOGGER.exception("QASPER typed candidate generation failed")
        reason, detail = provider_failure(exc)
        trace.update(status="failed", failure_reason=reason)
        trace["attempts"] = [
            {
                "attempt_id": identity["attempt_id"],
                "status": "provider_failed",
                "failure_reason": reason,
                "failure_detail": detail,
            }
        ]
        return ""

    return _record_candidate_response(
        response,
        trace,
        identity,
        input_digest,
    )


def _record_candidate_response(
    response: Any,
    trace: dict[str, Any],
    identity: dict[str, str],
    input_digest: str,
) -> str:
    raw = response_text(response)
    bounded_raw = raw[:QASPER_CANDIDATE_MAX_RESPONSE_CHARS]
    cleaned = bounded_raw.strip()
    candidate, failure = parse_qasper_candidate(cleaned)
    finish_reason = response_finish_reason(response)
    output_digest = _digest(raw)
    trace.update(
        status="parsed" if candidate else "failed",
        failure_reason=failure,
        raw_response=bounded_raw,
        raw_response_truncated=len(raw) > QASPER_CANDIDATE_MAX_RESPONSE_CHARS,
        cleaned_response=cleaned,
        typed_candidate=candidate,
        output_digest=output_digest,
        finish_reason=finish_reason,
        completion_tokens=response_completion_tokens(response),
        transformation_stages=[
            {
                "stage": "raw_response",
                "value": bounded_raw,
                "digest": output_digest,
                "failure_reason": "",
            },
            {
                "stage": "cleaning",
                "value": cleaned,
                "digest": _digest(cleaned),
                "changed": bounded_raw != cleaned,
                "failure_reason": "" if cleaned else "empty_cleaned_response",
            },
            {
                "stage": "typed_candidate",
                "value": candidate,
                "digest": _digest(candidate),
                "failure_reason": failure,
            },
        ],
    )
    trace["attempts"] = [
        {
            "attempt_id": identity["attempt_id"],
            "status": trace["status"],
            "failure_reason": failure,
            "raw_response": bounded_raw,
            "cleaned_response": cleaned,
            "typed_candidate": candidate,
            "finish_reason": finish_reason,
            "completion_tokens": trace["completion_tokens"],
            "input_digest": input_digest,
            "output_digest": output_digest,
        }
    ]
    return candidate


def qasper_candidate_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "qasper_typed_candidate",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "candidate": {
                        "type": "string",
                        "enum": sorted(QASPER_CANDIDATES),
                    }
                },
                "required": ["candidate"],
                "additionalProperties": False,
            },
        },
    }


def parse_qasper_candidate(text: str) -> tuple[str, str]:
    try:
        payload = json.loads(str(text or ""))
    except (TypeError, json.JSONDecodeError):
        return "", "json_decode_error"
    if not isinstance(payload, dict) or set(payload) != {"candidate"}:
        return "", "candidate_schema_invalid"
    candidate = str(payload.get("candidate") or "").strip().casefold()
    if candidate not in QASPER_CANDIDATES:
        return "", "candidate_enum_invalid"
    return candidate, ""


def _answering_llm(pipeline: Any) -> Any | None:
    answering_pipeline = getattr(pipeline, "answering_pipeline", None)
    llm = getattr(answering_pipeline, "llm", None)
    return llm if callable(llm) else None


def _packed_evidence(bundle: EvidenceBundle) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    used_chars = 0
    for item in bundle.items:
        text = evidence_item_text(item).strip()
        if not text:
            continue
        remaining = QASPER_CANDIDATE_MAX_EVIDENCE_CHARS - used_chars
        if remaining <= 0:
            break
        bounded = text[:remaining]
        try:
            evidence_id = identity_of(item).key
        except ValueError:
            evidence_id = str(item.get("evidence_id") or "")
        records.append(
            {
                "label": f"E{len(records) + 1}",
                "evidence_id": evidence_id,
                "text": bounded,
            }
        )
        used_chars += len(bounded)
        if len(records) >= QASPER_CANDIDATE_MAX_EVIDENCE_ITEMS:
            break
    return records


def _candidate_prompt(question: str, evidence: list[dict[str, str]]) -> str:
    evidence_text = "\n\n".join(
        f"[{record['label']}] evidence_id={record['evidence_id']}\n{record['text']}"
        for record in evidence
    )
    return (
        "/no_think\n"
        f"QUESTION:\n{question.strip()}\n\n"
        f"CANONICAL RETRIEVED EVIDENCE:\n{evidence_text}\n\n"
        "Return exactly one JSON object matching the required schema."
    )


def _serialized_messages(messages: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "role": "system" if isinstance(message, SystemMessage) else "user",
            "content": deepcopy(message.content),
        }
        for index, message in enumerate(messages)
    ]


def _transaction_identity(request: Any, route: str, seed: int) -> dict[str, str]:
    context = dict(getattr(request, "trace_context", {}) or {})
    group_id = str(context.get("trace_group_id") or "")
    benchmark_route_id = str(
        context.get("benchmark_route_id")
        or getattr(request, "benchmark_route_id", "")
        or ""
    )
    if not group_id:
        group_id = _digest(
            {
                "contract_id": "benchmark_transaction_identity.v1",
                "dataset": str(getattr(request, "dataset_family", "") or ""),
                "question": request_planning_question(request),
            }
        )
    transaction_id = _digest(
        {
            "trace_group_id": group_id,
            "benchmark_route_id": benchmark_route_id,
            "route": route,
            "stage": "candidate_generation",
            "seed": seed,
        }
    )
    return {
        "trace_group_id": group_id,
        "benchmark_route_id": benchmark_route_id,
        "internal_route": route,
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:candidate_generation:1",
    }


def _effective_seed(request: Any) -> int:
    value = getattr(request, "generation_seed", None)
    return QASPER_CANDIDATE_DEFAULT_SEED if value is None else int(value)


def _model_name(llm: Any | None) -> str:
    if llm is None:
        return ""
    for key in ("model_name", "model", "model_id"):
        value = str(getattr(llm, key, "") or "").strip()
        if value:
            return value
    return f"{type(llm).__module__}.{type(llm).__name__}"


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
