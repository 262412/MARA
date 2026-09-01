from __future__ import annotations

import hashlib
from typing import Any

from ktem.docqa.qasper_semantic_pack_contract import (
    canonical_payload_digest,
    qasper_canonical_span_universe_digest,
)
from ktem.docqa.question_proposition import build_question_proposition
from ktem.reasoning.mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding,
    candidate_required_slots_from_binding,
)
from ktem.reasoning.mara_qasper_selector_lineage import qasper_selector_crosswalk
from ktem.reasoning.mara_qasper_semantic_pack import prepare_qasper_canonical_records
from ktem.reasoning.mara_semantic_proposition_packing import (
    semantic_proposition_pack_digest,
)

from benchmark.tests.contract_smoke_fixtures import _fixture_digest

DEBUG_PACK_QUESTION = "Does the paper use the method?"


def _debug_semantic_pack(
    candidate_transaction_id: str,
    *,
    route: str = "fixture",
) -> dict[str, Any]:
    text = "The paper uses the method."
    records = prepare_qasper_canonical_records(
        DEBUG_PACK_QUESTION,
        [
            {
                "label": "E1",
                "evidence_id": "span:paper:s1",
                "semantic_identity": "fixture-semantic-identity",
                "source_id": "paper",
                "text": text,
                "text_start": 0,
                "selectors": [
                    {
                        "selector_id": "E1:S1",
                        "text": text,
                        "span_start": 0,
                        "span_end": len(text),
                        "canonical_start": 0,
                        "canonical_end": len(text),
                    }
                ],
            }
        ],
    )
    base_slots = [
        {
            "slot_id": "support:boolean_proposition",
            "description": "Evidence for or against the boolean proposition.",
        }
    ]
    proposition_binding = candidate_evidence_set_binding(
        records,
        DEBUG_PACK_QUESTION,
        candidate_transaction_id=candidate_transaction_id,
    )
    slots = candidate_required_slots_from_binding(base_slots, proposition_binding)
    proposition = build_question_proposition(DEBUG_PACK_QUESTION)
    semantic_pack_digest = semantic_proposition_pack_digest(
        proposition,
        slots,
        records,
        item_char_limit=1200,
    )
    payload = {
        "contract_id": "qasper_canonical_semantic_pack.v1",
        "candidate_transaction_id": candidate_transaction_id,
        "question_digest": _fixture_digest(DEBUG_PACK_QUESTION),
        "semantic_pack_digest": semantic_pack_digest,
        "span_universe_digest": qasper_canonical_span_universe_digest(records),
        "records": records,
        "slots": slots,
        "proposition_binding": proposition_binding,
        "proposition_binding_digest": proposition_binding["binding_digest"],
        "item_char_limit": 1200,
        "input_token_budget": 4096,
        "estimated_input_tokens": 128,
        "dropped_count": 0,
        "truncated_count": 0,
        "question_proposition": proposition.as_dict(),
        "question_proposition_resolution": {"status": "complete"},
        "immutable_after_candidate_generation": True,
        "source_packing_observation": _debug_source_packing_observation(
            text,
            semantic_pack_digest,
            records,
            route=route,
        ),
    }
    payload["pack_identity_digest"] = _fixture_digest(payload)
    return payload


def _debug_source_packing_observation(
    text: str,
    semantic_pack_digest: str,
    canonical_records: list[dict[str, Any]],
    *,
    route: str,
) -> dict[str, Any]:
    record_summary = {
        "evidence_id": "span:paper:s1",
        "label": "E1",
        "text_start": 0,
        "text_digest": canonical_payload_digest(text),
        "selector_refs": ["E1:S1"],
    }
    return {
        "contract_id": "qasper_source_packing_observation.v1",
        "semantic_pack_digest": semantic_pack_digest,
        "source_semantic_pack_digest": semantic_pack_digest,
        "source_input_snapshot": _debug_source_input_snapshot(text, route=route),
        "record_count": 1,
        "selector_count": 1,
        "estimated_input_tokens": 128,
        "input_token_budget": 4096,
        "item_char_limit": 1200,
        "dropped_count": 0,
        "truncated_count": 0,
        "source_records": [
            {
                "evidence_id": "span:paper:s1",
                "semantic_identity": "fixture-semantic-identity",
                "source_id": "paper",
                "page_label": None,
                "section_id": "",
                "canonical_start": None,
                "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_chars": len(text),
                "semantic_rank": 1,
                "priority": [0, 1, 0, 0.0],
                "selected_for_windowing": True,
                "packed": True,
                "stop_stage": "packed",
            }
        ],
        "records": [{**record_summary, "window_index": None}],
        "canonical_records": [record_summary],
        "selector_crosswalk": qasper_selector_crosswalk(
            canonical_records,
            canonical_records,
        ),
    }


def _debug_source_input_snapshot(
    text: str,
    *,
    route: str,
) -> dict[str, Any]:
    text_digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    source_items = [
        {
            "source_item_index": 1,
            "evidence_id": "span:paper:s1",
            "text_digest": text_digest,
            "text_chars": len(text),
            "identity_decision": "packed",
            "identity_reason": "packed",
        }
    ]
    ranked_evidence = [{"ranked_position": 0, "canonical_id": "span:paper:s1"}]
    query_plan = {"plan_id": "debug-semantic-pack"}
    required_slots = [{"slot_id": "support:boolean_proposition"}]
    payload = {
        "contract_id": "semantic_source_input_snapshot.v1",
        "complete": True,
        "route": route,
        "candidate_priority": True,
        "question": DEBUG_PACK_QUESTION,
        "question_digest": _fixture_digest(DEBUG_PACK_QUESTION),
        "query_plan": query_plan,
        "query_plan_digest": _fixture_digest(query_plan),
        "required_slots": required_slots,
        "required_slots_digest": _fixture_digest(required_slots),
        "max_context_length": None,
        "item_char_limit": 1200,
        "source_item_count": len(source_items),
        "source_items_digest": _fixture_digest(source_items),
        "source_items": source_items,
        "ranked_evidence_present": True,
        "ranked_evidence_count": len(ranked_evidence),
        "ranked_evidence_digest": _fixture_digest(ranked_evidence),
        "ranked_evidence": ranked_evidence,
    }
    payload["snapshot_digest"] = _fixture_digest(payload)
    return payload


def _debug_semantic_pack_identity(pack: dict[str, Any]) -> dict[str, str]:
    return {
        "semantic_pack_digest": str(pack["semantic_pack_digest"]),
        "span_universe_digest": str(pack["span_universe_digest"]),
        "candidate_transaction_id": str(pack["candidate_transaction_id"]),
    }


def _debug_audited_premises() -> list[dict[str, Any]]:
    text = "The paper uses the method."
    return [
        {
            "span_selector": "E1:S1",
            "evidence_id": "span:paper:s1",
            "quote": text,
            "span_start": 0,
            "span_end": len(text),
        }
    ]


def _debug_semantic_authority(
    verdict: str,
    pack_identity: dict[str, str],
) -> dict[str, Any]:
    evidence_refs = ["span:paper:s1#quote:0:30"]
    evidence_relation = (
        "explicit_contradiction" if verdict == "no" else "proposition_support"
    )
    slot_spans = {
        "actor": (0, 9, "The paper"),
        "predicate": (9, 13, "uses"),
        "object": (13, 23, "the method"),
    }
    slot_evidence_refs = {
        slot: [f"{evidence_refs[0]}#slot:{slot}:{start}:{end}"]
        for slot, (start, end, _text) in slot_spans.items()
    }
    slot_evidence = {
        evidence_refs[0]: {
            slot: {
                "evidence_ref": refs[0],
                "text": text,
                "span_start": start,
                "span_end": end,
                "clause_ref": "C1",
                "clause_start": 0,
                "clause_end": 30,
            }
            for slot, refs in slot_evidence_refs.items()
            for start, end, text in (slot_spans[slot],)
        }
    }
    payload = {
        "evidence_relation": evidence_relation,
        "proposition_slot_bindings": {
            "actor": "current_paper",
            "predicate": "use",
            "object": "the method",
        },
        "proposition_slot_evidence_refs": slot_evidence_refs,
        "proposition_binding_evidence_set_refs": evidence_refs,
        "not_applicable_proposition_slots": ["quantifier"],
    }
    return {
        "contract_id": "semantic_proposition_verdict.v4",
        "status": "verified",
        "reason": "semantic_evidence_set_bound",
        "required_slot_ids": ["support:boolean_proposition"],
        "verified_support_slot_ids": ["support:boolean_proposition"],
        "required_proposition_slots": ["actor", "predicate", "object"],
        "proposition_slot_evidence": slot_evidence,
        "semantic_pack_digest": pack_identity["semantic_pack_digest"],
        "canonical_span_universe_digest": pack_identity["span_universe_digest"],
        "candidate_transaction_id": pack_identity["candidate_transaction_id"],
        "canonical_pack_continuity_status": "preserved",
        "auditor_semantic_pack_identity": pack_identity,
        **payload,
        "proposition_evidence_set_digest": _fixture_digest(payload),
    }
