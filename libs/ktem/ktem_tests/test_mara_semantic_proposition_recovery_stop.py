from __future__ import annotations

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem_tests.test_mara_semantic_proposition_audit import (
    QUESTION,
    _atomic_audit,
    _audit_with_false_premise_but_joint_entailment,
    _items,
    _proposal,
    _rebuilt_atomic_proposal,
    _request,
    _response,
    _SequenceLLM,
    _verifier,
)


def test_unprunable_contradictory_audit_stops_without_reanswering() -> None:
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response(_audit_with_false_premise_but_joint_entailment()),
            _response(_rebuilt_atomic_proposal()),
            _response(_atomic_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None
    assert result["verdict"] == "insufficient_evidence"
    assert result["candidate_verification_audit"]["status"] == "failed"
    assert len(llm.calls) == 2
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace.get("proof_repair_count", 0) == 0
    assert trace.get("proof_rebuild_count", 0) == 0
    assert trace.get("proof_reaudit_count", 0) == 0
    assert trace["recovery_transitions"][-1]["outcome"] == "recovery_no_progress"
    repair_debug = trace["debug_trace"]["events"][0]["transaction"]["proof_repair"]
    assert repair_debug["kind"] == "stopped"
    assert repair_debug["initial_audit"]["attempts"][0]["raw_response"] == (
        _audit_with_false_premise_but_joint_entailment()
    )
    assert repair_debug["proof_reaudit"] == {}
