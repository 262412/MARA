from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from typing import Any

from .mara_semantic_proposition_debug import response_text
from .mara_semantic_proposition_schema import semantic_proposition_response_format

SEMANTIC_PROPOSITION_DATA_LINEAGE_CONTRACT = "semantic_proposition_data_lineage.v1"


def record_proposal_data_lineage(
    diagnostics: dict[str, Any],
    stage: Any,
    *,
    context: Any,
    candidate: str,
    applicable_proposition_slots: Collection[str] | None,
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None,
    allowed_proposition_evidence_plans: (Mapping[str, Mapping[str, Any]] | None),
) -> None:
    plan_mode = allowed_proposition_evidence_plans is not None
    response_format = semantic_proposition_response_format(
        [
            str(selector.get("selector_id") or "")
            for record in context.packed
            for selector in record.get("selectors") or []
            if str(selector.get("selector_id") or "")
        ],
        [str(slot.get("slot_id") or "") for slot in context.slots],
        candidate=candidate,
        applicable_proposition_slots=applicable_proposition_slots,
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )
    lineage = _lineage(diagnostics)
    lineage.update(
        {
            "identities": {
                "semantic_pack_digest": str(context.semantic_pack_digest or ""),
                "canonical_span_universe_digest": str(
                    context.canonical_span_universe_digest or ""
                ),
                "candidate_transaction_id": str(context.candidate_transaction_id or ""),
            },
            "proposal_contract": {
                "mode": (
                    "canonical_plan_selection"
                    if plan_mode
                    else "model_premise_generation"
                ),
                "allowed_plan_ids": sorted(
                    str(plan_id)
                    for plan_id in (allowed_proposition_evidence_plans or {})
                    if str(plan_id)
                ),
                "response_schema_digest": _canonical_digest(
                    response_format.get("json_schema", {}).get("schema", {})
                ),
            },
            "proposal_attempts": _attempt_lineage(stage),
            "local_projection": {
                "status": (
                    "passed"
                    if plan_mode and stage.value is not None
                    else "not_run"
                    if plan_mode
                    else "not_applicable"
                ),
                "selected_plan_id": str(
                    (stage.value or {}).get("canonical_evidence_plan_id") or ""
                ),
            },
        }
    )
    _record_stage_first_inconsistency(
        lineage,
        stage,
        provider_stage="proposal_provider",
        parser_stage="proposal_parse",
    )


def record_audit_data_lineage(
    diagnostics: dict[str, Any],
    stage: Any,
) -> None:
    lineage = _lineage(diagnostics)
    lineage["audit"] = {
        "status": (
            "provider_failed"
            if stage.provider_failure_reason
            else "not_run"
            if stage.call_count == 0 and stage.value is None
            else "parse_failed"
            if stage.value is None
            else "parsed"
        ),
        "reason": str(stage.provider_failure_reason or stage.failure_reason or ""),
        "attempts": _attempt_lineage(stage),
    }
    _record_stage_first_inconsistency(
        lineage,
        stage,
        provider_stage="audit_provider",
        parser_stage="audit_parse",
    )


def finalize_semantic_data_lineage(
    diagnostics: dict[str, Any],
    *,
    status: str,
    reason: str,
) -> None:
    lineage = _lineage(diagnostics)
    lineage["status"] = "passed" if status == "parsed" else "failed"
    lineage.setdefault(
        "audit",
        {
            "status": str(diagnostics.get("audit_status") or "not_run"),
            "reason": str(diagnostics.get("audit_reason") or ""),
            "attempts": [],
        },
    )
    if status == "parsed" or lineage.get("first_inconsistency"):
        return
    stage = _diagnostic_failure_stage(diagnostics, reason)
    attempt = 0
    raw_response_digest = ""
    if stage in {"auditor_semantics", "local_semantic_constraint"}:
        audit_attempts = lineage.get("audit", {}).get("attempts", [])
        if audit_attempts:
            latest_attempt = audit_attempts[-1]
            attempt = int(latest_attempt.get("attempt") or 0)
            raw_response_digest = str(latest_attempt.get("raw_response_digest") or "")
    failure_reason = (
        str(diagnostics.get("audit_reason") or "")
        if stage == "auditor_semantics"
        else str(reason or diagnostics.get("audit_reason") or status)
    )
    lineage["first_inconsistency"] = {
        "stage": stage,
        "reason": failure_reason,
        "attempt": attempt,
        "raw_response_digest": raw_response_digest,
    }


def _lineage(diagnostics: dict[str, Any]) -> dict[str, Any]:
    value = diagnostics.get("semantic_data_lineage")
    if isinstance(value, dict):
        return value
    lineage = {
        "contract_id": SEMANTIC_PROPOSITION_DATA_LINEAGE_CONTRACT,
        "status": "in_progress",
        "identities": {
            "semantic_pack_digest": str(diagnostics.get("semantic_pack_digest") or ""),
            "canonical_span_universe_digest": "",
            "candidate_transaction_id": "",
        },
        "proposal_contract": {
            "mode": "not_started",
            "allowed_plan_ids": [],
            "response_schema_digest": "",
        },
        "proposal_attempts": [],
        "local_projection": {"status": "not_run", "selected_plan_id": ""},
        "audit": {"status": "not_run", "reason": "", "attempts": []},
        "first_inconsistency": {},
    }
    diagnostics["semantic_data_lineage"] = lineage
    return lineage


def _attempt_lineage(stage: Any) -> list[dict[str, Any]]:
    return [
        {
            "attempt": index,
            "raw_response_digest": _response_digest(attempt.response),
            "parse_failure_reason": str(attempt.parse_failure_reason or ""),
            "provider_failure_reason": str(attempt.provider_failure_reason or ""),
        }
        for index, attempt in enumerate(stage.attempts, start=1)
    ]


def _record_stage_first_inconsistency(
    lineage: dict[str, Any],
    stage: Any,
    *,
    provider_stage: str,
    parser_stage: str,
) -> None:
    if lineage.get("first_inconsistency"):
        return
    for index, attempt in enumerate(stage.attempts, start=1):
        reason = str(
            attempt.provider_failure_reason or attempt.parse_failure_reason or ""
        )
        if not reason:
            continue
        lineage["first_inconsistency"] = {
            "stage": (
                provider_stage
                if attempt.provider_failure_reason
                else _proposal_parser_failure_stage(reason)
                if parser_stage == "proposal_parse"
                else parser_stage
            ),
            "reason": reason,
            "attempt": index,
            "raw_response_digest": _response_digest(attempt.response),
        }
        return


def _proposal_parser_failure_stage(reason: str) -> str:
    if reason == "canonical_evidence_plan_id_invalid":
        return "plan_lookup"
    if reason == "candidate_judgment_plan_mismatch":
        return "candidate_plan_relation"
    if reason.startswith("canonical_evidence_plan_"):
        return "frozen_plan_projection"
    return "proposal_parse"


def _diagnostic_failure_stage(
    diagnostics: Mapping[str, Any],
    reason: str,
) -> str:
    if str(reason).startswith("release_"):
        return "transaction_preflight"
    if str(diagnostics.get("audit_execution_status") or "") == "provider_failed":
        return "audit_provider"
    if str(diagnostics.get("audit_parse_failure_reason") or ""):
        return "audit_parse"
    constraint = diagnostics.get("independent_semantic_constraint")
    if isinstance(constraint, Mapping) and constraint.get("status") == "rejected":
        return "local_semantic_constraint"
    if str(diagnostics.get("audit_reason") or ""):
        return "auditor_semantics"
    if str(diagnostics.get("question_proposition_status") or "") not in {
        "",
        "complete",
    }:
        return "proposition_resolution"
    return "transaction_runtime"


def _response_digest(response: Any | None) -> str:
    if response is None:
        return ""
    return hashlib.sha256(response_text(response).encode("utf-8")).hexdigest()


def _canonical_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
