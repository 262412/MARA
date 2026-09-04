from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan_contract import (
    canonical_selector_sort_key,
)

from .mara_semantic_proposition_causal_lineage import (
    finalize_decisive_transition,
    record_candidate_bound_decisive_transition,
    record_plan_decisive_transition,
)
from .mara_semantic_proposition_debug import response_text
from .mara_semantic_proposition_lineage_packing import (
    empty_source_packing_lineage,
    source_packing_lineage,
)
from .mara_semantic_proposition_lineage_plan import (
    plan_construction_lineage as _plan_construction_lineage,
)
from .mara_semantic_proposition_lineage_proposal import proposal_lineage_fields

SEMANTIC_PROPOSITION_DATA_LINEAGE_CONTRACT = "semantic_proposition_data_lineage.v1"


def record_proposal_data_lineage(
    diagnostics: dict[str, Any],
    stage: Any,
    *,
    context: Any,
    candidate: str,
    applicable_proposition_slots: Collection[str] | None,
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]] | None,
) -> None:
    stage_value = stage.value if isinstance(stage.value, Mapping) else {}
    selectors = _context_selectors(context)
    lineage = _lineage(diagnostics)
    lineage.update(
        proposal_lineage_fields(
            context=context,
            candidate=candidate,
            selectors=selectors,
            stage_value=stage_value,
            proposal_attempts=_attempt_lineage(stage),
            applicable_proposition_slots=applicable_proposition_slots,
            allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
            allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
        )
    )
    selector, construction = _plan_construction_lineage(
        context=context,
        selectors=selectors,
        candidate=candidate,
        applicable_proposition_slots=applicable_proposition_slots,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
        selected_plan_id=str(stage_value.get("canonical_evidence_plan_id") or ""),
    )
    lineage["selector"] = selector
    lineage["plan_construction"] = construction
    lineage["source_packing"] = source_packing_lineage(context)
    record_plan_decisive_transition(lineage, candidate=candidate)
    _record_early_plan_construction_failure(lineage, construction)
    _record_stage_first_inconsistency(
        lineage,
        stage,
        provider_stage="proposal_provider",
        parser_stage="proposal_parse",
    )


def record_audit_data_lineage(diagnostics: dict[str, Any], stage: Any) -> None:
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


def record_validated_plan_projection_lineage(
    diagnostics: dict[str, Any],
    projection: Any,
) -> None:
    """Bind plan-construction lineage to the validated frozen projection."""

    lineage = _lineage(diagnostics)
    construction = lineage.get("plan_construction")
    if not isinstance(construction, dict):
        return
    event_subplans = [
        dict(value)
        for value in getattr(projection, "event_subplans", ()) or ()
        if isinstance(value, Mapping)
    ]
    construction.update(
        {
            "authority_source": "frozen_canonical_proposition_plan",
            "canonical_projection_status": "validated",
            "selected_plan_id": str(getattr(projection, "plan_id", "") or ""),
            "canonical_plan_digest": str(getattr(projection, "plan_digest", "") or ""),
            "canonical_projection_digest": _canonical_digest(projection.as_dict()),
            "required_slots": _string_list(getattr(projection, "required_slots", ())),
            "covered_slots": _string_list(getattr(projection, "required_slots", ())),
            "required_tokens": _string_list(
                getattr(projection, "required_object_tokens", ())
            ),
            "covered_tokens": _string_list(
                getattr(projection, "covered_object_tokens", ())
            ),
            "required_object_tokens": _string_list(
                getattr(projection, "required_object_tokens", ())
            ),
            "covered_object_tokens": _string_list(
                getattr(projection, "covered_object_tokens", ())
            ),
            "event_ids": _string_list(
                [value.get("event_id") for value in event_subplans]
            ),
            "event_subplans": event_subplans,
            "slot_refs": {
                str(slot): _string_list(refs)
                for slot, refs in dict(
                    getattr(projection, "slot_refs", {}) or {}
                ).items()
            },
        }
    )


def record_runtime_authority_rejection(
    diagnostics: dict[str, Any],
    *,
    reason: str,
    outcome_status: str,
    evidence_digest: str = "",
    semantic_pack_digest: str = "",
    slot_state_digest: str = "",
    proposition_binding_digest: str = "",
    canonical_plan_id: str = "",
    canonical_plan_digest: str = "",
    canonical_projection_digest: str = "",
) -> None:
    """Make a post-lineage runtime rejection the first decisive failure."""

    lineage = _lineage(diagnostics)
    previous = lineage.get("first_decisive_transition")
    if (
        isinstance(previous, Mapping)
        and previous
        and str(previous.get("stage") or "") != "runtime_authority"
    ):
        lineage.setdefault("prior_first_decisive_transition", dict(previous))
    context = {
        "reason": str(reason or ""),
        "outcome_status": str(outcome_status or ""),
        "audit_status": str(diagnostics.get("audit_status") or ""),
        "audit_reason": str(diagnostics.get("audit_reason") or ""),
        "canonical_plan_id": str(canonical_plan_id or ""),
        "canonical_plan_digest": str(canonical_plan_digest or ""),
        "canonical_projection_digest": str(canonical_projection_digest or ""),
        "evidence_digest": str(evidence_digest or ""),
        "semantic_pack_digest": str(semantic_pack_digest or ""),
        "slot_state_digest": str(slot_state_digest or ""),
        "proposition_binding_digest": str(proposition_binding_digest or ""),
    }
    transition = {
        "stage": "runtime_authority",
        "decision": "runtime_authority_rejected",
        "candidate": str(lineage.get("candidate") or ""),
        "classification_hint": "runtime_authority_rejection",
        "decision_context": context,
        "decision_context_digest": _canonical_digest(context),
        "observation_digest": _canonical_digest(
            {
                "reason": context["reason"],
                "outcome_status": context["outcome_status"],
                "canonical_projection_digest": context["canonical_projection_digest"],
            }
        ),
    }
    lineage["runtime_authority"] = {
        "status": "rejected",
        "reason": context["reason"],
        "canonical_plan_id": context["canonical_plan_id"],
        "canonical_plan_digest": context["canonical_plan_digest"],
        "canonical_projection_digest": context["canonical_projection_digest"],
        "evidence_digest": context["evidence_digest"],
        "semantic_pack_digest": context["semantic_pack_digest"],
        "slot_state_digest": context["slot_state_digest"],
        "proposition_binding_digest": context["proposition_binding_digest"],
    }
    lineage["first_decisive_transition"] = transition
    lineage["status"] = "failed"


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
    if str(diagnostics.get("audit_status") or "") == "candidate_bound":
        record_candidate_bound_decisive_transition(
            lineage,
            status=status,
            reason=reason,
            audit_reason=str(diagnostics.get("audit_reason") or ""),
        )
    construction = lineage.get("plan_construction")
    plan_failed = (
        isinstance(construction, Mapping)
        and str(construction.get("semantic_plan_status") or "") == "failed"
    )
    transport_failed = (
        isinstance(construction, Mapping)
        and str(construction.get("transport_status") or "") == "failed"
    )
    if plan_failed or transport_failed:
        lineage["status"] = "failed"
        _record_plan_construction_inconsistency(lineage)
        if status == "parsed" or lineage.get("first_inconsistency"):
            finalize_decisive_transition(lineage, status=status, reason=reason)
            return
    if status == "parsed" or lineage.get("first_inconsistency"):
        finalize_decisive_transition(lineage, status=status, reason=reason)
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
    finalize_decisive_transition(lineage, status=status, reason=reason)


def _context_selectors(context: Any) -> list[dict[str, Any]]:
    selectors: list[dict[str, Any]] = []
    for record in getattr(context, "packed", ()) or ():
        if not isinstance(record, Mapping):
            continue
        for raw_selector in record.get("selectors") or ():
            if not isinstance(raw_selector, Mapping):
                continue
            selector = dict(raw_selector)
            selector.setdefault("evidence_id", str(record.get("evidence_id") or ""))
            selector.setdefault(
                "slot_hints",
                list(selector.get("allowed_proposition_slots") or ()),
            )
            if selector.get("selector_id"):
                selectors.append(selector)
    return sorted(selectors, key=canonical_selector_sort_key)


def _record_plan_construction_inconsistency(lineage: dict[str, Any]) -> None:
    if lineage.get("first_inconsistency"):
        return
    construction = lineage.get("plan_construction")
    if not isinstance(construction, Mapping):
        return
    lineage["first_inconsistency"] = {
        "stage": "plan_construction",
        "reason": str(construction.get("reason") or "plan_construction_failed"),
        "attempt": 1,
        "raw_response_digest": _canonical_digest(construction),
    }


def _record_early_plan_construction_failure(
    lineage: dict[str, Any],
    construction: Mapping[str, Any],
) -> None:
    if construction.get("status") == "failed":
        lineage["status"] = "failed"
        _record_plan_construction_inconsistency(lineage)


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
        "source_packing": empty_source_packing_lineage(),
        "selector": {
            "status": "not_run",
            "universe": [],
            "universe_refs": [],
            "universe_records": [],
            "candidate_count": 0,
            "event_ids": [],
        },
        "plan_construction": {
            "status": "not_run",
            "transport_status": "not_run",
            "semantic_plan_status": "not_run",
            "universe": [],
            "universe_refs": [],
            "candidate_count": 0,
            "legal_plan_count": 0,
            "valid_candidate_counts": {},
            "best_rejected_candidate": None,
            "best_rejected_candidates": {},
            "reason": "",
            "authority_source": "not_started",
            "canonical_projection_status": "not_run",
            "canonical_plan_digest": "",
            "required_slots": [],
            "covered_slots": [],
            "required_tokens": [],
            "covered_tokens": [],
            "required_object_tokens": [],
            "covered_object_tokens": [],
            "event_ids": [],
            "event_subplans": [],
            "slot_refs": {},
            "selected_plan_id": "",
        },
        "audit": {"status": "not_run", "reason": "", "attempts": []},
        "runtime_authority": {
            "status": "not_run",
            "reason": "",
            "canonical_plan_id": "",
            "canonical_plan_digest": "",
            "canonical_projection_digest": "",
            "evidence_digest": "",
            "semantic_pack_digest": "",
            "slot_state_digest": "",
            "proposition_binding_digest": "",
        },
        "first_inconsistency": {},
        "first_decisive_transition": {},
    }
    diagnostics["semantic_data_lineage"] = lineage
    return lineage


def _attempt_lineage(stage: Any) -> list[dict[str, Any]]:
    attempts: list[dict[str, Any]] = []
    for index, attempt in enumerate(stage.attempts, start=1):
        record = {
            "attempt": index,
            "raw_response_digest": _response_digest(attempt.response),
            "parse_failure_reason": str(attempt.parse_failure_reason or ""),
            "provider_failure_reason": str(attempt.provider_failure_reason or ""),
        }
        request_snapshot = getattr(attempt, "request_snapshot", None)
        snapshot = request_snapshot if isinstance(request_snapshot, Mapping) else {}
        serialization = snapshot.get("serialization")
        if isinstance(serialization, Mapping):
            record.update(
                {
                    "request_snapshot_digest": _canonical_digest(snapshot),
                    "serializer_identity": str(
                        serialization.get("serializer_identity") or ""
                    ),
                    "message_digest": str(serialization.get("message_digest") or ""),
                    "prompt_char_count": serialization.get("prompt_char_count"),
                    "prompt_char_limit": serialization.get("prompt_char_limit"),
                    "input_token_count": serialization.get("input_token_count"),
                    "input_token_limit": serialization.get("input_token_limit"),
                    "failed_before_transport": serialization.get(
                        "failed_before_transport"
                    ),
                    "transport_status": str(
                        serialization.get("transport_status") or ""
                    ),
                    "serialization": dict(serialization),
                }
            )
        attempts.append(record)
    return attempts


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
        serialization = _attempt_serialization(attempt)
        inconsistency_stage = (
            provider_stage
            if attempt.provider_failure_reason
            else _proposal_parser_failure_stage(reason)
            if parser_stage == "proposal_parse"
            else "auditor_message_serialization"
            if serialization.get("failed_before_transport") is True
            else parser_stage
        )
        lineage["first_inconsistency"] = {
            "stage": inconsistency_stage,
            "reason": reason,
            "attempt": index,
            "raw_response_digest": _response_digest(attempt.response),
        }
        if serialization:
            lineage["first_inconsistency"].update(
                {
                    "serializer_identity": str(
                        serialization.get("serializer_identity") or ""
                    ),
                    "message_digest": str(serialization.get("message_digest") or ""),
                    "failed_before_transport": serialization.get(
                        "failed_before_transport"
                    ),
                }
            )
        return


def _attempt_serialization(attempt: Any) -> Mapping[str, Any]:
    snapshot = getattr(attempt, "request_snapshot", None)
    if not isinstance(snapshot, Mapping):
        return {}
    serialization = snapshot.get("serialization")
    return serialization if isinstance(serialization, Mapping) else {}


def _proposal_parser_failure_stage(reason: str) -> str:
    if reason == "canonical_evidence_plan_id_invalid":
        return "plan_lookup"
    if reason == "candidate_judgment_plan_mismatch":
        return "candidate_plan_relation"
    if reason.startswith("canonical_evidence_plan_"):
        return "frozen_plan_projection"
    return "proposal_parse"


def _diagnostic_failure_stage(diagnostics: Mapping[str, Any], reason: str) -> str:
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


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return list(dict.fromkeys(str(item) for item in value if str(item)))
