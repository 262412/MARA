from __future__ import annotations

import json
from types import SimpleNamespace

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_semantic_proposition_verifier import (
    build_semantic_proposition_verifier,
)
from ktem_tests.test_mara_semantic_proposition_verifier import (
    QUESTION,
    _items,
    _RecordingLLM,
    _request,
)


def test_proposal_parse_failure_is_recorded_before_audit() -> None:
    llm = _RecordingLLM(
        json.dumps(
            {
                "candidate_judgment": "supported",
                "support_mode": "evidence_set",
                "jointly_complete": False,
                "each_premise_required": False,
                "premises": [],
            }
        )
    )
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=llm),
            semantic_proposition_debug_trace=True,
        )
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None

    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["status"] == "failed"
    assert trace["candidate_verification_status"] == "pre_audit_failed"
    assert trace["audit_status"] == "not_started"
    assert trace["audit_model_call_count"] == 0
    assert trace["candidate_verification_audit"]["status"] == "not_started"
    assert trace["candidate_verification_audit"]["classification"] == (
        "pre_audit_failed"
    )
    assert trace["explicit_contradiction"] is False
    assert trace["candidate_verifier_disagreement"] is False
    assert trace["unknown"] is False
    assert len(llm.calls) == 2
