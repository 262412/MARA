from __future__ import annotations

from typing import Any


def _schema_body(schema: dict[str, object]) -> dict[str, Any]:
    body = schema.get("schema")
    if not isinstance(body, dict):
        raise RuntimeError("provider response schema body missing")
    return body


def _schema_properties(schema: dict[str, object]) -> dict[str, Any]:
    properties = _schema_body(schema).get("properties")
    if not isinstance(properties, dict):
        raise RuntimeError("provider response schema properties missing")
    return properties


def _schema_required(schema: dict[str, object]) -> set[str]:
    required = _schema_body(schema).get("required")
    return (
        {str(field) for field in required if isinstance(field, str)}
        if isinstance(required, list)
        else set()
    )


def _schema_enum(value: object) -> list[str]:
    if not isinstance(value, dict):
        return []
    enum = value.get("enum")
    return [str(item) for item in enum] if isinstance(enum, list) else []


def _schema_branch(schema: dict[str, object], judgment: str) -> dict[str, Any]:
    body = _schema_body(schema)
    branches = body.get("oneOf")
    if not isinstance(branches, list) or not branches:
        return body
    for branch in branches:
        if not isinstance(branch, dict):
            continue
        properties = branch.get("properties")
        if not isinstance(properties, dict):
            continue
        if judgment in _schema_enum(properties.get("candidate_judgment")):
            return branch
    raise RuntimeError("provider candidate judgment is outside response schema")


def _schema_shape(
    values: dict[str, object],
    properties: dict[str, Any],
    required: set[str],
    label: str,
) -> dict[str, object]:
    output = {key: value for key, value in values.items() if key in properties}
    missing = required - set(output)
    if missing:
        raise RuntimeError(f"provider {label} schema fields missing: {sorted(missing)}")
    return output


def _proposal_schema_context(
    schema: dict[str, object],
    proposal_judgment: str,
    source: dict[str, Any],
    *,
    selector: str,
) -> tuple[
    dict[str, Any],
    set[str],
    dict[str, Any],
    dict[str, Any],
    list[str],
    list[str],
    list[str],
    list[str],
]:
    branch = _schema_branch(schema, proposal_judgment)
    properties = branch.get("properties")
    if not isinstance(properties, dict):
        raise RuntimeError("provider proposal schema properties missing")
    required = branch.get("required")
    required_fields = (
        {str(field) for field in required if isinstance(field, str)}
        if isinstance(required, list)
        else set()
    )
    premise_properties, source_premise = _proposal_premise_context(
        properties,
        source,
        selector,
    )
    proposition_slots = _proposal_proposition_slots(
        premise_properties,
        source_premise,
    )
    support_slot_ids = _proposal_support_slot_ids(
        premise_properties,
        source_premise,
    )
    if proposal_judgment != "unknown" and not proposition_slots:
        raise RuntimeError("provider proposal proposition slots missing")
    applicable_slots, not_applicable_slots = _schema_proposition_scope(properties)
    return (
        properties,
        required_fields,
        premise_properties,
        source_premise,
        proposition_slots,
        support_slot_ids,
        applicable_slots,
        not_applicable_slots,
    )


def _proposal_premise_context(
    properties: dict[str, Any],
    source: dict[str, Any],
    selector: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    premise_schema = properties.get("premises")
    premise_item = _planned_premise_item(premise_schema, selector=selector)
    premise_properties = (
        premise_item.get("properties") if isinstance(premise_item, dict) else {}
    )
    if not isinstance(premise_properties, dict):
        premise_properties = {}
    source_premises = source.get("premises")
    source_premise = (
        source_premises[0]
        if isinstance(source_premises, list)
        and source_premises
        and isinstance(source_premises[0], dict)
        else {}
    )
    return premise_properties, source_premise


def _planned_premise_item(
    premise_schema: object,
    *,
    selector: str,
) -> dict[str, Any]:
    schema = premise_schema if isinstance(premise_schema, dict) else {}
    raw_plans = schema.get("oneOf")
    plans = raw_plans if isinstance(raw_plans, list) else [schema]
    for raw_plan in plans:
        plan = raw_plan if isinstance(raw_plan, dict) else {}
        item = plan.get("items")
        item = item if isinstance(item, dict) else {}
        branches = item.get("oneOf")
        candidates = branches if isinstance(branches, list) else [item]
        for raw_candidate in candidates:
            candidate = raw_candidate if isinstance(raw_candidate, dict) else {}
            properties = candidate.get("properties")
            properties = properties if isinstance(properties, dict) else {}
            allowed = _schema_enum(properties.get("span_selector"))
            if not allowed or selector in allowed:
                return candidate
    raise RuntimeError("provider proposal selector is outside response schema")


def _proposal_proposition_slots(
    premise_properties: dict[str, Any],
    source_premise: dict[str, Any],
) -> list[str]:
    slot_schema = premise_properties.get("binds_proposition_slots", {})
    slot_values = slot_schema.get("enum") if isinstance(slot_schema, dict) else None
    if (
        isinstance(slot_values, list)
        and len(slot_values) == 1
        and isinstance(slot_values[0], list)
    ):
        return [str(value) for value in slot_values[0]]
    return [
        str(value)
        for value in source_premise.get("binds_proposition_slots") or []
        if str(value)
    ]


def _proposal_support_slot_ids(
    premise_properties: dict[str, Any],
    source_premise: dict[str, Any],
) -> list[str]:
    support_schema = premise_properties.get("supports_slot_ids", {})
    support_items = support_schema.get("items")
    support_items = support_items if isinstance(support_items, dict) else {}
    schema_values = _schema_enum(support_items)
    if schema_values:
        return schema_values
    return [
        str(value)
        for value in source_premise.get("supports_slot_ids") or []
        if str(value)
    ]


def _selector_premise_branch(
    premise_item: object,
    *,
    selector: str,
) -> dict[str, Any]:
    item = premise_item if isinstance(premise_item, dict) else {}
    branches = item.get("oneOf")
    if not isinstance(branches, list):
        return item
    for raw_branch in branches:
        branch = raw_branch if isinstance(raw_branch, dict) else {}
        properties = branch.get("properties")
        properties = properties if isinstance(properties, dict) else {}
        if selector in _schema_enum(properties.get("span_selector")):
            return branch
    raise RuntimeError("provider proposal selector is outside response schema")


def _schema_proposition_scope(
    properties: dict[str, Any],
) -> tuple[list[str], list[str]]:
    all_slots = ("actor", "predicate", "object", "quantifier")
    schema = properties.get("not_applicable_proposition_slots")
    values = schema.get("enum") if isinstance(schema, dict) else None
    if (
        not isinstance(values, list)
        or len(values) != 1
        or not isinstance(values[0], list)
    ):
        raise RuntimeError("provider proposal proposition scope missing")
    not_applicable = [str(value) for value in values[0]]
    return (
        [slot for slot in all_slots if slot not in not_applicable],
        not_applicable,
    )
