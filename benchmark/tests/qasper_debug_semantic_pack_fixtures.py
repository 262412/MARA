from __future__ import annotations

from typing import Any

from benchmark.tests.contract_smoke_fixtures import _fixture_digest


def _debug_semantic_pack(candidate_transaction_id: str) -> dict[str, Any]:
    text = "The paper uses the method."
    records = [
        {
            "evidence_id": "span:paper:s1",
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": text,
                    "span_start": 0,
                    "span_end": len(text),
                    "canonical_start": 0,
                    "canonical_end": len(text),
                    "allowed_proposition_slots": ["actor", "predicate", "object"],
                    "relation_bearing": True,
                    "candidate_relation_role": "polarity_evidence",
                    "local_relation_state": "affirmative_assertion",
                    "local_relation_analysis_digest": "fixture-local-analysis",
                }
            ],
        }
    ]
    span_universe = [
        {
            "evidence_id": "span:paper:s1",
            "selector_id": "E1:S1",
            "text": text,
            "span_start": 0,
            "span_end": len(text),
            "canonical_start": 0,
            "canonical_end": len(text),
            "allowed_proposition_slots": ["actor", "predicate", "object"],
            "relation_bearing": True,
            "candidate_relation_role": "polarity_evidence",
            "local_relation_state": "affirmative_assertion",
            "local_relation_analysis_digest": "fixture-local-analysis",
        }
    ]
    slots = [
        {
            "slot_id": "support:boolean_proposition",
            "description": "Evidence for or against the boolean proposition.",
        }
    ]
    payload = {
        "contract_id": "qasper_canonical_semantic_pack.v1",
        "candidate_transaction_id": candidate_transaction_id,
        "question_digest": _fixture_digest("Does the paper use the method?"),
        "semantic_pack_digest": _fixture_digest(
            {"records": records, "slots": slots, "item_char_limit": 1200}
        ),
        "span_universe_digest": _fixture_digest(span_universe),
        "records": records,
        "slots": slots,
        "item_char_limit": 1200,
        "input_token_budget": 4096,
        "estimated_input_tokens": 128,
        "dropped_count": 0,
        "truncated_count": 0,
        "question_proposition": {
            "actor": "current_paper",
            "predicate": "use",
            "object_surface": "the method",
            "quantifier": "none",
        },
        "question_proposition_resolution": {"status": "complete"},
        "immutable_after_candidate_generation": True,
    }
    payload["pack_identity_digest"] = _fixture_digest(payload)
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
