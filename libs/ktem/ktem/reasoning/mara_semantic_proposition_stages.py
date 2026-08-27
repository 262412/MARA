from __future__ import annotations

import json
import logging
from collections.abc import Collection
from copy import deepcopy
from typing import Any

from ktem.docqa.boolean_authority_schema import SEMANTIC_ENTAILMENT_AUDIT_CONTRACT

from kotaemon.base import HumanMessage, SystemMessage

from .mara_candidate_unknown_audit import (
    UNKNOWN_AUDIT_MAX_TOKENS,
    UNKNOWN_AUDIT_SYSTEM_PROMPT,
    candidate_unknown_audit_response_format,
    parse_candidate_unknown_audit,
)
from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    SEMANTIC_ENTAILMENT_AUDIT_SYSTEM_PROMPT,
    parse_semantic_entailment_audit,
    semantic_entailment_audit_response_format,
)
from .mara_semantic_audit_preflight import (
    PRE_AUDIT_SCHEMA_VALIDATION_FAILED,
    audit_preflight_failure_reason,
)
from .mara_semantic_proposition_debug import (
    provider_failure,
    response_completion_tokens,
    response_finish_reason,
    response_text,
)
from .mara_semantic_proposition_stage_runtime import (
    ParsedSemanticStage,
    StageCallResult,
    parsed_stage as _parsed_stage,
)
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT,
)
from .mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)

SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS = 768
SEMANTIC_PROPOSITION_VERIFIER_MAX_PARSE_RETRIES = 1

LOGGER = logging.getLogger(__name__)


def proposal_stage(
    llm: Any,
    prompt: str,
    *,
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    model: str,
    seed: int,
    candidate: str = "",
    applicable_proposition_slots: Collection[str] | None = None,
) -> ParsedSemanticStage:
    def call(correction: str = "") -> StageCallResult:
        return _call_proposal(
            llm,
            prompt,
            packed=packed,
            slots=slots,
            seed=seed,
            correction_reason=correction,
            candidate=candidate,
            applicable_proposition_slots=applicable_proposition_slots,
        )

    def parse(response: Any) -> Any:
        return parse_semantic_proposition_response(
            response_text(response),
            packed=packed,
            slot_ids={value["slot_id"] for value in slots},
            model=model,
            seed=seed,
            candidate=candidate,
            applicable_proposition_slots=applicable_proposition_slots,
        )

    return _parsed_stage(
        call,
        parse,
        max_parse_retries=SEMANTIC_PROPOSITION_VERIFIER_MAX_PARSE_RETRIES,
    )


def audit_stage(
    llm: Any,
    prompt: str,
    premise_count: int,
    *,
    seed: int,
    premise_slot_expectations: dict[str, Collection[str]] | None = None,
    premise_slot_evidence: dict[str, dict[str, Any]] | None = None,
    semantic_identity: dict[str, Any] | None = None,
) -> ParsedSemanticStage:
    labels = [f"P{index}" for index in range(1, premise_count + 1)]

    preflight_reason = audit_preflight_failure_reason(
        labels,
        premise_slot_expectations=premise_slot_expectations,
        premise_slot_evidence=premise_slot_evidence,
    )
    if preflight_reason:
        return _pre_audit_failure_stage(preflight_reason)

    def call(correction: str = "") -> StageCallResult:
        return _call_audit(
            llm,
            prompt,
            premise_labels=labels,
            seed=seed,
            correction_reason=correction,
            premise_slot_expectations=premise_slot_expectations,
            premise_slot_evidence=premise_slot_evidence,
        )

    def parse(response: Any) -> Any:
        return parse_semantic_entailment_audit(
            response_text(response),
            premise_labels=labels,
            premise_slot_expectations=premise_slot_expectations,
            premise_slot_evidence=premise_slot_evidence,
        )

    return _parsed_stage(
        call,
        parse,
        semantic_identity=lambda response, _parsed: _audit_semantic_identity(
            response,
            input_identity=semantic_identity,
        ),
        identity_failure_reason="audit_retry_semantic_identity_changed",
        max_parse_retries=SEMANTIC_PROPOSITION_VERIFIER_MAX_PARSE_RETRIES,
    )


def candidate_unknown_audit_stage(
    llm: Any,
    prompt: str,
    *,
    candidate: str,
    verifier_judgment: str = "",
    seed: int,
) -> ParsedSemanticStage:
    def call(correction: str = "") -> StageCallResult:
        return _call_candidate_unknown_audit(
            llm,
            prompt,
            candidate=candidate,
            verifier_judgment=verifier_judgment,
            seed=seed,
            correction_reason=correction,
        )

    def parse(response: Any) -> Any:
        return parse_candidate_unknown_audit(
            response_text(response),
            candidate=candidate,
            verifier_judgment=verifier_judgment,
        )

    return _parsed_stage(
        call,
        parse,
        max_parse_retries=SEMANTIC_PROPOSITION_VERIFIER_MAX_PARSE_RETRIES,
    )


def proposal_diagnostics(stage: ParsedSemanticStage) -> dict[str, Any]:
    return {
        "proposal_retry_count": stage.retry_count,
        "initial_parse_failure_reason": stage.initial_failure_reason,
        "parse_failure_reason": stage.failure_reason,
        "response_finish_reason": response_finish_reason(stage.response),
        "response_completion_tokens": response_completion_tokens(stage.response),
        "response_chars": (
            len(response_text(stage.response)) if stage.response is not None else 0
        ),
        "audit_status": "not_started",
        "audit_reason": "",
    }


def audit_diagnostics(stage: ParsedSemanticStage, *, model: str) -> dict[str, Any]:
    execution_status = (
        "provider_failed"
        if stage.provider_failure_reason
        else "not_started"
        if stage.call_count == 0 and stage.value is None
        else "parse_failed"
        if stage.value is None
        else "parsed"
    )
    return {
        "audit_contract_id": SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
        "audit_model": model,
        "audit_status": execution_status,
        "audit_execution_status": execution_status,
        "audit_parser_accepted": stage.value is not None,
        "audit_semantic_rejection": False,
        "audit_reason": (
            stage.provider_failure_reason
            if stage.provider_failure_reason
            else stage.failure_reason
            if execution_status == "not_started"
            else ""
        ),
        "audit_retry_count": stage.retry_count,
        "audit_initial_parse_failure_reason": stage.initial_failure_reason,
        "audit_parse_failure_reason": stage.failure_reason,
        "audit_response_finish_reason": response_finish_reason(stage.response),
        "audit_response_completion_tokens": response_completion_tokens(stage.response),
        "audit_response_chars": (
            len(response_text(stage.response)) if stage.response is not None else 0
        ),
    }


def invalid_response_reason(
    response: Any,
    *,
    max_tokens: int,
    invalid_reason: str,
) -> str:
    finish_reason = response_finish_reason(response).casefold()
    completion_tokens = response_completion_tokens(response)
    if finish_reason in {"length", "max_tokens"} or completion_tokens >= max_tokens:
        return (
            "semantic_entailment_audit_output_truncated"
            if invalid_reason == "invalid_entailment_audit_json"
            else "provider_output_truncated"
        )
    return invalid_reason


def _audit_semantic_identity(
    response: Any,
    *,
    input_identity: dict[str, Any] | None = None,
) -> str | None:
    payload = _response_payload(response)
    if payload is None:
        unavailable: dict[str, Any] = {"response_semantics_unavailable": True}
        if input_identity:
            unavailable["input"] = deepcopy(input_identity)
        return json.dumps(unavailable, sort_keys=True, separators=(",", ":"))
    identity = {
        "original_candidate": str(payload.get("original_candidate") or ""),
        "candidate_judgment": str(payload.get("candidate_judgment") or ""),
        "evidence_relation": str(payload.get("evidence_relation") or ""),
        "verdict": str(payload.get("verdict") or ""),
        "replacement_candidate_allowed": payload.get("replacement_candidate_allowed"),
        "replacement_candidate": str(payload.get("replacement_candidate") or ""),
        "typed_conclusion_polarity": str(
            (payload.get("typed_conclusion") or {}).get("polarity") or ""
        ),
        "premise_checks": _normalized_premise_checks(payload.get("premise_checks")),
        "jointly_entails": payload.get("jointly_entails"),
        "each_premise_required": payload.get("each_premise_required"),
        "contradiction_free": payload.get("contradiction_free"),
        "conclusion_check": _normalized_conclusion_check(
            payload.get("conclusion_check")
        ),
    }
    if input_identity:
        identity["input"] = deepcopy(input_identity)
    return json.dumps(identity, sort_keys=True, separators=(",", ":"))


def _normalized_premise_checks(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        raw_checks = [
            {"premise_ref": label, **raw}
            for label, raw in value.items()
            if isinstance(raw, dict)
        ]
    elif isinstance(value, list):
        raw_checks = value
    else:
        return []
    normalized: list[dict[str, Any]] = []
    for raw in raw_checks:
        if not isinstance(raw, dict):
            continue
        slots = raw.get("declared_proposition_slots")
        slot_checks = raw.get("proposition_slot_checks")
        if isinstance(slot_checks, dict):
            normalized_slot_checks = [
                {
                    "slot": str(slot),
                    "binding_valid": check.get("binding_valid"),
                }
                for slot, check in slot_checks.items()
                if isinstance(check, dict)
            ]
            normalized_slots = [str(slot) for slot in slot_checks]
        else:
            normalized_slot_checks = [
                {
                    "slot": str(check.get("slot") or ""),
                    "binding_valid": check.get("binding_valid"),
                }
                for check in slot_checks or []
                if isinstance(check, dict)
            ]
            normalized_slots = (
                [str(slot) for slot in slots] if isinstance(slots, list) else []
            )
        normalized.append(
            {
                "premise_ref": str(raw.get("premise_ref") or ""),
                "fragment_entailed": raw.get("fragment_entailed"),
                "scope_consistent": raw.get("scope_consistent"),
                "proposition_bindings_valid": raw.get("proposition_bindings_valid"),
                "evidence_relation_valid": raw.get("evidence_relation_valid"),
                "declared_proposition_slots": sorted(normalized_slots),
                "proposition_slot_checks": sorted(
                    normalized_slot_checks,
                    key=lambda check: check["slot"],
                ),
            }
        )
    return sorted(normalized, key=lambda check: check["premise_ref"])


def _normalized_conclusion_check(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {
        key: value.get(key)
        for key in (
            "conclusion_entailed",
            "actor_consistent",
            "predicate_consistent",
            "object_consistent",
            "polarity_consistent",
            "quantifier_consistent",
            "scope_consistent",
        )
        if key in value
    }


def _response_payload(response: Any) -> dict[str, Any] | None:
    try:
        payload = json.loads(response_text(response))
    except (TypeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _call_proposal(
    llm: Any,
    prompt: str,
    *,
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    seed: int,
    correction_reason: str,
    candidate: str,
    applicable_proposition_slots: Collection[str] | None,
) -> StageCallResult:
    try:
        return StageCallResult(
            llm(
                [
                    SystemMessage(content=SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT),
                    HumanMessage(content=_corrected_prompt(prompt, correction_reason)),
                ],
                max_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                response_format=semantic_proposition_response_format(
                    [],
                    [value["slot_id"] for value in slots],
                    candidate=candidate,
                    applicable_proposition_slots=applicable_proposition_slots,
                ),
                temperature=0,
                top_p=1,
                seed=seed,
            ),
        )
    except Exception as exc:
        LOGGER.exception("Semantic proposition verifier model call failed")
        failure, detail = provider_failure(exc)
        return StageCallResult(None, failure, detail)


def _call_audit(
    llm: Any,
    prompt: str,
    *,
    premise_labels: list[str],
    seed: int,
    correction_reason: str,
    premise_slot_expectations: dict[str, Collection[str]] | None,
    premise_slot_evidence: dict[str, dict[str, Any]] | None,
) -> StageCallResult:
    try:
        response_format = semantic_entailment_audit_response_format(
            premise_labels,
            premise_slot_expectations=premise_slot_expectations,
            premise_slot_evidence=premise_slot_evidence,
        )
    except ValueError as exc:
        return StageCallResult(
            None,
            PRE_AUDIT_SCHEMA_VALIDATION_FAILED,
            str(exc)[:4000],
            False,
        )
    try:
        return StageCallResult(
            llm(
                [
                    SystemMessage(content=SEMANTIC_ENTAILMENT_AUDIT_SYSTEM_PROMPT),
                    HumanMessage(content=_corrected_prompt(prompt, correction_reason)),
                ],
                max_tokens=SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
                response_format=response_format,
                temperature=0,
                top_p=1,
                seed=seed,
            ),
        )
    except Exception as exc:
        LOGGER.exception("Semantic entailment audit model call failed")
        failure, detail = provider_failure(exc)
        return StageCallResult(None, failure, detail)


def _call_candidate_unknown_audit(
    llm: Any,
    prompt: str,
    *,
    candidate: str,
    verifier_judgment: str,
    seed: int,
    correction_reason: str,
) -> StageCallResult:
    try:
        return StageCallResult(
            llm(
                [
                    SystemMessage(content=UNKNOWN_AUDIT_SYSTEM_PROMPT),
                    HumanMessage(content=_corrected_prompt(prompt, correction_reason)),
                ],
                max_tokens=UNKNOWN_AUDIT_MAX_TOKENS,
                response_format=candidate_unknown_audit_response_format(
                    candidate,
                    verifier_judgment=verifier_judgment,
                ),
                temperature=0,
                top_p=1,
                seed=seed,
            ),
        )
    except Exception as exc:
        LOGGER.exception("Candidate-bound unknown audit model call failed")
        failure, detail = provider_failure(exc)
        return StageCallResult(None, failure, detail)


def _pre_audit_failure_stage(reason: str) -> ParsedSemanticStage:
    return ParsedSemanticStage(
        None,
        None,
        reason,
        reason,
        0,
        "",
        0,
        (),
    )


def _corrected_prompt(prompt: str, failure_reason: str) -> str:
    if not failure_reason:
        return prompt
    correction = {
        "unexpected_unknown_assessment": (
            "For candidate_judgment=supported or contradicted, omit "
            "unknown_assessment entirely. unknown requires a non-empty "
            "unknown_assessment, both entailment flags false, and premises=[]. "
            "Do not emit proof_mode; runtime derives it from premise count."
        ),
        "unknown_assessment_schema_invalid": (
            "unknown requires a complete non-empty unknown_assessment object; "
            "reviewed spans and unresolved proposition slots must be non-empty, "
            "and unknown must use premises=[]. Do not emit proof_mode."
        ),
        "verdict_payload_inconsistent": (
            "supported or contradicted requires one to four premises, both "
            "entailment flags true, and no unknown_assessment; unknown requires "
            "false flags and no premises. Do not emit proof_mode; runtime derives "
            "it from premise count."
        ),
        "proof_mode_premise_count_mismatch": (
            "Do not emit proof_mode. Keep the same candidate judgment and premise "
            "semantics; runtime derives proof mode from premise count."
        ),
        "proposition_slot_coverage_incomplete": (
            "Declare only the proposition slots established by each quote, but "
            "ensure the union across the evidence set covers every applicable "
            "proposition slot."
        ),
        "semantic_entailment_premise_quote_not_proof": (
            "Use an assertive sentence from the exact canonical evidence span, "
            "not a heading, fragment, label, or model/architecture declaration."
        ),
        "semantic_entailment_premise_fragment_not_in_quote": (
            "Keep proposition_fragment as a normalized contiguous statement "
            "that occurs inside its exact quoted evidence span."
        ),
        "semantic_entailment_proposition_binding_unbound": (
            "Every declared actor, predicate, object, and quantifier binding must "
            "be explicitly supported by that premise's exact quote and match the "
            "typed proposition; omit unsupported bindings."
        ),
        "premise_check_slots_invalid": (
            "Return every schema-required proposition slot exactly once using "
            "its controlled evidence_ref."
        ),
        "premise_check_slots_inconsistent": (
            "Keep every binding_valid decision unchanged; runtime derives the "
            "combined proposition binding state."
        ),
        "premise_check_slot_evidence_invalid": (
            "Use the exact controlled evidence_ref required by the response "
            "schema. Do not generate or rewrite evidence text."
        ),
    }.get(
        failure_reason,
        "Return one complete object that follows every schema and cross-field "
        "requirement.",
    )
    return (
        f"{prompt}\n\nYour previous response was rejected by the local parser "
        f"({failure_reason}). {correction}"
    )
