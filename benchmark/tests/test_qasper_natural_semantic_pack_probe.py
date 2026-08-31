from __future__ import annotations

import hashlib
from copy import deepcopy
from types import SimpleNamespace
from typing import Any, cast

from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_qasper_candidate import _record_candidate_request
from ktem.reasoning.mara_qasper_candidate_prompt import _candidate_evidence
from ktem.reasoning.mara_qasper_candidate_request import fit_candidate_request
from ktem.reasoning.mara_qasper_candidate_transport import (
    qasper_candidate_response_format,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest
from scripts.slurm import qasper_natural_semantic_pack_probe as probe
from scripts.slurm.qasper_natural_semantic_pack_probe import probe_prediction
from scripts.slurm.qasper_natural_semantic_pack_replay import candidate_replay_context

_CODE_SHA = "a" * 40


def _row() -> dict[str, object]:
    question = "Did the authors compare the two systems?"
    text = "The authors compared the two systems."
    return _attach_replay_context(
        {
            "example_id": "natural-probe-example",
            "route": "text_rag",
            "question": question,
            "gold_answers": ["yes"],
            "evidence_bundle": {
                "items": [
                    {
                        "evidence_id": "natural-probe-evidence",
                        "source_id": "paper",
                        "text": text,
                    }
                ]
            },
            "evidence_metadata": {
                "query_plan": {
                    "evidence_slots": [
                        {
                            "slot_id": "support:boolean_proposition",
                            "description": "complete proposition support",
                            "required_for_verification": True,
                            "evidence_ids": [],
                            "evidence_refs": [],
                        }
                    ]
                }
            },
            "qasper_annotation_diagnostics": {
                "ambiguity_reasons": [],
                "boolean_no_evidence_semantics": {},
            },
        }
    )


def _attach_replay_context(row: dict[str, Any]) -> dict[str, Any]:
    bundle = cast(dict[str, Any], row["evidence_bundle"])
    items = cast(list[dict[str, Any]], bundle["items"])
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    query_plan = cast(dict[str, Any], metadata["query_plan"])
    source_items = []
    ranked = []
    for index, item in enumerate(items, start=1):
        text = evidence_item_text(item)
        evidence_id = identity_of(item).key
        source_items.append(
            {
                "source_item_index": index,
                "evidence_id": evidence_id,
                "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_chars": len(text),
                "identity_decision": "eligible",
                "identity_reason": "accepted_for_semantic_ranking",
            }
        )
        ranked.append({"ranked_position": index - 1, "canonical_id": evidence_id})
    snapshot = {
        "contract_id": "semantic_source_input_snapshot.v1",
        "complete": True,
        "source_items": source_items,
        "ranked_evidence_present": True,
        "ranked_evidence": ranked,
        "query_plan": deepcopy(query_plan),
        "query_plan_digest": canonical_digest(query_plan),
        "max_context_length": None,
    }
    snapshot["snapshot_digest"] = canonical_digest(snapshot)
    metadata["qasper_canonical_semantic_pack"] = {
        "source_packing_observation": {"source_input_snapshot": snapshot}
    }
    transaction_id = "c" * 64
    metadata["qasper_candidate_generation"] = {
        "trace_group_id": "natural-probe-fixture",
        "benchmark_route_id": str(row.get("route") or ""),
        "internal_route": str(row.get("route") or ""),
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:candidate_generation:1",
        "generation_sequence": 0,
        "predecessor_transaction_id": "",
        "effective_seed": 20260724,
        "candidate_request_dropped_evidence_count": 0,
    }
    row["retrieved_hits"] = deepcopy(items)
    _record_fixture_candidate_request(row)
    replay = candidate_replay_context(row)
    context = probe.freeze_natural_pack(
        str(row.get("question") or ""),
        route=str(row.get("route") or ""),
        example_id=str(row.get("example_id") or ""),
        replay=replay,
        code_sha=_CODE_SHA,
    )
    metadata["qasper_candidate_generation"] = deepcopy(context.candidate_generation)
    metadata["qasper_canonical_semantic_pack"] = deepcopy(
        context.bundle.metadata["qasper_canonical_semantic_pack"]
    )
    metadata["candidate_ranked_evidence"] = deepcopy(
        context.bundle.metadata["candidate_ranked_evidence"]
    )
    metadata["semantic_proposition_verifier"] = {
        "contract_id": "semantic_proposition_verifier_runtime.v3",
        "status": "not_run_in_fixture_reference",
        "semantic_data_lineage": {
            "contract_id": "semantic_proposition_data_lineage.v1",
            "source_packing": deepcopy(
                context.bundle.metadata["qasper_canonical_semantic_pack"][
                    "source_packing_observation"
                ]
            ),
            "plan_construction": deepcopy(context.binding["plan_construction_trace"]),
        },
    }
    return row


def _record_fixture_candidate_request(row: dict[str, Any]) -> None:
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    initial = cast(dict[str, Any], metadata["qasper_candidate_generation"])
    replay = candidate_replay_context(row)
    question = str(row["question"])
    transaction_id = str(initial["transaction_id"])
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="qasper",
        dataset_family="qasper",
        answer_type="boolean",
        question=question,
        query=question,
        query_plan=deepcopy(replay.query_plan),
    )
    bundle = EvidenceBundle(
        route=str(row["route"]),
        items=deepcopy(replay.items),
        metadata=deepcopy(replay.bundle_metadata),
    )
    records, diagnostics, _source_packing = _candidate_evidence(
        request,
        question,
        bundle,
        candidate_transaction_id=transaction_id,
    )
    response_schema = qasper_candidate_response_format()
    (
        records,
        diagnostics,
        messages,
        token_measurement,
        dropped_count,
    ) = fit_candidate_request(
        None,
        question,
        records,
        diagnostics,
        response_schema=response_schema,
        controlled_candidate="",
        candidate_transaction_id=transaction_id,
    )
    identity = {
        key: deepcopy(initial.get(key))
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
    observation, _input_digest = _record_candidate_request(
        bundle,
        llm=None,
        messages=messages,
        response_schema=response_schema,
        identity=identity,
        route=str(row["route"]),
        seed=int(initial["effective_seed"]),
        evidence=records,
        evidence_diagnostics=diagnostics,
        controlled_candidate="",
        token_measurement=token_measurement,
        request_dropped_count=dropped_count,
    )
    metadata["qasper_candidate_generation"] = observation


def test_natural_probe_reuses_one_plan_across_pack_schema_parser_and_constraint() -> (
    None
):
    result = probe_prediction(_row(), code_sha=_CODE_SHA)

    assert result["status"] == "passed"
    assert result["binding_state"] == "relation_bound_support"
    assert result["schema_parser"]["schema_accepted"] is True
    assert result["schema_parser"]["parser_accepted"] is True
    assert result["schema_parser"]["downstream_status"] == "passed"
    assert result["plan_construction_trace"]["candidate_count"] >= 1
    assert result["plan_construction_trace"]["bounded_selector_refs"]
    assert result["packing_observation"]["contract_id"] == (
        "qasper_source_packing_observation.v1"
    )
    assert result["packing_observation"]["record_count"] >= 1
    assert result["packing_observation"]["selector_count"] >= 1
    assert result["packing_observation"]["source_records"]
    assert result["packing_observation"]["source_records"][0]["stop_stage"]
    assert result["checks"]["causal_trace_prefix_complete"] is True
    assert result["checks"]["production_candidate_path_replayed"] is True
    assert result["checks"]["candidate_request_input_replayed"] is True
    assert result["checks"]["online_local_causal_prefix_matched"] is True
    causal_replay = result["causal_transaction_replay"]
    assert causal_replay["status"] == "matched"
    assert causal_replay["through_stage_index"] == 7
    assert causal_replay["through_stage"] == "projected_plan_authority"
    assert causal_replay["comparison"]["status"] == "matched_prefix"
    assert causal_replay["comparison"]["later_stages_evaluated"] is False
    assert result["candidate_path_replay"]["stage_sequence"][-1] == (
        "canonical_pack_freeze"
    )
    assert all(result["checks"].values())


def test_natural_probe_fails_closed_on_a_tampered_trace_digest(monkeypatch) -> None:
    original = probe.qasper_causal_evidence_chain_prefix_complete

    def tampered_prefix(row: dict[str, Any]) -> bool:
        lineage = row["semantic_verifier"]["semantic_data_lineage"]
        lineage["source_packing"]["source_decisions_digest"] = "0" * 64
        return original(row)

    monkeypatch.setattr(
        probe,
        "qasper_causal_evidence_chain_prefix_complete",
        tampered_prefix,
    )

    result = probe_prediction(_row(), code_sha=_CODE_SHA)

    assert result["checks"]["causal_trace_prefix_complete"] is False
    assert result["status"] == "failed"


def test_natural_probe_reports_only_the_first_online_local_path_divergence() -> None:
    row = _row()
    generator = cast(
        dict[str, Any],
        cast(dict[str, Any], row["evidence_metadata"])["qasper_candidate_generation"],
    )
    messages = deepcopy(generator["message_stack"])
    messages[1]["content"] += "\nTAMPERED ONLINE INPUT"
    generator["message_stack"] = messages
    generator["message_stack_digest"] = canonical_digest(messages)
    generator["input_digest"] = canonical_digest(
        {
            "messages": messages,
            "response_schema_digest": generator["response_schema_digest"],
            "seed": generator["effective_seed"],
            "route": row["route"],
            "benchmark_route_id": generator["benchmark_route_id"],
        }
    )

    result = probe_prediction(row, code_sha=_CODE_SHA)

    comparison = result["causal_transaction_replay"]["comparison"]
    assert comparison["status"] == "diverged"
    assert comparison["first_divergence"]["stage_index"] == 3
    assert comparison["first_divergence"]["stage"] == "candidate_input"
    assert comparison["later_stages_evaluated"] is False
    assert "later_divergences" not in comparison


def test_natural_probe_rejects_unambiguous_unresolved_zero_plan() -> None:
    row = _row()
    row["evidence_bundle"] = {
        "items": [
            {
                "evidence_id": "natural-probe-evidence",
                "source_id": "paper",
                "text": "The paper discusses comparisons between systems.",
            }
        ]
    }
    _attach_replay_context(row)

    result = probe_prediction(row, code_sha=_CODE_SHA)

    assert result["binding_state"] == "unresolved"
    assert result["canonical_plan_count"] == 0
    assert result["ambiguity"]["ambiguous"] is False
    assert result["checks"]["unambiguous_zero_plan_rejected"] is False
    assert result["status"] == "failed"


def test_natural_probe_rejects_a_plan_that_fails_the_audit_constraint(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        probe,
        "semantic_relation_evidence_set_constraint",
        lambda *_args, **_kwargs: {
            "status": "rejected",
            "reason": "audit_invalid_plan",
        },
    )

    result = probe_prediction(deepcopy(_row()), code_sha=_CODE_SHA)

    assert result["schema_parser"]["downstream_status"] == "rejected"
    assert result["checks"]["canonical_plan_audit_valid"] is False
    assert result["status"] == "failed"


def test_natural_probe_keeps_ambiguous_and_unambiguous_denominators_separate() -> None:
    ambiguous = _row()
    base_bundle = cast(dict[str, Any], _row()["evidence_bundle"])
    base_items = cast(list[dict[str, Any]], base_bundle["items"])
    ambiguous["evidence_bundle"] = {
        "items": [
            *base_items,
            {
                "evidence_id": "natural-probe-contradiction",
                "source_id": "paper",
                "text": "The authors did not compare the two systems.",
            },
        ]
    }
    ambiguous["qasper_annotation_diagnostics"] = {
        "ambiguous": True,
        "ambiguity_reasons": ["annotation_answer_disagreement"],
        "boolean_no_evidence_semantics": {},
    }
    _attach_replay_context(ambiguous)

    audit = probe.build_audit(
        [
            probe_prediction(_row(), code_sha=_CODE_SHA),
            probe_prediction(ambiguous, code_sha=_CODE_SHA),
        ],
        code_sha=_CODE_SHA,
        input_path=__import__("pathlib").Path(__file__),
        expected_count=2,
    )

    assert audit["ambiguity_denominator"] == {
        "ambiguous": 1,
        "unambiguous": 1,
    }
    assert audit["hard_gates"]["ambiguity_denominator_complete"] is True


def test_six_sample_probe_requires_the_frozen_four_two_denominator() -> None:
    prediction = probe_prediction(_row(), code_sha=_CODE_SHA)
    audit = probe.build_audit(
        [deepcopy(prediction) for _index in range(6)],
        code_sha=_CODE_SHA,
        input_path=__import__("pathlib").Path(__file__),
        expected_count=6,
    )

    assert audit["ambiguity_denominator"] == {"unambiguous": 6}
    assert audit["hard_gates"]["six_sample_ambiguity_denominator_4_2"] is False
    assert audit["status"] == "failed"


def test_six_sample_probe_accepts_four_ambiguous_two_unambiguous() -> None:
    prediction = probe_prediction(_row(), code_sha=_CODE_SHA)
    predictions = [deepcopy(prediction) for _index in range(6)]
    for value in predictions[:4]:
        value["ambiguity"] = {
            "ambiguous": True,
            "reasons": ["boolean_no_requires_closed_world_inference"],
            "denominator": "ambiguous",
        }
    audit = probe.build_audit(
        predictions,
        code_sha=_CODE_SHA,
        input_path=__import__("pathlib").Path(__file__),
        expected_count=6,
    )

    assert audit["ambiguity_denominator"] == {
        "ambiguous": 4,
        "unambiguous": 2,
    }
    assert audit["hard_gates"]["six_sample_ambiguity_denominator_4_2"] is True


def test_probe_code_identity_gate_rejects_dirty_or_non_sha_runs() -> None:
    prediction = probe_prediction(_row(), code_sha=_CODE_SHA)
    dirty = probe.build_audit(
        [prediction],
        code_sha=_CODE_SHA,
        input_path=__import__("pathlib").Path(__file__),
        expected_count=1,
        runtime_code_sha=_CODE_SHA,
        runtime_worktree_clean=False,
    )
    labeled_dirty = probe.build_audit(
        [{**prediction, "code_sha": f"{_CODE_SHA}-dirty"}],
        code_sha=f"{_CODE_SHA}-dirty",
        input_path=__import__("pathlib").Path(__file__),
        expected_count=1,
    )

    assert dirty["hard_gates"]["single_clean_code_identity"] is False
    assert labeled_dirty["hard_gates"]["single_clean_code_identity"] is False


def test_legacy_replay_uses_candidate_stage_rank_not_late_bundle_rank() -> None:
    row = _row()
    bundle = cast(dict[str, Any], row["evidence_bundle"])
    items = cast(list[dict[str, Any]], bundle["items"])
    items.append(
        {
            "evidence_id": "late-rank-evidence",
            "source_id": "paper",
            "text": "The paper discusses unrelated implementation details.",
        }
    )
    _attach_replay_context(row)
    metadata = cast(dict[str, Any], row["evidence_metadata"])
    pack = cast(dict[str, Any], metadata["qasper_canonical_semantic_pack"])
    source = cast(dict[str, Any], pack["source_packing_observation"])
    del source["source_input_snapshot"]
    observations = []
    for position, item in enumerate(reversed(items)):
        text = evidence_item_text(item)
        observations.append(
            {
                "evidence_id": identity_of(item).key,
                "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "text_chars": len(text),
                "priority": [0, position],
            }
        )
    source["source_records"] = observations
    bundle["metadata"] = {
        "candidate_ranked_evidence": [
            {"canonical_id": identity_of(item).key} for item in items
        ]
    }

    replay = candidate_replay_context(row)

    assert replay.observation["complete"] is False
    assert replay.observation["context_source"] == ("legacy_source_priority_projection")
    assert (
        "legacy_replay_not_causally_verifiable"
        in replay.observation["incompleteness_reasons"]
    )
    assert [row["canonical_id"] for row in replay.observation["ranked_evidence"]] == [
        identity_of(item).key for item in reversed(items)
    ]
