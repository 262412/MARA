from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_semantic_proposition_verifier import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    build_semantic_proposition_verifier,
)

from .test_mara_semantic_proposition_audit import (
    QUESTION,
    _atomic_audit,
    _atomic_proposal,
    _atomic_request,
    _audit,
    _insufficient_proposal,
    _items,
    _proposal,
    _request,
    _response,
    _SequenceLLM,
    _unknown_audit,
    _verifier,
)


def test_runtime_retries_one_malformed_proposal_then_audits_it() -> None:
    llm = _SequenceLLM(
        [
            _response("{", completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS),
            _response(_proposal()),
            _response(_audit()),
        ]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None and result["verdict"] == "yes"
    assert len(llm.calls) == 3
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["proposal_retry_count"] == 1
    assert trace["initial_parse_failure_reason"] == "json_decode_error"


def test_runtime_classifies_exhausted_output_without_recording_response_text() -> None:
    llm = _SequenceLLM(
        [
            _response(
                "{",
                completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                finish_reason="length",
            ),
            _response(
                "{",
                completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                finish_reason="length",
            ),
        ]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None

    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["reason"] == "provider_output_truncated"
    assert trace["parse_failure_reason"] == "json_decode_error"
    assert trace["response_finish_reason"] == "length"
    assert trace["response_completion_tokens"] == (
        SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS
    )
    assert trace["response_chars"] == 1
    assert "response_text" not in trace
    assert "debug_trace" not in trace


def test_debug_trace_records_proposal_and_audit_without_changing_result() -> None:
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "yes"
    debug = bundle.metadata["semantic_proposition_verifier"]["debug_trace"]
    assert debug["contract_id"] == "semantic_proposition_debug_trace.v3"
    [event] = debug["events"]
    assert event["event"] == "model_transaction"
    assert event["auditor_relationship"] == "same_instance"
    proposal_attempt = event["transaction"]["proposal"]["attempts"][0]
    audit_attempt = event["transaction"]["audit"]["attempts"][0]
    assert proposal_attempt["raw_response"] == _proposal()
    assert proposal_attempt["parsed_value"]["verdict"] == "yes"
    assert audit_attempt["raw_response"] == _audit()
    assert audit_attempt["parsed_value"]["jointly_entails"] is True


def test_debug_trace_preserves_cache_reuse_after_a_rejected_audit() -> None:
    llm = _SequenceLLM(
        [
            _response(_proposal()),
            _response(_audit(second_fragment_entailed=False)),
            _response(_insufficient_proposal()),
            _response(_unknown_audit()),
        ]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    first = verifier(_request(), QUESTION, "yes", bundle)
    second = verifier(_request(), QUESTION, "yes", bundle)

    assert first == second
    debug = bundle.metadata["semantic_proposition_verifier"]["debug_trace"]
    assert [event["event"] for event in debug["events"]] == [
        "model_transaction",
        "cache_reuse",
    ]
    assert debug["events"][0]["outcome"]["audit_status"] == "rejected"
    assert debug["events"][1]["source_event_index"] == 1
    assert debug["events"][1]["cached_outcome"]["audit_status"] == "rejected"


def test_debug_trace_can_be_enabled_by_the_slurm_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE", "1")
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    verifier(_request(), QUESTION, "unanswerable", bundle)

    debug = bundle.metadata["semantic_proposition_verifier"]["debug_trace"]
    assert debug["contract_id"] == "semantic_proposition_debug_trace.v3"


def test_canonical_sentence_span_selector_preserves_exact_quote_and_offsets() -> None:
    source_text = (
        "Lead-in context. We evaluated transfer across two languages. "
        "Trailing context."
    )
    target_quote = "We evaluated transfer across two languages."
    local_start = source_text.index(target_quote)
    canonical_start = 240
    item = {
        "evidence_id": "canonical-span-source",
        "source_id": "paper",
        "section_id": "experiments",
        "canonical_start": canonical_start,
        "text": source_text,
    }
    llm = _SequenceLLM(
        [_response(_atomic_proposal(selector="E1:S2")), _response(_atomic_audit())]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=[item])

    result = verifier(
        _atomic_request(),
        "Did the authors evaluate transfer across languages?",
        "yes",
        bundle,
    )

    assert result is not None
    [premise] = result["premises"]
    assert premise["quote"] == target_quote
    assert premise["span_start"] == local_start
    assert premise["span_end"] == local_start + len(target_quote)
    assert premise["canonical_start"] == canonical_start + local_start
    assert premise["canonical_end"] == canonical_start + local_start + len(target_quote)
