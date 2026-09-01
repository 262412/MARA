from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.fusion_stage import FUSION_STAGE_CONTRACT, fusion_stage_snapshot

from benchmark.docqa_response_projection import response_evidence_outputs
from benchmark.fusion_stage_contract import fusion_stage_audit
from scripts.slurm.validate_contract_smoke import _stage_audit

FIXTURE = Path(__file__).parent / "fixtures/qasper_quality_10389403_fusion_stage.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _item(row: dict, index: int, stage: str) -> dict:
    return {
        "source_id": "paper",
        "span_id": f"{row['example_id'][:8]}-{stage}-{index}",
        "evidence_level": "span",
        "text": f"{stage} evidence {index}.",
    }


def _historical_prediction(row: dict, *, declare_contract: bool = False) -> dict:
    metadata: dict[str, Any] = {
        stage: [_item(row, index, stage) for index in range(1, count + 1)]
        for stage, count in {
            "canonical_candidate_evidence": row["canonical_count"],
            "fused_evidence": row["fused_count"],
            "reranker_input_evidence": row["ranked_count"],
            "reranked_evidence": row["ranked_count"],
            "selected_evidence": min(row["ranked_count"], 8),
            "generation_context_evidence": min(row["ranked_count"], 8),
            "verified_claim_support_evidence": 0,
            "emitted_citation_evidence": 0,
        }.items()
    }
    metadata["ranking_trace"] = {
        "candidate_stage": "post_fusion",
        "executed": True,
        "input_count": row["canonical_count"],
        "output_count": row["ranked_count"],
    }
    if row["hybrid_trace"]:
        metadata["hybrid_fusion_trace"] = {"status": "executed"}
    if declare_contract:
        metadata["ranking_trace"]["fusion_stage_contract_id"] = FUSION_STAGE_CONTRACT
    return {
        "example_id": row["example_id"],
        "route": row["route"],
        "gold_answers": ["yes"]
        if not row["expected_ambiguity_safe_abstention"]
        else ["no"],
        "terminal_outcome": row["terminal_outcome"],
        "qasper_annotation_diagnostics": {
            "ambiguous": row["expected_ambiguity_safe_abstention"]
        },
        "evidence_metadata": metadata,
    }


def _snapshot_prediction(snapshot: dict, items: list[dict]) -> dict:
    metadata = {
        "canonical_candidate_evidence": deepcopy(items),
        "candidate_ranked_evidence": deepcopy(items),
        "fused_evidence": deepcopy(items),
        "hybrid_fusion_trace": {"status": "executed"}
        if snapshot["state"] == "executed"
        else None,
        "fusion_stage_snapshot": deepcopy(snapshot),
        "ranking_trace": {
            "fusion_stage_contract_id": FUSION_STAGE_CONTRACT,
            "candidate_stage": snapshot["candidate_stage"],
            "fusion_stage_snapshot": deepcopy(snapshot),
        },
    }
    if metadata["hybrid_fusion_trace"] is None:
        metadata.pop("hybrid_fusion_trace")
    return {"example_id": "fusion-test", "evidence_metadata": metadata}


def test_job_10389403_freezes_all_18_historical_fusion_observations() -> None:
    fixture = _fixture()
    rows = fixture["rows"]
    assert fixture["source"]["job_id"] == "10389403"
    assert len(rows) == 18
    assert {row["route"] for row in rows} == {
        "text_rag",
        "crag_guarded",
        "controller_auto",
    }
    assert sum(row["hybrid_trace"] for row in rows) == 4
    assert sum(row["expected_ambiguity_safe_abstention"] for row in rows) == 12
    assert fixture["source"]["observed_candidate_stage"] == "post_fusion"

    for row in rows:
        prediction = _historical_prediction(row)
        audit, violations = fusion_stage_audit(prediction)
        assert audit["status"] == "not_applicable"
        assert audit["applicable"] is False
        assert violations == []


def test_declared_new_contract_without_snapshot_fails_closed() -> None:
    for row in _fixture()["rows"]:
        prediction = _historical_prediction(row, declare_contract=True)
        audit, violations = fusion_stage_audit(prediction)
        assert audit["status"] == "failed"
        assert "fusion_stage_snapshot_missing" in violations
        if row["fused_count"] == 0:
            assert "post_fusion_output_missing" in violations


def test_producer_records_executed_passthrough_and_not_executed_states() -> None:
    items = [{"source_id": "paper", "span_id": "s1", "text": "Evidence."}]
    for route in ("text_rag", "crag_guarded", "controller_auto"):
        snapshot = fusion_stage_snapshot(route, items, items, fusion_trace=None)
        prediction = _snapshot_prediction(snapshot, items)
        audit, violations = fusion_stage_audit(prediction)
        assert snapshot["state"] == "passthrough"
        assert audit["status"] == "passed"
        assert violations == []

    executed = fusion_stage_snapshot(
        "controller_auto",
        items,
        items,
        fusion_trace={"status": "executed"},
    )
    audit, violations = fusion_stage_audit(_snapshot_prediction(executed, items))
    assert executed["state"] == "executed"
    assert audit["status"] == "passed"
    assert violations == []

    not_executed = fusion_stage_snapshot("controller_auto", [], [], fusion_trace=None)
    audit, violations = fusion_stage_audit(_snapshot_prediction(not_executed, []))
    assert not_executed["state"] == "not_executed"
    assert audit["status"] == "passed"
    assert violations == []


def test_evidence_bundle_producer_writes_versioned_snapshot_for_routes() -> None:
    request = SimpleNamespace(
        question="Did the paper report the result?",
        query="Did the paper report the result?",
        verification_domain="qasper",
        query_plan=None,
    )
    for route in ("text_rag", "crag_guarded", "controller_auto"):
        bundle = build_evidence_bundle(
            route,
            request,
            {
                "evidence": [
                    {
                        "source_id": "paper",
                        "span_id": "s1",
                        "evidence_level": "span",
                        "text": "The paper reports the result.",
                    }
                ]
            },
        )
        snapshot = bundle.metadata["fusion_stage_snapshot"]
        prediction = {
            "example_id": route,
            "evidence_bundle": bundle.as_dict(),
            "evidence_metadata": bundle.metadata,
        }
        audit, violations = fusion_stage_audit(prediction)
        assert bundle.metadata["ranking_trace"]["fusion_stage_contract_id"] == (
            FUSION_STAGE_CONTRACT
        )
        assert snapshot["route"] == route
        assert snapshot["state"] == "passthrough"
        assert audit["status"] == "passed"
        assert violations == []


def test_fusion_stage_projection_preserves_frozen_producer_order() -> None:
    first = {
        "evidence_id": "runtime-a",
        "source_id": "runtime-source-a",
        "evaluation_source_id": "paper-1",
        "document_id": "paper-1",
        "normalized_text_hash": "hash-a",
        "canonical_start": 10,
        "canonical_end": 31,
        "text": "First canonical span.",
    }
    second = {
        "evidence_id": "runtime-b",
        "source_id": "runtime-source-b",
        "evaluation_source_id": "paper-1",
        "document_id": "paper-1",
        "normalized_text_hash": "hash-b",
        "canonical_start": 40,
        "canonical_end": 62,
        "text": "Second canonical span.",
    }
    producer_order = [second, first]
    snapshot = fusion_stage_snapshot(
        "hybrid",
        producer_order,
        producer_order,
        fusion_trace={"status": "executed"},
    )
    metadata = {
        "query_plan": {"constraints": {"verification_domain": "qasper"}},
        "canonical_candidate_evidence": deepcopy(producer_order),
        "candidate_evidence": deepcopy(producer_order),
        "candidate_ranked_evidence": deepcopy(producer_order),
        "fused_evidence": deepcopy(producer_order),
        "fusion_stage_snapshot": deepcopy(snapshot),
        "hybrid_fusion_trace": {"status": "executed"},
        "ranking_trace": {
            "fusion_stage_contract_id": FUSION_STAGE_CONTRACT,
            "candidate_stage": "post_fusion",
            "fusion_stage_snapshot": deepcopy(snapshot),
        },
    }
    response = SimpleNamespace(
        answer="",
        references_text="",
        evidence_bundle={
            "items": deepcopy(producer_order),
            "metadata": deepcopy(metadata),
        },
        evidence_metadata=metadata,
    )

    evidence_metadata, _retrieved_hits, *_ = response_evidence_outputs(
        response=response,
        documents=[],
        selected_file_ids=[],
    )

    expected = [
        "evidence:runtime-source-b:runtime-b",
        "evidence:runtime-source-a:runtime-a",
    ]
    assert [
        identity_of(item).key
        for item in evidence_metadata["canonical_candidate_evidence"]
    ] == expected
    assert [
        identity_of(item).key for item in evidence_metadata["candidate_ranked_evidence"]
    ] == expected
    assert [
        identity_of(item).key for item in evidence_metadata["fused_evidence"]
    ] == expected
    assert evidence_metadata["fusion_stage_snapshot"]["output_identities"] == expected
    audit, violations = fusion_stage_audit(
        {"example_id": "frozen-order", "evidence_metadata": evidence_metadata}
    )
    assert audit["status"] == "passed"
    assert violations == []


def test_evidence_bundle_stage_records_are_independent_snapshots() -> None:
    request = SimpleNamespace(
        question="Did the paper report the result?",
        query="Did the paper report the result?",
        verification_domain="qasper",
        query_plan=None,
    )
    bundle = build_evidence_bundle(
        "text_rag",
        request,
        {
            "evidence": [
                {
                    "source_id": "paper",
                    "span_id": "s1",
                    "evidence_level": "span",
                    "text": "The paper reports the result.",
                }
            ]
        },
    )
    metadata = bundle.metadata
    canonical = metadata["canonical_candidate_evidence"]
    ranked = metadata["candidate_ranked_evidence"]
    snapshot = metadata["fusion_stage_snapshot"]
    ranking_snapshot = metadata["ranking_trace"]["fusion_stage_snapshot"]

    assert canonical is not ranked
    assert canonical[0] is not ranked[0]
    assert snapshot is not ranking_snapshot

    canonical[0]["span_id"] = "mutated-after-freeze"
    snapshot["output_identities"].reverse()
    assert identity_of(ranked[0]).key == "span:paper:s1"
    assert ranking_snapshot["output_identities"] == ["span:paper:s1"]


def test_expected_ambiguity_safe_abstention_allows_only_empty_terminal_stages() -> None:
    fixture = _fixture()
    expected_rows = [
        row for row in fixture["rows"] if row["expected_ambiguity_safe_abstention"]
    ]
    assert len(expected_rows) == 12
    for row in expected_rows:
        audit, violations = _stage_audit(
            _historical_prediction(row), suite_kind="qasper"
        )
        assert audit["verified_claim_support_evidence"] == {
            "status": "recorded_empty_not_applicable",
            "count": 0,
            "applicability": "not_applicable",
        }
        assert audit["emitted_citation_evidence"] == {
            "status": "recorded_empty_not_applicable",
            "count": 0,
            "applicability": "not_applicable",
        }
        assert "verified_claim_support_evidence" not in violations
        assert "emitted_citation_evidence" not in violations


def test_unambiguous_answerable_empty_terminal_stages_remain_violations() -> None:
    fixture = _fixture()
    unambiguous_rows = [
        row for row in fixture["rows"] if not row["expected_ambiguity_safe_abstention"]
    ]
    assert len(unambiguous_rows) == 6
    for row in unambiguous_rows:
        audit, violations = _stage_audit(
            _historical_prediction(row), suite_kind="qasper"
        )
        assert audit["verified_claim_support_evidence"]["status"] == "empty_required"
        assert audit["emitted_citation_evidence"]["status"] == "empty_required"
        assert "verified_claim_support_evidence" in violations
        assert "emitted_citation_evidence" in violations


def test_ambiguity_exemption_requires_diagnostic_flag_and_safe_abstention() -> None:
    row = next(
        row for row in _fixture()["rows"] if row["expected_ambiguity_safe_abstention"]
    )
    prediction = _historical_prediction(row)
    prediction["qasper_annotation_diagnostics"]["ambiguous"] = False
    audit, violations = _stage_audit(prediction, suite_kind="qasper")
    assert audit["verified_claim_support_evidence"]["status"] == "empty_required"
    assert "verified_claim_support_evidence" in violations

    prediction = _historical_prediction(row)
    prediction["terminal_outcome"] = "execution_failed"
    audit, violations = _stage_audit(prediction, suite_kind="qasper")
    assert audit["emitted_citation_evidence"]["status"] == "empty_required"
    assert "emitted_citation_evidence" in violations
