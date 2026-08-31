from __future__ import annotations

from collections.abc import Collection, Mapping
from copy import deepcopy
from typing import Any

from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_lexical import (
    canonical_proposition_object_token_set,
)

from .mara_semantic_proposition_causal_lineage import plan_decision_trace_fields


def plan_construction_lineage(
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
    fields = _plan_fields(
        selected,
        selected_plan_id=selected_plan_id,
        context=context,
        selectors=selectors,
        applicable_proposition_slots=applicable_proposition_slots,
    )
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
    return selector, _construction_record(
        trace,
        selector=selector,
        plans=plans,
        selected=selected,
        selected_plan_id=selected_plan_id,
        semantic_status=semantic_status,
        transport_status=transport_status,
        reason=reason,
        fields=fields,
    )


def _plan_fields(
    selected: Mapping[str, Any] | None,
    *,
    selected_plan_id: str,
    context: Any,
    selectors: list[dict[str, Any]],
    applicable_proposition_slots: Collection[str] | None,
) -> dict[str, Any]:
    required_slots = _string_list(applicable_proposition_slots)
    if selected is not None:
        raw_slot_refs = selected.get("slot_refs")
        required_slots = (
            _string_list(list(raw_slot_refs))
            if isinstance(raw_slot_refs, Mapping)
            else []
        )
        return {
            "authority_source": "frozen_canonical_proposition_plan",
            "required_tokens": _string_list(selected.get("required_object_tokens")),
            "covered_tokens": _string_list(selected.get("covered_object_tokens")),
            "covered_slots": (
                _string_list(list(raw_slot_refs.keys()))
                if isinstance(raw_slot_refs, Mapping)
                else []
            ),
            "event_ids": _event_ids(selected.get("event_subplans")),
            "canonical_plan_digest": str(
                selected.get("plan_digest")
                or selected.get("canonical_plan_digest")
                or selected.get("plan_id")
                or ""
            ),
            "required_slots": required_slots,
        }
    if selected_plan_id:
        return {
            "authority_source": "selected_frozen_plan_missing",
            "required_tokens": [],
            "covered_tokens": [],
            "covered_slots": [],
            "event_ids": [],
            "canonical_plan_digest": "",
            "required_slots": required_slots,
        }
    covered_slots, covered_tokens, event_ids = _plan_coverage(
        selected,
        selectors,
    )
    return {
        "authority_source": "question_proposition_expectation",
        "required_tokens": _question_object_tokens(context),
        "covered_tokens": covered_tokens,
        "covered_slots": covered_slots,
        "event_ids": event_ids,
        "canonical_plan_digest": "",
        "required_slots": required_slots,
    }


def _construction_record(
    trace: Mapping[str, Any],
    *,
    selector: Mapping[str, Any],
    plans: Mapping[str, Mapping[str, Any]],
    selected: Mapping[str, Any] | None,
    selected_plan_id: str,
    semantic_status: str,
    transport_status: str,
    reason: str,
    fields: Mapping[str, Any],
) -> dict[str, Any]:
    rejected = trace.get("best_rejected")
    rejected = rejected if isinstance(rejected, Mapping) else {}
    required_slots = list(fields["required_slots"])
    event_ids = list(fields["event_ids"])
    if selected is None and not event_ids:
        event_ids = list(selector["event_ids"])
    return {
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
        "authority_source": fields["authority_source"],
        "canonical_projection_status": (
            "selected_frozen_plan_pending_validation"
            if selected is not None
            else "not_applicable"
        ),
        "canonical_plan_digest": fields["canonical_plan_digest"],
        "required_slots": required_slots,
        "covered_slots": _ordered_subset(
            fields["covered_slots"],
            required_slots,
        ),
        "required_tokens": fields["required_tokens"],
        "covered_tokens": fields["covered_tokens"],
        "required_object_tokens": fields["required_tokens"],
        "covered_object_tokens": fields["covered_tokens"],
        "event_ids": event_ids,
        "event_subplans": deepcopy(
            selected.get("event_subplans") or []
            if isinstance(selected, Mapping)
            else []
        ),
        "slot_refs": deepcopy(
            selected.get("slot_refs") or [] if isinstance(selected, Mapping) else {}
        ),
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


def _event_ids(raw_subplans: Any) -> list[str]:
    if not isinstance(raw_subplans, list):
        return []
    return _string_list(
        [value.get("event_id") for value in raw_subplans if isinstance(value, Mapping)]
    )


def _ordered_subset(values: list[str], order: list[str]) -> list[str]:
    value_set = set(values)
    ordered = [value for value in order if value in value_set]
    return ordered + [value for value in values if value not in set(order)]


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return []
    return list(dict.fromkeys(str(item) for item in value if str(item)))
