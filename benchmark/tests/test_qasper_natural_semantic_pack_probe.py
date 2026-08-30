from __future__ import annotations

import hashlib
from copy import deepcopy
from typing import Any, cast

from ktem.docqa.boolean_evidence_scope import evidence_item_text
from ktem.docqa.evidence_identity import identity_of

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
        "query_plan_digest": canonical_digest(query_plan),
        "max_context_length": None,
    }
    metadata["qasper_canonical_semantic_pack"] = {
        "source_packing_observation": {"source_input_snapshot": snapshot}
    }
    metadata["qasper_candidate_generation"] = {
        "candidate_request_dropped_evidence_count": 0
    }
    return row


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

    assert replay.observation["complete"] is True
    assert replay.observation["context_source"] == ("legacy_source_priority_projection")
    assert [row["canonical_id"] for row in replay.observation["ranked_evidence"]] == [
        identity_of(item).key for item in reversed(items)
    ]
