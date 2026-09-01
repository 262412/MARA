from __future__ import annotations

import json
from copy import deepcopy
from types import SimpleNamespace
from typing import Any, cast

from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_validation import (
    premise_slot_evidence_for_audit,
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_qasper_candidate import _record_candidate_response
from ktem.reasoning.mara_qasper_semantic_pack import qasper_canonical_selector_bindings
from ktem.reasoning.mara_semantic_entailment_audit import (
    parse_semantic_entailment_audit,
)
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
)

from benchmark.qasper_causal_transaction import qasper_causal_transaction
from benchmark.qasper_causal_transaction_runtime_stages import (
    runtime_transaction_stage_payloads,
)
from benchmark.tests.qasper_terminal_projection_fixture import (
    attach_valid_terminal_projection,
)
from benchmark.tests.test_qasper_causal_transaction import (
    _prediction_and_debug_row,
    _run_context,
)
from benchmark.tests.test_qasper_natural_semantic_pack_probe import _CODE_SHA, _row
from benchmark.tests.test_qasper_stage7_causal_transaction import _projection_fixture
from scripts.slurm import qasper_natural_semantic_pack_probe as probe
from scripts.slurm.qasper_natural_causal_transaction import (
    natural_causal_transaction_replay,
)
from scripts.slurm.qasper_natural_semantic_pack_replay import candidate_replay_context


def _row_with_real_raw_response() -> dict[str, Any]:
    row = cast(dict[str, Any], _row())
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    generation = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    identity = {
        key: str(generation.get(key) or "")
        for key in (
            "trace_group_id",
            "benchmark_route_id",
            "internal_route",
            "transaction_id",
            "attempt_id",
            "generation_sequence",
            "predecessor_transaction_id",
        )
    }
    _record_candidate_response(
        SimpleNamespace(
            text='{\n\n\n    "candidate": "yes"\n}',
            completion_tokens=10,
            prompt_tokens=generation["estimated_input_tokens"],
            finish_reason="stop",
        ),
        generation,
        identity,
        str(generation["input_digest"]),
        "",
    )
    return row


def test_stage_eight_replays_and_reparses_the_frozen_candidate_response() -> None:
    row = _row_with_real_raw_response()
    online = cast(
        dict[str, Any],
        cast(dict[str, Any], row["evidence_metadata"])["qasper_candidate_generation"],
    )
    replay = candidate_replay_context(row)

    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )

    local = context.candidate_generation
    for field in (
        "status",
        "failure_reason",
        "raw_response",
        "raw_response_digest",
        "raw_response_truncated",
        "cleaned_response",
        "typed_candidate",
        "typed_candidate_digest",
        "attempts",
    ):
        assert local[field] == online[field]
    assert local["candidate_response_replay"]["status"] == "matched"


def test_stage_eight_rejects_a_tampered_frozen_raw_response_digest() -> None:
    row = _row_with_real_raw_response()
    generation = cast(
        dict[str, Any],
        cast(dict[str, Any], row["evidence_metadata"])["qasper_candidate_generation"],
    )
    generation["raw_response"] = '{"candidate":"no"}'
    replay = candidate_replay_context(row)

    context = probe.freeze_natural_pack(
        str(row["question"]),
        route=str(row["route"]),
        example_id=str(row["example_id"]),
        replay=replay,
        code_sha=_CODE_SHA,
    )

    response_replay = context.candidate_generation["candidate_response_replay"]
    assert response_replay["status"] == "failed"
    assert "candidate_raw_response_digest_mismatch" in response_replay["reasons"]


def test_stage_eight_accepts_a_typed_pre_audit_stop_without_a_proposal() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    verifier = debug_row["semantic_verifier"]
    event = verifier["debug_trace"]["events"][0]
    event["transaction"] = {}
    event["outcome"] = {
        "status": "failed",
        "reason": "release_conclusion_auditor_not_independent",
        "audit_status": "not_started",
        "audit_reason": "release_conclusion_auditor_not_independent",
    }
    verifier.update(
        status="failed",
        reason="release_conclusion_auditor_not_independent",
        audit_reason="release_conclusion_auditor_not_independent",
        candidate_verification_status="pre_audit_failed",
        proposal_status="not_started",
        audit_status="not_started",
    )

    transaction = qasper_causal_transaction(
        prediction,
        debug_row,
        run_context=_run_context(),
    )
    stage = transaction["stages"][7]

    assert stage["status"] == "complete"
    assert stage["incompleteness_reasons"] == []
    assert stage["payload"]["semantic_proposal"] == {}
    assert stage["payload"]["semantic_audit"] == {}


def test_stage_eight_attempt_digest_ignores_empty_normalization_fields() -> None:
    prediction, debug_row = _prediction_and_debug_row()
    generator = debug_row["main_candidate_generator"]
    normalized_generator = deepcopy(generator)
    normalized_generator["attempts"][0].update(
        provider_failure_reason="",
        provider_failure_detail="",
    )
    verifier = debug_row["semantic_verifier"]
    event = verifier["debug_trace"]["events"][0]
    transaction = event["transaction"]

    reference = runtime_transaction_stage_payloads(
        prediction,
        generator,
        verifier,
        event,
        transaction,
        transaction["proposal"],
        transaction["audit"],
        _run_context(),
    )["model_response_and_parser"]
    normalized = runtime_transaction_stage_payloads(
        prediction,
        normalized_generator,
        verifier,
        event,
        transaction,
        transaction["proposal"],
        transaction["audit"],
        _run_context(),
    )["model_response_and_parser"]

    assert normalized == reference


def _semantic_response_replay_fixture() -> tuple[dict[str, Any], Any]:
    prediction, debug_row, plan = _projection_fixture()
    pack = prediction["evidence_metadata"]["qasper_canonical_semantic_pack"]
    transaction = debug_row["semantic_verifier"]["debug_trace"]["events"][0][
        "transaction"
    ]
    debug_row["semantic_verifier"]["debug_trace"]["events"][0][
        "auditor_relationship"
    ] = "distinct_model"
    proposal_raw = json.dumps(
        {
            "candidate_judgment": "supported",
            "canonical_evidence_plan_id": plan["plan_id"],
        },
        separators=(",", ":"),
    )
    proposal = _parse_local_proposal(prediction, pack, plan, proposal_raw)
    transaction["proposal"]["attempts"][0].update(
        raw_response=proposal_raw,
        parsed_value=proposal,
    )
    audit_raw, audit_value = _local_audit_response(prediction, proposal)
    transaction["audit"]["attempts"][0].update(
        raw_response=audit_raw,
        parsed_value=audit_value,
    )
    prediction["evidence_metadata"]["semantic_proposition_verifier"] = deepcopy(
        debug_row["semantic_verifier"]
    )
    attach_valid_terminal_projection(prediction)
    context = SimpleNamespace(
        bundle=SimpleNamespace(metadata=prediction["evidence_metadata"]),
        binding=pack["proposition_binding"],
        candidate_generation=debug_row["main_candidate_generator"],
        slots=pack["slots"],
    )
    return prediction, context


def _parse_local_proposal(
    prediction: dict[str, Any],
    pack: dict[str, Any],
    plan: dict[str, Any],
    raw_response: str,
) -> dict[str, Any]:
    parsed = parse_semantic_proposition_response(
        raw_response,
        packed=pack["records"],
        slot_ids={slot["slot_id"] for slot in pack["slots"]},
        model="verifier-model:v2",
        seed=0,
        candidate="yes",
        applicable_proposition_slots=pack["proposition_binding"]["applicable_slots"],
        allowed_proposition_slot_bindings=qasper_canonical_selector_bindings(
            pack["records"]
        ),
        slot_evidence_refs={
            slot["slot_id"]: tuple(slot["evidence_refs"]) for slot in pack["slots"]
        },
        allowed_proposition_evidence_plans={plan["plan_id"]: plan},
    )
    assert parsed.failure_reason == ""
    assert parsed.value is not None
    return parsed.value


def _local_audit_response(
    prediction: dict[str, Any],
    proposal: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    premises = proposal["premises"]
    expectations = {
        f"P{index}": tuple(premise["binds_proposition_slots"])
        for index, premise in enumerate(premises, start=1)
    }
    constraint = semantic_relation_evidence_set_constraint(
        premises,
        build_question_proposition(prediction["question"]),
        proposal["verdict"],
        auditor_relationship="distinct_model",
    )
    slot_evidence = premise_slot_evidence_for_audit(constraint)
    raw_response = _audit_raw_response(expectations)
    parsed = parse_semantic_entailment_audit(
        raw_response,
        premise_labels=list(expectations),
        premise_slot_expectations=expectations,
        premise_slot_evidence=slot_evidence,
    )
    assert parsed.failure_reason == ""
    assert parsed.value is not None
    return raw_response, parsed.value


def _audit_raw_response(expectations: dict[str, tuple[str, ...]]) -> str:
    flags = {
        "conclusion_entailed": True,
        "actor_consistent": True,
        "predicate_consistent": True,
        "object_consistent": True,
        "polarity_consistent": True,
        "quantifier_consistent": True,
        "scope_consistent": True,
    }
    payload = {
        "premise_checks": {
            label: {
                "fragment_entailed": True,
                "scope_consistent": True,
                "evidence_relation_valid": True,
                "proposition_slot_checks": {
                    slot: {
                        "binding_valid": True,
                        "evidence_ref": f"{label}:{slot}",
                    }
                    for slot in slots
                },
            }
            for label, slots in expectations.items()
        },
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "conclusion_check": flags,
    }
    return json.dumps(payload, separators=(",", ":"))


def test_stage_eight_replays_semantic_proposal_and_audit_raw_responses() -> None:
    prediction, context = _semantic_response_replay_fixture()

    replay = natural_causal_transaction_replay(prediction, context, through_stage=8)

    assert replay["status"] == "matched"
    assert replay["through_stage_index"] == 8
    reference = replay["reference_transaction"]["stages"][7]
    local = replay["local_replay_transaction"]["stages"][7]
    assert local["comparison_digest"] == reference["comparison_digest"]


def test_stage_eight_rejects_a_forged_frozen_semantic_parse() -> None:
    prediction, context = _semantic_response_replay_fixture()
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    transaction = verifier["debug_trace"]["events"][0]["transaction"]
    transaction["proposal"]["attempts"][0]["parsed_value"]["verifier"]["seed"] = 999
    attach_valid_terminal_projection(prediction)

    replay = natural_causal_transaction_replay(prediction, context)

    assert replay["status"] == "failed"
    comparison = replay["comparison"]
    assert comparison["first_divergence"]["stage_index"] == 8
    assert comparison["later_stages_evaluated"] is False
    local = replay["local_replay_transaction"]["stages"][7]
    assert "semantic_proposal_parser_replay_mismatch" in local["incompleteness_reasons"]
