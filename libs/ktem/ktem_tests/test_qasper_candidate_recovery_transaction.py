from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.execution_models import GuardrailDecision, RouteExecutionResult
from ktem.docqa.execution_qasper_candidate_recovery import (
    regenerate_qasper_candidate as _regenerate_qasper_candidate,
)
from ktem.docqa.pipeline_stage_timings import PipelineStageTimings
from ktem.docqa.route_selection import ControllerDecision
from ktem.docqa.verification_schema import VerifyDecision
from ktem.reasoning.mara_qasper_candidate_identity import candidate_transaction_identity


def _decision() -> ControllerDecision:
    return ControllerDecision(
        route="text_rag",
        legacy_route="doc_text",
        policy="doc",
        controller_mode="rules",
        requires_retrieval=True,
        reason="test",
    )


def _initial_result() -> RouteExecutionResult:
    bundle = EvidenceBundle(
        route="doc_text",
        items=[{"evidence_id": "old", "source_id": "paper", "text": "old"}],
        metadata={
            "qasper_canonical_semantic_pack": {
                "semantic_pack_digest": "old-pack",
                "span_universe_digest": "old-spans",
                "candidate_transaction_id": "old-transaction",
            },
            "qasper_candidate_generation": {
                "transaction_id": "old-transaction",
                "generation_sequence": 0,
                "predecessor_transaction_id": "",
                "canonical_semantic_pack_digest": "old-pack",
                "canonical_span_universe_digest": "old-spans",
                "canonical_pack_candidate_transaction_id": "old-transaction",
            },
        },
    )
    return RouteExecutionResult(
        controller_decision=_decision(),
        retrieve_decision=RetrieveDecision(status="good", reason="test"),
        verify_decision=VerifyDecision(
            mode="strict",
            status="unknown",
            reason="authority_missing",
        ),
        guardrail_decision=GuardrailDecision(
            status="blocked",
            action="abstain",
            reason="authority_missing",
        ),
        evidence_bundle=bundle,
        answer="yes",
    )


def _request() -> SimpleNamespace:
    return SimpleNamespace(
        verification_domain="qasper",
        dataset_family="qasper",
        generation_timeout_seconds=None,
    )


def test_recovery_adopts_new_candidate_transaction_only_after_pack_change() -> None:
    initial = _initial_result()
    recovered = EvidenceBundle(
        route="doc_text",
        items=[{"evidence_id": "new", "source_id": "paper", "text": "new"}],
        metadata=dict(initial.evidence_bundle.metadata),
    )
    observed: dict[str, Any] = {}

    def generate(_request: Any, _decision: Any, bundle: EvidenceBundle) -> str:
        observed.update(bundle.metadata)
        bundle.metadata["qasper_canonical_semantic_pack"] = {
            "semantic_pack_digest": "new-pack",
            "span_universe_digest": "new-spans",
            "candidate_transaction_id": "new-transaction",
        }
        bundle.metadata["qasper_candidate_generation"] = {
            "transaction_id": "new-transaction",
            "generation_sequence": 1,
            "predecessor_transaction_id": "old-transaction",
            "canonical_semantic_pack_digest": "new-pack",
            "canonical_span_universe_digest": "new-spans",
            "canonical_pack_candidate_transaction_id": "new-transaction",
        }
        return "no"

    event: dict[str, Any] = {"stage": "reverify"}
    bundle, candidate, stopped = _regenerate_qasper_candidate(
        _request(),
        initial,
        _decision(),
        RetrieveDecision(status="good", reason="recovered"),
        recovered,
        "yes",
        generate,
        [event],
        event,
        PipelineStageTimings(),
    )

    assert stopped is None
    assert candidate == "no"
    assert (
        bundle.metadata["qasper_canonical_semantic_pack"]["candidate_transaction_id"]
        == "new-transaction"
    )
    assert observed["qasper_candidate_generation_sequence"] == 1
    assert observed["qasper_candidate_predecessor_transaction_id"] == (
        "old-transaction"
    )
    assert event["recovery_action"] == "new_candidate_transaction"
    assert event["candidate_transaction_changed"] is True


def test_recovery_stops_before_verifier_when_effective_pack_is_unchanged() -> None:
    initial = _initial_result()
    recovered = EvidenceBundle(
        route="doc_text",
        items=[{"evidence_id": "late", "source_id": "paper", "text": "late"}],
        metadata=dict(initial.evidence_bundle.metadata),
    )

    def generate(_request: Any, _decision: Any, bundle: EvidenceBundle) -> str:
        bundle.metadata["qasper_canonical_semantic_pack"] = {
            "semantic_pack_digest": "old-pack",
            "span_universe_digest": "old-spans",
            "candidate_transaction_id": "new-transaction",
        }
        bundle.metadata["qasper_candidate_generation"] = {
            "transaction_id": "new-transaction",
            "generation_sequence": 1,
            "predecessor_transaction_id": "old-transaction",
            "canonical_semantic_pack_digest": "old-pack",
            "canonical_span_universe_digest": "old-spans",
            "canonical_pack_candidate_transaction_id": "new-transaction",
        }
        return "yes"

    event: dict[str, Any] = {"stage": "reverify"}
    bundle, candidate, stopped = _regenerate_qasper_candidate(
        _request(),
        initial,
        _decision(),
        RetrieveDecision(status="good", reason="recovered"),
        recovered,
        "yes",
        generate,
        [event],
        event,
        PipelineStageTimings(),
    )

    assert bundle is recovered
    assert candidate == "yes"
    assert stopped is not None
    assert event["recovery_action"] == "stop_without_reverify"
    assert event["stop_reason"] == "canonical_semantic_pack_unchanged"


def test_recovery_stops_when_new_pack_and_candidate_trace_disagree() -> None:
    initial = _initial_result()
    recovered = EvidenceBundle(
        route="doc_text",
        items=[{"evidence_id": "new", "source_id": "paper", "text": "new"}],
        metadata=dict(initial.evidence_bundle.metadata),
    )

    def generate(_request: Any, _decision: Any, bundle: EvidenceBundle) -> str:
        bundle.metadata["qasper_canonical_semantic_pack"] = {
            "semantic_pack_digest": "new-pack",
            "span_universe_digest": "new-spans",
            "candidate_transaction_id": "new-transaction",
        }
        bundle.metadata["qasper_candidate_generation"] = {
            "transaction_id": "new-transaction",
            "generation_sequence": 1,
            "predecessor_transaction_id": "wrong-predecessor",
            "canonical_semantic_pack_digest": "new-pack",
            "canonical_span_universe_digest": "new-spans",
            "canonical_pack_candidate_transaction_id": "new-transaction",
        }
        return "no"

    event: dict[str, Any] = {"stage": "reverify"}
    bundle, candidate, stopped = _regenerate_qasper_candidate(
        _request(),
        initial,
        _decision(),
        RetrieveDecision(status="good", reason="recovered"),
        recovered,
        "yes",
        generate,
        [event],
        event,
        PipelineStageTimings(),
    )

    assert bundle is recovered
    assert candidate == "yes"
    assert stopped is not None
    assert event["recovery_action"] == "stop_without_reverify"
    assert event["stop_reason"] == (
        "candidate_transaction_identity_invalid_after_recovery"
    )


def test_candidate_transaction_identity_advances_with_generation_sequence() -> None:
    request = SimpleNamespace(
        dataset_family="qasper",
        prompt="Did the authors compare the systems?",
        trace_context={"trace_group_id": "group", "benchmark_route_id": "route"},
    )

    initial = candidate_transaction_identity(
        request,
        "doc_text",
        17,
    )
    recovered = candidate_transaction_identity(
        request,
        "doc_text",
        17,
        generation_sequence=1,
        predecessor_transaction_id=initial["transaction_id"],
    )

    assert recovered["transaction_id"] != initial["transaction_id"]
    assert recovered["generation_sequence"] == 1
    assert recovered["predecessor_transaction_id"] == initial["transaction_id"]
