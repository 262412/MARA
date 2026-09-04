from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_semantic_proposition_verifier import (
    build_semantic_proposition_verifier,
)
from ktem_tests.test_mara_semantic_proposition_verifier import (
    QUESTION,
    _insufficient_response,
    _items,
    _model_response,
    _RecordingLLM,
    _request,
)


def _request_for_transaction(group: str, route: str = "") -> Any:
    request = _request()
    request.trace_context = {
        "trace_group_id": group,
        "benchmark_route_id": route,
    }
    return request


def _bundle_for_transaction(transaction_id: str) -> EvidenceBundle:
    return EvidenceBundle(
        route="doc_text",
        items=_items(),
        metadata={"qasper_candidate_generation": {"transaction_id": transaction_id}},
    )


def test_cached_judgment_rebinds_current_transaction_and_auditor_identity() -> None:
    llm = _RecordingLLM(_model_response())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    verifier_state: Any = verifier

    first_bundle = _bundle_for_transaction("candidate-first")
    first = verifier(
        _request_for_transaction("group-first", "route-first"),
        QUESTION,
        "yes",
        first_bundle,
    )
    assert first is not None

    second_bundle = _bundle_for_transaction("candidate-second")
    second = verifier(
        _request_for_transaction("group-second", "route-second"),
        QUESTION,
        "yes",
        second_bundle,
    )

    assert second is not None
    assert second["verifier"]["candidate_transaction_id"] == "candidate-second"
    assert second["entailment_audit"]["semantic_pack_identity"] == {
        "semantic_pack_digest": second["verifier"]["semantic_pack_digest"],
        "span_universe_digest": second["verifier"]["canonical_span_universe_digest"],
        "candidate_transaction_id": "candidate-second",
    }
    assert (
        second_bundle.metadata["semantic_proposition_verifier"][
            "auditor_semantic_pack_identity"
        ]["candidate_transaction_id"]
        == "candidate-second"
    )
    assert second_bundle.metadata["semantic_proposition_verifier"][
        "transaction_id"
    ] != (first_bundle.metadata["semantic_proposition_verifier"]["transaction_id"])
    for field in ("attempt_id", "auditor_attempt_id"):
        assert second_bundle.metadata["semantic_proposition_verifier"][field] != (
            first_bundle.metadata["semantic_proposition_verifier"][field]
        )
    [cached] = verifier_state.cache.values()
    assert cached is not None
    assert "semantic_pack_digest" not in cached["verifier"]
    assert "candidate_transaction_id" not in cached["verifier"]
    assert "semantic_pack_identity" not in cached["entailment_audit"]
    [cached_diagnostics] = verifier_state.cache_diagnostics.values()
    assert "auditor_semantic_pack_identity" not in cached_diagnostics
    assert len(llm.calls) == 2


def test_cached_unknown_judgment_rebinds_candidate_audit_identity() -> None:
    llm = _RecordingLLM(_insufficient_response())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None

    first = verifier(
        _request_for_transaction("unknown-first"),
        QUESTION,
        "yes",
        _bundle_for_transaction("unknown-first"),
    )
    assert first is not None
    second = verifier(
        _request_for_transaction("unknown-second"),
        QUESTION,
        "yes",
        _bundle_for_transaction("unknown-second"),
    )

    assert second is not None
    assert (
        second["candidate_verification_audit"]["semantic_pack_identity"][
            "candidate_transaction_id"
        ]
        == "unknown-second"
    )
    assert len(llm.calls) == 2
