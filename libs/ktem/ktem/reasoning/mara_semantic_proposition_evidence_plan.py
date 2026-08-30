from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def normalized_proposition_evidence_plans(
    value: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, dict[str, Any]] | None:
    if value is None:
        return None
    normalized: dict[str, dict[str, Any]] = {}
    for raw_plan_id, raw_plan in value.items():
        if not isinstance(raw_plan, Mapping):
            continue
        mapping_plan_id = str(raw_plan_id or "").strip()
        embedded_plan_id = str(raw_plan.get("plan_id") or "").strip()
        if mapping_plan_id and embedded_plan_id not in {"", mapping_plan_id}:
            continue
        plan_id = mapping_plan_id or embedded_plan_id
        relation = str(raw_plan.get("polarity_relation") or "")
        refs = tuple(
            dict.fromkeys(
                str(ref).strip() for ref in raw_plan.get("span_refs") or () if ref
            )
        )
        if (
            plan_id
            and refs
            and len(refs) <= 4
            and relation in {"proposition_support", "explicit_contradiction"}
        ):
            normalized[plan_id] = {
                **dict(raw_plan),
                "plan_id": plan_id,
                "polarity_relation": relation,
                "span_refs": refs,
            }
    return normalized


def selected_evidence_plan_id(
    premises: list[dict[str, Any]],
    *,
    evidence_relation: str,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[str, str]:
    plans = normalized_proposition_evidence_plans(allowed_proposition_evidence_plans)
    if plans is None or evidence_relation == "undetermined":
        return "", ""
    selected_refs = {str(premise.get("span_selector") or "") for premise in premises}
    matches = [
        plan_id
        for plan_id, plan in plans.items()
        if plan["polarity_relation"] == evidence_relation
        and set(plan["span_refs"]) == selected_refs
        and len(plan["span_refs"]) == len(premises)
    ]
    if len(matches) != 1:
        return "", "premise_evidence_plan_not_allowed"
    return matches[0], ""


def premise_bound_slots(premises: list[dict[str, Any]]) -> set[str]:
    return {
        slot
        for premise in premises
        for slot in premise.get("binds_proposition_slots", [])
    }


def candidate_projection(candidate: str, judgment: str) -> tuple[str, str]:
    if judgment == "unknown":
        return "undetermined", "insufficient_evidence"
    relation = (
        {
            "yes": {
                "supported": "proposition_support",
                "contradicted": "explicit_contradiction",
            },
            "no": {
                "supported": "explicit_contradiction",
                "contradicted": "proposition_support",
            },
        }
        .get(candidate, {})
        .get(judgment)
    )
    if relation is None:
        return "undetermined", "insufficient_evidence"
    return relation, verdict_for_evidence_relation(relation)


def verdict_for_evidence_relation(relation: str) -> str:
    return {
        "proposition_support": "yes",
        "explicit_contradiction": "no",
        "undetermined": "insufficient_evidence",
    }[relation]


def projected_evidence_relation(
    candidate: str,
    candidate_judgment: str,
    verdict: str,
) -> str:
    normalized_candidate = str(candidate or "").strip().casefold()
    if candidate_judgment == "unknown" or verdict == "insufficient_evidence":
        return "undetermined"
    if normalized_candidate == "unanswerable":
        return "proposition_support" if verdict == "yes" else "explicit_contradiction"
    if normalized_candidate in {"yes", "no"}:
        relation, _ = candidate_projection(normalized_candidate, candidate_judgment)
        return relation
    return "proposition_support" if verdict == "yes" else "explicit_contradiction"


def canonical_premise_metadata(selector: Mapping[str, Any]) -> dict[str, Any]:
    if not str(selector.get("event_id") or ""):
        return {}
    return {
        "event_id": str(selector.get("event_id") or ""),
        "object_tokens": list(selector.get("object_tokens") or []),
        "event_core_tokens": list(selector.get("event_core_tokens") or []),
        "predicate_match_kind": str(selector.get("predicate_match_kind") or ""),
        "local_relation_state": str(selector.get("local_relation_state") or ""),
        "proposition_slot_spans": dict(selector.get("proposition_slot_spans") or {}),
    }
