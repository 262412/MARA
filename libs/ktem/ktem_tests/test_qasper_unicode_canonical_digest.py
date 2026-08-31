from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from types import SimpleNamespace

from benchmark.qasper_causal_transaction import (
    QASPER_CAUSAL_TRANSACTION_STAGES,
    _stage_record,
    qasper_causal_transaction_first_failure,
)
from benchmark.qasper_causal_transaction_plan_projection import (
    projected_plan_authority_stage_payload,
)
from ktem.docqa.canonical_serialization import (
    CANONICAL_SERIALIZER_IDENTITY,
    canonical_digest,
    canonical_digest_trace,
    canonical_projection_digest,
)
from ktem.docqa.frozen_semantic_relation_projection import (
    frozen_semantic_relation_evidence_set_constraint,
)
from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest
from scripts.slurm.qasper_causal_transaction_gate import _first_divergence


def test_frozen_relation_producer_and_validator_share_unicode_digest() -> None:
    quote = "The authors said “yes”."
    premise = {
        "span_selector": "E1:S1",
        "quote": quote,
        "local_relation_state": "affirmative_assertion",
        "binds_proposition_slots": [],
        "semantic_alignment": {},
        "relation_bearing": False,
        "candidate_relation_role": "",
    }
    canonical = {
        "polarity_relation": "proposition_support",
        "premises": [premise],
        "plan_id": "plan-1",
        "plan_digest": "plan-1",
    }
    premise["canonical_projection_digest"] = canonical_projection_digest(canonical)
    projection = SimpleNamespace(
        polarity_relation="proposition_support",
        premises=(premise,),
        slot_evidence={"E1:S1": {}},
        required_slots=(),
        required_object_tokens=(),
        covered_object_tokens=(),
        covered_tokens_by_ref={"E1:S1": ()},
        plan_id="plan-1",
        plan_digest="plan-1",
        audit_slot_evidence={},
        as_dict=lambda: canonical,
    )

    constraint = frozen_semantic_relation_evidence_set_constraint(
        projection,
        "yes",
        auditor_relationship="",
    )

    assert constraint["premise_analyses"][0]["quote_digest"] == (
        canonical_payload_digest(quote)
    )
    trace = constraint["canonical_projection_digest_trace"]
    assert trace["status"] == "matched"
    assert trace["producer_digest"] == trace["validator_digest"]
    assert trace["serializer_identity"] == CANONICAL_SERIALIZER_IDENTITY


def test_digest_trace_localizes_legacy_unicode_mismatch_at_projection_boundary() -> (
    None
):
    payload = {"quote": "The authors said “yes”."}
    legacy_ascii_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    trace = canonical_digest_trace(payload, producer_digest=legacy_ascii_digest)

    assert trace["producer_digest"] == legacy_ascii_digest
    assert trace["validator_digest"] == canonical_digest(payload)
    assert trace["serializer_identity"] == CANONICAL_SERIALIZER_IDENTITY
    assert trace["status"] == "mismatch"
    assert trace["first_divergence"]["boundary"] == "canonical_projection_digest"
    assert trace["first_divergence"]["producer_digest"] == legacy_ascii_digest
    assert trace["first_divergence"]["validator_digest"] == trace["validator_digest"]


def test_causal_first_failure_preserves_digest_boundary_fields() -> None:
    trace = {
        "status": "mismatch",
        "producer_digest": "a" * 64,
        "validator_digest": "b" * 64,
        "serializer_identity": "canonical_json_utf8_v1",
        "first_divergence": {"boundary": "canonical_projection_digest"},
    }
    stage_payload = projected_plan_authority_stage_payload(
        {},
        {},
        {},
        authority={"canonical_projection_digest_trace": trace},
    )
    assert stage_payload["status"] == "incomplete"
    assert stage_payload["incompleteness_reasons"] == [
        "canonical_projection_digest_mismatch"
    ]
    stages = []
    previous_chain_digest = ""
    for index, stage in enumerate(QASPER_CAUSAL_TRANSACTION_STAGES, start=1):
        payload = (
            deepcopy(stage_payload)
            if index == 7
            else {"status": "complete", "incompleteness_reasons": []}
        )
        record = _stage_record(
            index,
            stage,
            payload,
            previous_chain_digest=previous_chain_digest,
        )
        stages.append(record)
        previous_chain_digest = record["chain_digest"]
    transaction = {
        "contract_id": "qasper_causal_transaction.v1",
        "transaction_key": {"example_id": "example-1", "route": "fixture"},
        "stages": stages,
    }

    failure = qasper_causal_transaction_first_failure(transaction)

    assert failure["stage_index"] == 7
    assert failure["stage"] == "projected_plan_authority"
    assert failure["reason"] == "transaction_stage_incomplete"
    assert failure["producer_digest"] == trace["producer_digest"]
    assert failure["validator_digest"] == trace["validator_digest"]
    assert failure["serializer_identity"] == trace["serializer_identity"]
    divergence = _first_divergence(failure)
    assert divergence["producer_digest"] == trace["producer_digest"]
    assert divergence["validator_digest"] == trace["validator_digest"]
    assert divergence["serializer_identity"] == trace["serializer_identity"]
