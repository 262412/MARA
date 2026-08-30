from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan_contract import (
    canonical_selector_sort_key,
)
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_lexical import (
    canonical_proposition_object_token_set,
)

from .mara_semantic_proposition_causal_lineage import (
    finalize_decisive_transition,
    plan_decision_trace_fields,
    record_candidate_bound_decisive_transition,
    record_plan_decisive_transition,
)
from .mara_semantic_proposition_debug import response_text
from .mara_semantic_proposition_lineage_packing import (
    empty_source_packing_lineage,
    source_packing_lineage,
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


def _plan_construction_lineage(
    *,
    context: Any,
    selectors: list[dict[str, Any]],
    candidate: str,
    applicable_proposition_slots: Collection[str] | None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]] | None,
    selected_plan_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    trace = _trace_from_context(context)
    if trace is None:
        trace = {
            "selector_count": len(selectors),
            "candidate_count": len(selectors),
            "event_ids": [
                str(value.get("event_id") or "")
                for value in selectors
                if str(value.get("event_id") or "")
            ],
        }
    selector = _selector_lineage(trace, selectors)
    plans = _normalised_plans(allowed_proposition_evidence_plans)
    selected = plans.get(selected_plan_id)
    required_slots = _string_list(applicable_proposition_slots)
    required_tokens = _question_object_tokens(context)
    covered_slots, covered_tokens, event_ids = _plan_coverage(selected, selectors)
    semantic_status, reason = _plan_status_and_reason(
        trace,
        plans=plans,
        candidate=candidate,
    )
    transport_status = _plan_transport_status(
        allowed_proposition_evidence_plans,
        plans=plans,
        selected_plan_id=selected_plan_id,
    )
    if transport_status == "failed":
        reason = "selected_plan_not_allowed"
    rejected = trace.get("best_rejected")
    rejected = rejected if isinstance(rejected, Mapping) else {}
    return selector, {
        "status": (
            "failed" if "failed" in {semantic_status, transport_status} else "passed"
        ),
        "transport_status": transport_status,
        "semantic_plan_status": semantic_status,
        "universe": selector["universe_refs"],
        "universe_refs": selector["universe_refs"],
        "candidate_count": int(
            trace.get("candidate_count") or len(selector["universe_refs"])
        ),
        "legal_plan_count": len(plans),
        "valid_candidate_counts": {
            str(key): int(value)
            for key, value in (trace.get("valid_candidate_counts") or {}).items()
        },
        "best_rejected_candidate": dict(next(iter(rejected.values()), {}))
        if rejected
        else None,
        "best_rejected_candidates": {
            str(key): dict(value)
            for key, value in rejected.items()
            if isinstance(value, Mapping)
        },
        "reason": reason,
        "required_slots": required_slots,
        "covered_slots": _ordered_subset(covered_slots, required_slots),
        "required_tokens": required_tokens,
        "covered_tokens": covered_tokens,
        "required_object_tokens": required_tokens,
        "covered_object_tokens": covered_tokens,
        "event_ids": event_ids or selector["event_ids"],
        "selected_plan_id": selected_plan_id,
        **plan_decision_trace_fields(trace),
    }


def _selector_lineage(
    trace: Mapping[str, Any],
    selectors: list[dict[str, Any]],
) -> dict[str, Any]:
    refs = _string_list(
        trace.get("selector_universe_refs") or trace.get("universe_refs")
    ) or [str(value.get("selector_id") or "") for value in selectors]
    return {
        "status": "passed" if refs else "failed",
        "universe": refs,
        "universe_refs": refs,
        "universe_records": [dict(value) for value in selectors],
        "candidate_count": int(trace.get("selector_count") or len(refs)),
        "event_ids": _string_list(trace.get("event_ids"))
        or sorted(
            {
                str(value.get("event_id") or "")
                for value in selectors
                if str(value.get("event_id") or "")
            }
        ),
    }


def _plan_status_and_reason(
    trace: Mapping[str, Any],
    *,
    plans: Mapping[str, Mapping[str, Any]],
    candidate: str,
) -> tuple[str, str]:
    state = str(trace.get("binding_state") or trace.get("state") or "")
    ambiguous = trace.get("ambiguous") is True or state in {
        "ambiguous",
        "ambiguous_conflict",
    }
    if plans:
        status = "passed"
    elif str(candidate or "").casefold() in {"yes", "no"} and not ambiguous:
        status = "failed"
    else:
        status = "not_applicable"
    reason = str(trace.get("reason") or "")
    if not reason:
        reason = {
            "failed": "no_legal_evidence_plan",
            "not_applicable": "candidate_not_answerable",
        }.get(status, "")
    return status, reason


def _plan_transport_status(
    supplied_plans: Mapping[str, Mapping[str, Any]] | None,
    *,
    plans: Mapping[str, Mapping[str, Any]],
    selected_plan_id: str,
) -> str:
    if supplied_plans is None:
        return "not_applicable"
    if not plans:
        return "passed"
    if not selected_plan_id:
        return "not_run"
    return "passed" if selected_plan_id in plans else "failed"


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


def _trace_from_context(context: Any) -> Mapping[str, Any] | None:
    for value in (
        getattr(context, "plan_construction_trace", None),
        getattr(context, "construction_trace", None),
        getattr(context, "selection_trace", None),
    ):
        if isinstance(value, Mapping):
            return value
    for record in getattr(context, "packed", ()) or ():
        if not isinstance(record, Mapping):
            continue
        for key in ("plan_construction_trace", "construction_trace"):
            value = record.get(key)
            if isinstance(value, Mapping):
                return value
    return None


def _normalised_plans(
    plans: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Mapping[str, Any]]:
    return {
        str(plan_id): value
        for plan_id, value in (plans or {}).items()
        if str(plan_id) and isinstance(value, Mapping)
    }


def _plan_coverage(
    plan: Mapping[str, Any] | None,
    selectors: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    if not isinstance(plan, Mapping):
        return [], [], []
    refs = set(_string_list(plan.get("span_refs")))
    slot_refs = plan.get("slot_refs")
    covered_slots = (
        [str(slot) for slot, refs in slot_refs.items() if refs]
        if isinstance(slot_refs, Mapping)
        else []
    )
    covered_tokens = _string_list(plan.get("covered_object_tokens"))
    event_ids = sorted(
        {
            str(selector.get("event_id") or "")
            for selector in selectors
            if str(selector.get("selector_id") or "") in refs
            and str(selector.get("event_id") or "")
        }
    )
    return covered_slots, covered_tokens, event_ids


def _question_object_tokens(context: Any) -> list[str]:
    question = str(getattr(context, "question", "") or "")
    if not question:
        return []
    return sorted(
        canonical_proposition_object_token_set(build_question_proposition(question))
    )


def _ordered_subset(values: list[str], order: list[str]) -> list[str]:
    value_set = set(values)
    ordered = [value for value in order if value in value_set]
    return ordered + [value for value in values if value not in set(order)]


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
            "required_slots": [],
            "covered_slots": [],
            "required_tokens": [],
            "covered_tokens": [],
            "required_object_tokens": [],
            "covered_object_tokens": [],
            "event_ids": [],
            "selected_plan_id": "",
        },
        "audit": {"status": "not_run", "reason": "", "attempts": []},
        "first_inconsistency": {},
        "first_decisive_transition": {},
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
