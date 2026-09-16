"""Observe real binder state/assessment calls without replacing their behavior."""

from collections import Counter
from contextlib import ExitStack
from copy import deepcopy
from typing import Any
from unittest.mock import patch

from ktem.docqa import boolean_proposition_candidates as candidates
from ktem.docqa import boolean_proposition_evidence as propositions
from ktem.docqa import query_evidence_binding as binding
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.selection_assessment_snapshot import SelectionAssessmentSnapshot
from ktem_tests.binding_contract_inputs import case_inputs
from ktem_tests.plan_policy_characterization import lossless


def _audit(snapshot):
    if snapshot is None:
        return None
    observed = snapshot.audit()
    assert isinstance(observed["time_spent_ms"], (float, int))
    assert observed["time_spent_ms"] >= 0
    return {**observed, "time_spent_ms": "elapsed milliseconds"}


def _observe_calls(stack, calls):
    for name in (
        "_existing_binding_state",
        "_candidate_score",
        "_slot_binding_quality",
        "_bound_slot_status",
        "_update_bound_operand_state",
        "reconcile_boolean_binding_slots",
    ):
        original = getattr(binding, name)

        def observe(*args, _name=name, _original=original, **kwargs):
            entry = {"stage": _name}
            slot_index = (
                0
                if _name in {"_slot_binding_quality", "_update_bound_operand_state"}
                else 1
            )
            if _name == "reconcile_boolean_binding_slots":
                entry["slots"] = [slot.as_dict() for slot in args[1]]
                entry["identities"] = list(args[2])
            else:
                entry["slot"] = args[slot_index].slot_id
            if _name == "_candidate_score":
                entry["identity"] = identity_of(args[2]).key
            calls.append(entry)
            value = _original(*args, **kwargs)
            if _name in {
                "_existing_binding_state",
                "_candidate_score",
                "_slot_binding_quality",
                "_bound_slot_status",
            }:
                entry["result"] = list(value) if isinstance(value, tuple) else value
            if _name == "_update_bound_operand_state":
                entry["operand_items"] = deepcopy(args[3])
                # Sets have no public iteration contract; compare membership as a mapping.
                entry["used_generic_ids"] = dict.fromkeys(args[4], True)
            return value

        stack.enter_context(patch.object(binding, name, observe))


def observe_binding(name, mode, snapshot_mode):
    plan, rounds = deepcopy(case_inputs(name))
    calls: list[dict[str, Any]] = []
    observations = []
    classifications: Counter[str] = Counter()
    original = propositions.classify_boolean_evidence_candidates

    def classify(question, answer, record):
        classifications[str(record.get("evidence_id") or "")] += 1
        return original(question, answer, record)

    snapshot: SelectionAssessmentSnapshot | None = None
    with ExitStack() as stack:
        _observe_calls(stack, calls)
        for module in (propositions, candidates):
            stack.enter_context(
                patch.object(module, "classify_boolean_evidence_candidates", classify)
            )
        for items in rounds:
            if snapshot_mode:
                snapshot = (
                    snapshot.expanded(plan, items)
                    if snapshot is not None
                    else SelectionAssessmentSnapshot.build(plan, items)
                )
            observations.append(
                _bind_round(plan, items, mode, snapshot, calls, classifications)
            )
            if "error" in observations[-1]:
                break
            plan = observations[-1].pop("_plan_object")
    return lossless(observations)


def _bind_round(plan, items, mode, snapshot, calls, classifications):
    before = {
        "plan": plan.as_dict(),
        "items": deepcopy(items),
        "audit": _audit(snapshot),
        "classifications": dict(classifications),
    }
    calls.clear()
    try:
        if mode == "monotonic":
            bound, trace = binding.bind_evidence_slots_monotonic(
                plan, items, assessments=snapshot
            )
        else:
            bound = binding.bind_evidence_slots(plan, items, assessments=snapshot)
            trace = []
    except (ValueError, RuntimeError) as error:
        return {
            "before": before,
            "calls": deepcopy(calls),
            "error": [type(error).__name__, str(error)],
            "audit": _audit(snapshot),
            "classifications": dict(classifications),
        }
    return {
        "before": before,
        "after": bound.as_dict(),
        "trace": trace,
        "calls": deepcopy(calls),
        "items_after": deepcopy(items),
        "audit": _audit(snapshot),
        "classifications": dict(classifications),
        "same_slot_objects": [
            old is new for old, new in zip(plan.evidence_slots, bound.evidence_slots)
        ],
        "same_constraints": bound.constraints is plan.constraints,
        "_plan_object": bound,
    }
