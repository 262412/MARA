from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from typing import Any

from .mara_semantic_proposition_schema import semantic_proposition_response_format


def proposal_lineage_fields(
    *,
    context: Any,
    candidate: str,
    selectors: list[dict[str, Any]],
    stage_value: Mapping[str, Any],
    proposal_attempts: list[dict[str, Any]],
    applicable_proposition_slots: Collection[str] | None,
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    plan_mode = allowed_proposition_evidence_plans is not None
    response_format = semantic_proposition_response_format(
        [str(selector.get("selector_id") or "") for selector in selectors],
        [str(slot.get("slot_id") or "") for slot in context.slots],
        candidate=candidate,
        applicable_proposition_slots=applicable_proposition_slots,
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        allowed_proposition_evidence_plans=allowed_proposition_evidence_plans,
    )
    return {
        "identities": {
            "semantic_pack_digest": str(context.semantic_pack_digest or ""),
            "canonical_span_universe_digest": str(
                context.canonical_span_universe_digest or ""
            ),
            "candidate_transaction_id": str(context.candidate_transaction_id or ""),
        },
        "proposal_contract": {
            "mode": (
                "canonical_plan_selection" if plan_mode else "model_premise_generation"
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
        "proposal_attempts": proposal_attempts,
        "local_projection": {
            "status": (
                "passed"
                if plan_mode and stage_value
                else "not_run"
                if plan_mode
                else "not_applicable"
            ),
            "selected_plan_id": str(
                stage_value.get("canonical_evidence_plan_id") or ""
            ),
        },
        "candidate": str(candidate or ""),
    }


def _canonical_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
