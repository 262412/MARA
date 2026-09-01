from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from jsonschema import ValidationError, validate
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_qasper_semantic_pack import (
    qasper_canonical_evidence_plans,
    qasper_canonical_selector_bindings,
)
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)

_BOUND_STATES = frozenset({"relation_bound_support", "relation_bound_contradiction"})


def schema_parser_probe(
    bundle: EvidenceBundle,
    *,
    question: str,
    binding: dict[str, Any],
    records: list[dict[str, Any]],
    slots: list[dict[str, Any]],
) -> dict[str, Any]:
    allowed_bindings = qasper_canonical_selector_bindings(records)
    allowed_plans = qasper_canonical_evidence_plans(bundle)
    applicable_slots = tuple(
        str(slot) for slot in binding.get("applicable_slots") or []
    )
    payload, expected_plan_id = _schema_payload(binding)
    response_format = semantic_proposition_response_format(
        list(allowed_bindings),
        [str(slot.get("slot_id") or "") for slot in slots],
        candidate="yes",
        applicable_proposition_slots=applicable_slots,
        allowed_proposition_slot_bindings=allowed_bindings,
        allowed_proposition_evidence_plans=allowed_plans,
    )
    schema_accepted = True
    schema_reason = ""
    try:
        validate(instance=payload, schema=response_format["json_schema"]["schema"])
    except ValidationError as exc:
        schema_accepted = False
        schema_reason = str(exc.message)
    parsed = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=records,
        slot_ids={str(slot.get("slot_id") or "") for slot in slots},
        model="natural-semantic-pack-probe",
        seed=0,
        candidate="yes",
        applicable_proposition_slots=applicable_slots,
        allowed_proposition_slot_bindings=allowed_bindings,
        slot_evidence_refs={
            str(slot.get("slot_id") or ""): tuple(
                str(ref) for ref in slot.get("evidence_refs") or ()
            )
            for slot in slots
            if str(slot.get("slot_id") or "")
        },
        allowed_proposition_evidence_plans=allowed_plans,
    )
    downstream_status = "not_applicable"
    downstream_reason = ""
    if parsed.value is not None and binding.get("binding_state") in _BOUND_STATES:
        constraint = semantic_relation_evidence_set_constraint(
            parsed.value["premises"],
            build_question_proposition(question),
            str(parsed.value["verdict"]),
            auditor_relationship="distinct_model",
        )
        downstream_status = str(constraint.get("status") or "")
        downstream_reason = str(constraint.get("reason") or "")
    return {
        "schema_accepted": schema_accepted,
        "schema_reason": schema_reason,
        "parser_accepted": parsed.value is not None,
        "parser_reason": parsed.failure_reason,
        "expected_plan_id": expected_plan_id,
        "canonical_plan_count": len(allowed_plans or {}),
        "parsed_plan_id": (
            str(parsed.value.get("canonical_evidence_plan_id") or "")
            if parsed.value is not None
            else ""
        ),
        "downstream_status": downstream_status,
        "downstream_reason": downstream_reason,
    }


def _schema_payload(binding: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
    state = str(binding.get("binding_state") or "")
    if state not in _BOUND_STATES:
        return {"candidate_judgment": "unknown", "canonical_evidence_plan_id": ""}, ""
    plan_key = (
        "support_plan" if state == "relation_bound_support" else "contradiction_plan"
    )
    plan = _mapping(_mapping(binding.get("canonical_evidence_plan")).get(plan_key))
    plan_id = str(plan.get("plan_id") or "")
    return {
        "candidate_judgment": (
            "supported" if state == "relation_bound_support" else "contradicted"
        ),
        "canonical_evidence_plan_id": plan_id,
    }, plan_id


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
