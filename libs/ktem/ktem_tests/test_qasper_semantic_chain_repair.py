from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.question_proposition import build_question_proposition
from ktem.reasoning.mara_candidate_unknown_audit import (
    UNKNOWN_AUDIT_MAX_PROMPT_CHARS,
    candidate_unknown_audit_attestation,
    candidate_unknown_audit_prompt,
    candidate_unknown_audit_response_format,
    parse_candidate_unknown_audit,
)
from ktem.reasoning.mara_qasper_candidate import (
    _bound_candidate_slots,
    _candidate_prompt,
    _candidate_selector_options,
)
from ktem.reasoning.mara_semantic_candidate_policy import candidate_bound_response
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)


def _packed_complete_span() -> list[dict[str, object]]:
    quote = "The authors compared the two systems."
    return [
        {
            "evidence_id": "e1",
            "selectors": [
                {
                    "selector_id": "E1:S3",
                    "text": quote,
                    "span_start": 10,
                    "span_end": 10 + len(quote),
                }
            ],
        }
    ]


def _direct_verifier_payload(
    judgment: str,
    relation: str,
) -> dict[str, object]:
    quote = "The authors compared the two systems."
    return {
        "candidate_judgment": judgment,
        "evidence_relation": relation,
        "support_mode": "evidence_set",
        "proof_mode": "atomic_semantic",
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": [
            {
                "span_selector": "E1:S3",
                "proposition_fragment": quote,
                "supports_slot_ids": ["support:proposition"],
                "binds_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                    "quantifier",
                ],
            }
        ],
    }


def test_record_ids_and_first_selector_do_not_bind_a_candidate_slot() -> None:
    records = [
        {
            "evidence_id": "e1",
            "required_slot_ids": ["support:proposition"],
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": "first",
                    "span_start": 0,
                    "span_end": 5,
                },
                {
                    "selector_id": "E1:S3",
                    "text": "exact",
                    "span_start": 6,
                    "span_end": 11,
                },
            ],
        }
    ]

    observed = _bound_candidate_slots(
        [
            {
                "slot_id": "support:proposition",
                "evidence_ids": ["e1"],
                "evidence_refs": ["E1:S1"],
            }
        ],
        records,
    )[0]

    assert observed["binding_status"] == "missing"
    assert observed["binding_reason"] == "record_identity_only"
    assert observed["evidence_ids"] == []
    assert observed["evidence_refs"] == []
    assert observed["retrieved_evidence_refs"] == ["E1:S1", "E1:S3"]


def test_explicit_all_four_slot_span_set_is_the_only_candidate_binding() -> None:
    records = [
        {
            "evidence_id": "e1",
            "required_slot_ids": ["support:proposition"],
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": "first",
                    "span_start": 0,
                    "span_end": 5,
                },
                {
                    "selector_id": "E1:S3",
                    "text": "exact",
                    "span_start": 6,
                    "span_end": 11,
                },
            ],
        }
    ]
    slot = {
        "slot_id": "support:proposition",
        "evidence_ids": ["e1"],
        "evidence_refs": ["E1:S3"],
        "proposition_slot_bindings": {
            "actor": "the authors",
            "predicate": "compare",
            "object": "the two systems",
            "quantifier": "two",
        },
        "proposition_slot_evidence_refs": {
            "actor": ["E1:S3"],
            "predicate": ["E1:S3"],
            "object": ["E1:S3"],
            "quantifier": ["E1:S3"],
        },
        "typed_proposition": {
            "actor": "the authors",
            "predicate": "compare",
            "object_surface": "the two systems",
            "quantifier": "two",
        },
        "binding_status": "verified",
        "evidence_relation": "proposition_support",
    }

    observed = _bound_candidate_slots([slot], records)[0]

    assert observed["binding_status"] == "bound"
    assert observed["binding_reason"] == "exact_span_set"
    assert observed["evidence_ids"] == ["e1"]
    assert observed["evidence_refs"] == ["E1:S3"]


def test_malformed_selector_offsets_cannot_become_candidate_binding() -> None:
    records = [
        {
            "evidence_id": "e1",
            "required_slot_ids": ["support:proposition"],
            "selectors": [
                {
                    "selector_id": "E1:S3",
                    "text": "exact",
                    "span_start": 6,
                    "span_end": 99,
                }
            ],
        }
    ]
    slot = {
        "slot_id": "support:proposition",
        "evidence_refs": ["E1:S3"],
        "proposition_slot_bindings": {
            "actor": "the authors",
            "predicate": "compare",
            "object": "the two systems",
            "quantifier": "two",
        },
        "proposition_slot_evidence_refs": {
            name: ["E1:S3"] for name in ("actor", "predicate", "object", "quantifier")
        },
        "typed_proposition": {
            "actor": "the authors",
            "predicate": "compare",
            "object_surface": "the two systems",
            "quantifier": "two",
        },
        "binding_status": "verified",
        "evidence_relation": "proposition_support",
    }

    observed = _bound_candidate_slots([slot], records)[0]

    assert observed["binding_status"] == "missing"
    assert observed["evidence_refs"] == []


def test_candidate_prompt_exposes_all_selector_polarities_without_authority() -> None:
    question = "Did the authors collect the two datasets?"
    record = {
        "label": "E1",
        "evidence_id": "e1",
        "selectors": [
            {
                "selector_id": "E1:S1",
                "text": "The authors did not collect the two datasets.",
                "span_start": 0,
                "span_end": 45,
            },
            {
                "selector_id": "E1:S3",
                "text": "The authors collected the two datasets.",
                "span_start": 46,
                "span_end": 85,
            },
        ],
    }
    prompt = _candidate_prompt(
        question,
        [record],
        required_slots=[
            {
                "slot_id": "support:proposition",
                "binding_status": "missing",
                "retrieved_evidence_ids": ["e1"],
                "retrieved_evidence_refs": ["E1:S1", "E1:S3"],
            }
        ],
    )

    assert '"evidence_ref":"E1:S3"' in prompt
    assert '"polarity_signal":"explicit_contradiction"' in prompt
    assert '"polarity_signal":"support"' in prompt
    assert "first selector is not a proposition binding" in prompt
    options = _candidate_selector_options(record, question=question)
    assert options[0]["polarity_signal"] == "explicit_contradiction"
    assert options[1]["polarity_signal"] == "support"


def test_direct_candidate_judgment_derives_legacy_polarity_deterministically() -> None:
    properties = semantic_proposition_response_format([], ["support:proposition"])[
        "json_schema"
    ]["schema"]["properties"]
    assert "candidate_judgment" in properties
    assert "verdict" not in properties

    cases = (
        ("yes", "supported", "proposition_support", "yes"),
        ("yes", "contradicted", "explicit_contradiction", "no"),
        ("yes", "unknown", "undetermined", "insufficient_evidence"),
        ("no", "supported", "explicit_contradiction", "no"),
        ("no", "contradicted", "proposition_support", "yes"),
        ("unanswerable", "supported", "undetermined", "insufficient_evidence"),
        ("unanswerable", "unknown", "undetermined", "insufficient_evidence"),
        ("unanswerable", "contradicted", "proposition_support", "yes"),
    )
    for candidate, judgment, relation, verdict in cases:
        payload = _direct_verifier_payload(judgment, relation)
        if verdict == "insufficient_evidence":
            payload.update(
                {
                    "proof_mode": "none",
                    "jointly_complete": False,
                    "each_premise_required": False,
                    "premises": [],
                    "unknown_assessment": {
                        "reviewed_span_selectors": ["E1:S3"],
                        "unresolved_proposition_slots": [
                            "actor",
                            "predicate",
                            "object",
                            "quantifier",
                        ],
                        "support_gap": "The reviewed span does not establish support.",
                        "contradiction_gap": "The reviewed span does not contradict it.",
                    },
                }
            )
        parsed = parse_semantic_proposition_response(
            json.dumps(payload),
            packed=_packed_complete_span(),
            slot_ids={"support:proposition"},
            model="semantic-test-model",
            seed=17,
            candidate=candidate,
        )
        assert parsed.failure_reason == ""
        assert parsed.value is not None
        assert parsed.value["candidate_judgment"] == judgment
        assert parsed.value["verdict"] == verdict

    mixed = _direct_verifier_payload("supported", "proposition_support")
    mixed["verdict"] = "yes"
    parsed = parse_semantic_proposition_response(
        json.dumps(mixed),
        packed=_packed_complete_span(),
        slot_ids={"support:proposition"},
        model="semantic-test-model",
        seed=17,
        candidate="yes",
    )
    assert parsed.value is None
    assert parsed.failure_reason == "candidate_judgment_verdict_mixed"


def test_unanswerable_candidate_can_retain_verifier_unknown_judgment() -> None:
    response = candidate_bound_response(
        {
            "candidate_judgment": "unknown",
            "verdict": "insufficient_evidence",
            "unknown_assessment": {"reviewed_evidence": [{"evidence_id": "e1"}]},
        },
        "unanswerable",
    )

    assert response["candidate_verification_status"] == "unknown"
    assert response["candidate_judgment"] == "unknown"
    assert response["unknown"] is True


def test_unknown_auditor_binds_explicit_unanswerable_unknown_judgment() -> None:
    proposition = build_question_proposition("Did the authors compare the systems?")
    quote = "The paper discusses the systems."
    assessment = {
        "reviewed_evidence": [
            {
                "span_selector": "E1:S1",
                "evidence_id": "evidence-1",
                "quote": quote,
                "span_start": 0,
                "span_end": len(quote),
            }
        ],
        "unresolved_proposition_slots": ["predicate"],
        "support_gap": "The action is not established.",
        "contradiction_gap": "No explicit contradiction is present.",
    }
    prompt, _conclusion = candidate_unknown_audit_prompt(
        proposition,
        "unanswerable",
        assessment,
        verifier_judgment="unknown",
    )
    schema = candidate_unknown_audit_response_format(
        "unanswerable",
        verifier_judgment="unknown",
    )
    payload = {
        "audit_scope": "original_candidate_and_verifier_unknown_only",
        "audited_candidate": "unanswerable",
        "audited_verdict": "insufficient_evidence",
        "audited_judgment": "unknown",
        "typed_conclusion_present": True,
        "reviewed_evidence_present": True,
        "support_gap_valid": True,
        "contradiction_gap_valid": True,
        "relationship_consistent": True,
        "replacement_candidate_allowed": False,
        "replacement_candidate": "",
    }
    parsed = parse_candidate_unknown_audit(
        json.dumps(payload),
        candidate="unanswerable",
        verifier_judgment="unknown",
    )

    assert '"verifier_judgment":"unknown"' in prompt
    assert schema["json_schema"]["schema"]["properties"]["audited_judgment"][
        "enum"
    ] == ["unknown"]
    assert parsed.value == payload


def test_unknown_audit_keeps_twelve_exact_premises_under_bound() -> None:
    proposition = build_question_proposition(
        "Did the authors compare cross-lingual and single-language evaluation?"
    )
    reviewed = [
        {
            "span_selector": f"E{index}:S3",
            "evidence_id": f"evidence-{index}",
            "quote": f"Evidence {index}: " + ("x" * 180),
            "span_start": 100,
            "span_end": 100 + len(f"Evidence {index}: " + ("x" * 180)),
        }
        for index in range(1, 13)
    ]
    assessment = {
        "reviewed_evidence": reviewed,
        "unresolved_proposition_slots": ["actor", "predicate", "object", "quantifier"],
        "support_gap": "The reviewed spans do not establish all proposition slots.",
        "contradiction_gap": "No reviewed span explicitly contradicts the proposition.",
    }

    prompt, conclusion = candidate_unknown_audit_prompt(
        proposition,
        "yes",
        assessment,
    )

    assert conclusion
    assert len(prompt) <= UNKNOWN_AUDIT_MAX_PROMPT_CHARS
    assert "evidence-1" in prompt and "evidence-12" in prompt
    assert "Evidence 1:" in prompt and "Evidence 12:" in prompt
    assert '"reviewed_evidence"' not in prompt


def test_unknown_audit_does_not_relax_the_prompt_bound() -> None:
    proposition = build_question_proposition("Did the authors compare the systems?")
    quote = "x" * UNKNOWN_AUDIT_MAX_PROMPT_CHARS
    assessment = {
        "reviewed_evidence": [
            {
                "span_selector": "E1:S1",
                "evidence_id": "evidence-1",
                "quote": quote,
                "span_start": 0,
                "span_end": len(quote),
            }
        ],
        "unresolved_proposition_slots": [
            "actor",
            "predicate",
            "object",
            "quantifier",
        ],
        "support_gap": "The reviewed span does not establish support.",
        "contradiction_gap": "The reviewed span does not contradict it.",
    }

    with pytest.raises(
        ValueError,
        match="candidate_unknown_audit_prompt_bound_exceeded",
    ):
        candidate_unknown_audit_prompt(proposition, "yes", assessment)


def test_unknown_audit_rejects_empty_conclusion_or_evidence() -> None:
    proposition = build_question_proposition("Did the authors compare the systems?")
    with pytest.raises(ValueError):
        candidate_unknown_audit_prompt(proposition, "yes", {})
    with pytest.raises(ValueError):
        candidate_unknown_audit_attestation(
            {},
            typed_conclusion_value={},
            unknown_assessment={},
        )


def test_packing_prioritizes_explicit_negative_evidence() -> None:
    question = "Did the authors collect the two datasets?"
    request = SimpleNamespace(
        query_plan=build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="qasper",
        )
    )
    items = [
        {
            "evidence_id": f"unknown-{index}",
            "source_id": "paper",
            "text": f"The paper discusses topic {index}.",
        }
        for index in range(12)
    ]
    items.append(
        {
            "evidence_id": "explicit-negative",
            "source_id": "paper",
            "text": "The authors did not collect the two datasets.",
        }
    )
    packing = pack_semantic_proposition_evidence(
        request,
        question,
        required_semantic_proposition_slots(request),
        EvidenceBundle(route="text_rag", items=items),
    )

    assert any(
        "did not collect the two datasets" in record["text"]
        for record in packing.records
    )


def test_selector_polarity_signal_is_explicitly_unknown_for_missing_polarity() -> None:
    options = _candidate_selector_options(
        {
            "selectors": [
                {
                    "selector_id": "E1:S3",
                    "text": "The paper discusses datasets.",
                    "span_start": 0,
                    "span_end": 29,
                }
            ]
        },
        question="Did the authors collect the two datasets?",
    )

    assert options[0]["polarity_signal"] == "undetermined"


def test_selector_polarity_does_not_promote_predicate_only_negative_match() -> None:
    options = _candidate_selector_options(
        {
            "selectors": [
                {
                    "selector_id": "E1:S3",
                    "text": "The administrators did not compare the two invoices.",
                    "span_start": 0,
                    "span_end": 52,
                }
            ]
        },
        question="Did the authors compare the two systems?",
    )

    assert options[0]["polarity_signal"] == "undetermined"
    assert options[0]["joint_slot_hint"] is False
    assert set(options[0]["slot_hints"]) != {
        "actor",
        "predicate",
        "object",
        "quantifier",
    }
