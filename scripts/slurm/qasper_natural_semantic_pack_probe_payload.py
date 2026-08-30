from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any


def build_probe_result(
    *,
    contract_id: str,
    code_sha: str,
    example_id: str,
    route: str,
    question: str,
    items: list[Any],
    context: Any,
    canonical_plan_count: int,
    ambiguity: dict[str, Any],
    schema_parser: dict[str, Any],
    causal_transaction_replay: dict[str, Any],
    no_policy_cohorts: list[str],
    checks: dict[str, bool],
) -> dict[str, Any]:
    binding = context.binding
    stored_pack = _mapping(
        context.bundle.metadata.get("qasper_canonical_semantic_pack")
    )
    return {
        "contract_id": contract_id,
        "code_sha": code_sha,
        "example_id": example_id,
        "route": route,
        "question": question,
        "question_digest": _canonical_digest(question),
        "retrieval_evidence_digest": _canonical_digest(items),
        "retrieval_record_count": len(items),
        "canonical_record_count": len(context.frozen.records),
        "packing_observation": deepcopy(
            _mapping(stored_pack.get("source_packing_observation"))
        ),
        "candidate_path_replay": deepcopy(context.candidate_path_replay),
        "candidate_prompt_projection_trace": deepcopy(
            context.candidate_prompt_projection
        ),
        "candidate_generation_replay": deepcopy(context.candidate_generation),
        "canonical_selector_projection_trace": deepcopy(
            context.canonical_selector_projection
        ),
        "candidate_transaction_id": context.transaction_id,
        "binding_state": str(binding.get("binding_state") or ""),
        "binding_status": str(binding.get("binding_status") or ""),
        "canonical_plan_count": canonical_plan_count,
        "ambiguity": ambiguity,
        "plan_construction_trace": deepcopy(
            binding.get("plan_construction_trace") or {}
        ),
        "canonical_evidence_plan": deepcopy(
            binding.get("canonical_evidence_plan") or {}
        ),
        "canonical_selectors": canonical_selector_observations(context.frozen.records),
        "binding_observation": {
            key: deepcopy(binding.get(key))
            for key in (
                "applicable_slots",
                "covered_slots",
                "evidence_refs",
                "support_evidence_refs",
                "explicit_contradiction_evidence_refs",
                "no_evidence_semantics",
                "binding_reason",
            )
        },
        "semantic_pack_digest": context.frozen.semantic_pack_digest,
        "span_universe_digest": str(stored_pack.get("span_universe_digest") or ""),
        "schema_parser": schema_parser,
        "causal_transaction_replay": deepcopy(causal_transaction_replay),
        "no_policy_cohorts": no_policy_cohorts,
        "checks": checks,
        "status": "passed" if all(checks.values()) else "failed",
    }


def canonical_selector_observations(
    records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": str(record.get("evidence_id") or ""),
            "selector_id": str(selector.get("selector_id") or ""),
            "text": str(selector.get("text") or ""),
            "span_start": selector.get("span_start"),
            "span_end": selector.get("span_end"),
            "allowed_proposition_slots": list(
                selector.get("allowed_proposition_slots") or []
            ),
            "event_id": str(selector.get("event_id") or ""),
            "object_tokens": list(selector.get("object_tokens") or []),
            "predicate_match_kind": str(selector.get("predicate_match_kind") or ""),
            "local_relation_state": str(selector.get("local_relation_state") or ""),
            "semantic_alignment": deepcopy(
                dict(selector.get("semantic_alignment") or {})
            ),
        }
        for record in records
        for selector in record.get("selectors") or []
    ]


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
