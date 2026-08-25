from __future__ import annotations

import json

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.question_proposition import build_question_proposition, typed_conclusion
from ktem.reasoning.mara_semantic_entailment_audit import (
    semantic_entailment_audit_prompt,
)

from .test_mara_semantic_proposition_audit import (
    QUESTION,
    _audit,
    _items,
    _request,
    _response,
    _SequenceLLM,
    _proposal,
    _verifier,
)


def test_auditor_prompt_binds_original_candidate_judgment_and_polarity() -> None:
    proposition = build_question_proposition(QUESTION)
    conclusion = typed_conclusion(proposition, "yes")
    prompt = semantic_entailment_audit_prompt(
        proposition,
        conclusion,
        "atomic_semantic",
        [],
        original_candidate="yes",
        candidate_judgment="supported",
    )
    payload = json.loads(prompt.split("\n", 2)[-1])

    assert payload["original_candidate"] == "yes"
    assert payload["candidate_judgment"] == "supported"
    assert payload["typed_conclusion"]["polarity"] == "yes"
    assert "verifier_judgment" not in payload
    assert "verifier_verdict" not in payload


def test_audit_retry_cannot_turn_semantic_failure_into_pass() -> None:
    malformed_semantic_failure = json.loads(_audit(second_fragment_entailed=False))
    malformed_semantic_failure["format_only_noise"] = True
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response(json.dumps(malformed_semantic_failure)),
            _response(_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_reason"] == "audit_retry_semantic_identity_changed"
    assert len(llm.calls) == 3


def test_audit_retry_cannot_turn_unparseable_first_response_into_pass() -> None:
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response("not-json"),
            _response(_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_reason"] == "audit_retry_semantic_identity_changed"
    assert len(llm.calls) == 3


def test_audit_retry_cannot_remove_replacement_candidate_and_pass() -> None:
    replacement_attempt = json.loads(_audit())
    replacement_attempt["replacement_candidate_allowed"] = True
    replacement_attempt["replacement_candidate"] = "no"
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response(json.dumps(replacement_attempt)),
            _response(_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_reason"] == "audit_retry_semantic_identity_changed"


def test_audit_retry_allows_evidence_text_format_correction() -> None:
    malformed_format = json.loads(_audit())
    malformed_format["format_only_noise"] = True
    malformed_format["premise_checks"][0]["proposition_slot_checks"][0][
        "evidence_text"
    ] = "We "
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response(json.dumps(malformed_format)),
            _response(_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)
    assert result is not None
    assert result["verdict"] == "yes"
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_retry_count"] == 1
    assert len(llm.calls) == 3
