from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

LOCAL_SEMANTIC_RELATION_CONSTRAINT = "local_semantic_relation_constraint.v1"


def frozen_semantic_relation_evidence_set_constraint(
    projection: Any,
    verdict: str,
    *,
    auditor_relationship: str,
) -> dict[str, Any]:
    relation = str(getattr(projection, "polarity_relation", "") or "")
    expected_verdict = {
        "proposition_support": "yes",
        "explicit_contradiction": "no",
    }.get(relation)
    supplied = str(verdict or "")
    polarity_valid = _polarity_valid(relation, expected_verdict, supplied)
    analyses: list[dict[str, Any]] = []
    for premise in projection.premises:
        analysis = _frozen_premise_analysis(projection, premise)
        if analysis["status"] not in {
            "affirmative_assertion",
            "explicit_contradiction",
            "unbound",
        }:
            polarity_valid = False
        analyses.append(analysis)
    return _frozen_constraint_payload(
        projection,
        supplied,
        polarity_valid=polarity_valid,
        analyses=analyses,
        auditor_relationship=auditor_relationship,
    )


def frozen_semantic_relation_analyses(
    projection: Any,
    verdict: str,
) -> tuple[dict[str, Any], ...]:
    """Return relation records already validated by the frozen projection."""

    constraint = frozen_semantic_relation_evidence_set_constraint(
        projection,
        verdict,
        auditor_relationship="",
    )
    if constraint.get("status") != "passed":
        return ()
    return tuple(constraint.get("premise_analyses") or ())


def premise_slot_evidence_for_audit(
    constraint: Mapping[str, Any],
    *,
    canonical_plan_projection: Any | None = None,
) -> dict[str, dict[str, dict[str, Any]]]:
    if canonical_plan_projection is not None:
        return {
            premise_ref: {
                slot: dict(span)
                for slot, span in spans.items()
                if isinstance(span, Mapping)
            }
            for premise_ref, spans in canonical_plan_projection.audit_slot_evidence.items()
        }
    frozen = constraint.get("audit_slot_evidence")
    if isinstance(frozen, Mapping):
        return {
            str(premise_ref): {
                str(slot): dict(span)
                for slot, span in spans.items()
                if isinstance(span, Mapping)
            }
            for premise_ref, spans in frozen.items()
            if isinstance(spans, Mapping)
        }
    output: dict[str, dict[str, dict[str, Any]]] = {}
    for index, analysis in enumerate(constraint.get("premise_analyses") or [], start=1):
        if not isinstance(analysis, Mapping):
            continue
        output[f"P{index}"] = {
            str(slot): {
                **dict(span),
                "evidence_ref": f"P{index}:{slot}",
            }
            for slot, span in dict(analysis.get("slot_evidence") or {}).items()
            if isinstance(span, Mapping)
        }
    return output


def _polarity_valid(
    relation: str,
    expected_verdict: str | None,
    supplied: str,
) -> bool:
    return bool(
        relation
        and expected_verdict is not None
        and supplied in {relation, expected_verdict}
    )


def _frozen_premise_analysis(
    projection: Any,
    premise: Mapping[str, Any],
) -> dict[str, Any]:
    relation = str(getattr(projection, "polarity_relation", "") or "")
    selector = str(premise.get("span_selector") or "")
    slot_evidence = {
        slot: dict(span)
        for slot, span in projection.slot_evidence.get(selector, {}).items()
    }
    local_relation_state = str(premise.get("local_relation_state") or "")
    analysis = {
        "contract_id": LOCAL_SEMANTIC_RELATION_CONSTRAINT,
        "status": local_relation_state,
        "evidence_relation": relation,
        "independent_from_models": True,
        "method": "frozen_canonical_proposition_plan_projection",
        "quote_digest": _digest(str(premise.get("quote") or "")),
        "declared_proposition_slots": list(
            premise.get("binds_proposition_slots") or []
        ),
        "joint_relation_clause_bound": bool(
            premise.get("relation_bearing") is True
            and premise.get("candidate_relation_role") == "polarity_evidence"
            and dict(premise.get("semantic_alignment") or {}).get("status")
            == "verified"
        ),
        "selected_clause_ref": str(
            next(iter(slot_evidence.values()), {}).get("clause_ref") or "C1"
        ),
        "slot_evidence": slot_evidence,
        "required_object_tokens": list(projection.required_object_tokens),
        "covered_object_tokens": list(
            projection.covered_tokens_by_ref.get(selector, ())
        ),
        "target_relation_present": premise.get("target_relation_present") is True,
        "relation_bearing": premise.get("relation_bearing") is True,
        "meta_scope": premise.get("meta_scope") is True,
        "direct_relation_negated": premise.get("direct_relation_negated"),
        "clauses": [],
    }
    analysis["analysis_digest"] = _digest(analysis)
    return analysis


def _frozen_constraint_payload(
    projection: Any,
    supplied: str,
    *,
    polarity_valid: bool,
    analyses: list[dict[str, Any]],
    auditor_relationship: str,
) -> dict[str, Any]:
    relation = str(getattr(projection, "polarity_relation", "") or "")
    payload = {
        "contract_id": LOCAL_SEMANTIC_RELATION_CONSTRAINT,
        "status": "passed" if polarity_valid else "rejected",
        "reason": "" if polarity_valid else "local_semantic_relation_polarity_mismatch",
        "verdict": supplied,
        "expected_evidence_relation": relation,
        "auditor_relationship": str(auditor_relationship or ""),
        "independent_from_models": True,
        "correlated_model_guard_applied": auditor_relationship
        in {"same_instance", "distinct_instance_same_model"},
        "model_call_count": 0,
        "method": "frozen_canonical_proposition_plan_projection",
        "required_proposition_slots": list(projection.required_slots),
        "bound_proposition_slots": list(projection.required_slots),
        "required_object_tokens": list(projection.required_object_tokens),
        "covered_object_tokens": list(projection.covered_object_tokens),
        "uncovered_object_tokens": [],
        "local_relation_states": [
            str(analysis.get("status") or "unbound") for analysis in analyses
        ],
        "premise_analyses": analyses,
        "qasper_no_evidence_semantics": {
            "contract_id": "frozen_canonical_proposition_plan_projection.v1",
            "status": "not_applicable",
        },
        "support_evidence_binding_complete": True,
        "canonical_evidence_plan_id": projection.plan_id,
        "canonical_plan_digest": projection.plan_digest,
        "canonical_projection_digest": _digest(projection.as_dict()),
        "audit_slot_evidence": projection.audit_slot_evidence,
    }
    payload["constraint_digest"] = _digest(payload)
    return payload


def _digest(value: Any) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
