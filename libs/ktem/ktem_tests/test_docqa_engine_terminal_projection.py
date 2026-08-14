import hashlib
import json
from copy import deepcopy
from pathlib import Path

from ktem.docqa._runtime_mara import ResponseCapture
from ktem.docqa._runtime_models import DocQARequest, DocQAResponse
from ktem.docqa._runtime_turn import create_stream_result, finalize_stream_result
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.execution import ABSTAIN_MESSAGE, GuardrailDecision, _result
from ktem.docqa.route_selection import ControllerDecision
from ktem.docqa.terminal_session_state import (
    terminal_semantic_commit_for_message,
    with_terminal_semantic_commit,
)
from ktem.docqa.verification import VerifyDecision

from benchmark.engine_result import EngineRunResult
from benchmark.engine_result_adapters import prediction_to_result
from benchmark.runner import _engine_result_to_prediction
from benchmark.schemas import BenchmarkDocument, BenchmarkExample


def _execution_result():
    request = DocQARequest(prompt="Does the source support this claim?")
    decision = ControllerDecision(
        route="doc_text",
        legacy_route="doc_text",
        policy="document",
        controller_mode="heuristic",
        requires_retrieval=True,
        reason="test route",
    )
    retrieve = RetrieveDecision("good", "evidence found")
    verify = VerifyDecision(
        mode="strict",
        status="supported",
        reason="claim supported",
        verified_citations=["evidence-1"],
    )
    bundle = EvidenceBundle(
        route="doc_text",
        items=[{"evidence_id": "evidence-1", "text": "The source supports this."}],
    )
    return _result(
        request,
        decision,
        retrieve,
        verify,
        GuardrailDecision("ok", "return", "verified"),
        bundle,
        {"route": "doc_text"},
        "yes",
    )


def test_execution_terminal_projection_is_deep_copied_and_self_consistent():
    result = _execution_result()
    payload = result.as_dict()

    assert payload["engine_terminal_answer"] == "yes"
    assert payload["engine_verify_decision"] == result.verify_decision.as_dict()
    assert payload["engine_terminal_state"]["answer"] == "yes"
    assert payload["engine_terminal_state"]["raw_generated_answer"] == "yes"
    assert payload["engine_terminal_state"]["normalized_candidate_label"] == "yes"
    assert payload["engine_terminal_state"]["verified_canonical_answer"] == ""
    assert payload["engine_terminal_state"]["semantic_correction_applied"] is False
    assert payload["engine_terminal_state"]["correction_reason"] == ""
    assert payload["engine_terminal_state"]["authoritative_evidence_id"] == ""
    assert payload["engine_terminal_state"]["authoritative_evidence_ref"] == ""
    assert payload["engine_terminal_state"]["authoritative_quote"] == ""
    assert payload["engine_terminal_state"]["guardrail_result"] == {
        "status": "ok",
        "action": "return",
        "reason": "verified",
    }
    assert (
        payload["engine_terminal_state"]["verify_decision"]
        == payload["engine_verify_decision"]
    )
    assert (
        payload["engine_terminal_state"]["evidence_bundle"]
        == payload["engine_terminal_evidence_bundle"]
    )

    payload["engine_terminal_state"]["verify_decision"]["status"] = "unknown"
    payload["engine_terminal_evidence_bundle"]["metadata"]["mutated"] = True
    fresh = result.as_dict()
    assert fresh["engine_terminal_state"]["verify_decision"]["status"] == "supported"
    assert "mutated" not in fresh["engine_terminal_evidence_bundle"]["metadata"]


def test_engine_terminal_hash_covers_normalized_label_and_guardrail_result():
    payload = _execution_result().as_dict()
    state = payload["engine_terminal_state"]
    expected = hashlib.sha256(
        json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()

    assert payload["engine_terminal_projection_hash"] == expected

    state["normalized_candidate_label"] = "no"
    tampered = hashlib.sha256(
        json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    assert tampered != expected


def test_terminal_projection_preserves_an_empty_raw_generation() -> None:
    request = DocQARequest(prompt="Does the source support this claim?")
    result = _result(
        request,
        ControllerDecision(
            route="doc_text",
            legacy_route="doc_text",
            policy="document",
            controller_mode="heuristic",
            requires_retrieval=True,
            reason="test route",
        ),
        RetrieveDecision("good", "evidence found"),
        VerifyDecision(
            mode="strict",
            status="not_enough_evidence",
            reason="No generated answer was available.",
            action="abstain",
        ),
        GuardrailDecision("not_enough_evidence", "abstain", "empty answer"),
        EvidenceBundle(route="doc_text"),
        {"route": "doc_text"},
        ABSTAIN_MESSAGE,
        raw_generated_answer="",
    )

    payload = result.as_dict()
    assert payload["engine_terminal_state"]["raw_generated_answer"] == ""
    assert result.answer == ABSTAIN_MESSAGE
    assert payload["engine_terminal_answer"] == "unanswerable"
    assert payload["engine_terminal_state"]["answer"] == "unanswerable"
    assert payload["engine_terminal_commit"]["semantic_answer"] == "unanswerable"
    assert payload["engine_terminal_commit"]["answer_status"] == "abstained"


def test_stream_finalization_preserves_safe_abstention_presentation() -> None:
    request = DocQARequest(prompt="Which inputs does the method rely on?")
    execution = _result(
        request,
        ControllerDecision(
            route="doc_text",
            legacy_route="doc_text",
            policy="document",
            controller_mode="heuristic",
            requires_retrieval=True,
            reason="test route",
        ),
        RetrieveDecision("good", "evidence found"),
        VerifyDecision(
            mode="strict",
            status="unknown",
            reason="Claim support is unknown.",
            action="abstain",
        ),
        GuardrailDecision("unknown", "abstain", "Claim support is unknown."),
        EvidenceBundle(route="doc_text"),
        {"route": "doc_text"},
        ABSTAIN_MESSAGE,
        raw_generated_answer="unsupported answer",
    ).as_dict()
    result = create_stream_result(request)
    result.text = "unsupported answer"
    result.capture.ingest("execution", execution)

    finalize_stream_result(result, "empty")

    assert execution["engine_terminal_answer"] == "unanswerable"
    assert result.text == ABSTAIN_MESSAGE
    assert execution["engine_terminal_commit"]["semantic_answer"] == "unanswerable"
    assert execution["engine_terminal_commit"]["presentation_answer"] == (
        ABSTAIN_MESSAGE
    )


def test_response_capture_preserves_terminal_projection_without_rebuilding():
    execution = _execution_result().as_dict()
    capture = ResponseCapture(DocQARequest(prompt="Question"))
    capture.ingest("execution", execution)
    payload = capture.as_response_kwargs(answer="post-stream answer")

    assert payload["engine_terminal_answer"] == "yes"
    assert payload["engine_terminal_state"] == execution["engine_terminal_state"]
    assert payload["engine_verify_decision"] == execution["engine_verify_decision"]
    payload["engine_terminal_state"]["answer"] = "mutated"
    assert execution["engine_terminal_state"]["answer"] == "yes"


def test_stream_finalization_uses_captured_engine_terminal_answer():
    execution = _execution_result().as_dict()
    result = create_stream_result(DocQARequest(prompt="Question"))
    result.text = "yesyes"
    result.capture.ingest("execution", execution)

    finalize_stream_result(result, "empty")

    assert result.text == "yes"


def test_docqa_response_schema_exposes_terminal_projection_fields():
    response = DocQAResponse(
        conversation_id="conversation-1",
        answer="yes",
        references_html="",
        references_text="",
        mindmap_html="",
        plot=None,
        messages=[],
        retrieval_messages=[],
        plot_history=[],
        state={},
        selected_file_ids=[],
        selected_mapping={},
        graph_source_ids=[],
        active_file_id="",
        active_file_name="",
        qa_scope="document",
        page_number=None,
        selected_text="",
        graph_context={},
        reasoning_id="mara",
        settings={},
        stream_events=[],
        engine_terminal_answer="yes",
        engine_terminal_state={"answer": "yes"},
        engine_verify_decision={"status": "supported"},
    )

    payload = response.as_dict()
    assert payload["engine_terminal_answer"] == "yes"
    assert payload["engine_terminal_state"] == {"answer": "yes"}
    assert payload["engine_verify_decision"] == {"status": "supported"}


def test_session_state_persists_immutable_commit_separately_from_presentation() -> None:
    execution = _execution_result().as_dict()
    commit = execution["engine_terminal_commit"]

    state = with_terminal_semantic_commit(
        {"app": {"regen": False}},
        message_index=3,
        commit=commit,
    )
    commit["semantic_answer"] = "mutated outside session state"

    persisted = terminal_semantic_commit_for_message(state, 3)
    assert persisted["semantic_answer"] == "yes"
    assert persisted["presentation_answer"] == "yes"
    assert state["app"] == {"regen": False}


def test_benchmark_prediction_roundtrip_preserves_terminal_projection():
    terminal_state = {
        "contract_id": "engine_terminal_state.v1",
        "answer": "yes",
        "verify_decision": {"status": "supported"},
    }
    result = EngineRunResult(
        answer="post-engine presentation",
        engine_terminal_answer="yes",
        engine_terminal_state=deepcopy(terminal_state),
        engine_verify_decision={"status": "supported"},
        engine_terminal_guardrail_decision={"action": "return"},
        engine_terminal_evidence_bundle={"items": [{"evidence_id": "e1"}]},
        engine_terminal_projection_hash="hash",
    )
    example = BenchmarkExample(
        example_id="example-1",
        document_id="document-1",
        question="Question",
        answers=["yes"],
    )
    document = BenchmarkDocument(
        document_id="document-1",
        path=Path("document.txt"),
        format_type="text",
    )

    prediction = _engine_result_to_prediction(
        result,
        example=example,
        documents=[document],
    )
    assert prediction["engine_terminal_state"] == terminal_state
    assert prediction["engine_verify_decision"] == {"status": "supported"}

    roundtrip = prediction_to_result(prediction)
    assert roundtrip.engine_terminal_answer == "yes"
    assert roundtrip.engine_terminal_state == terminal_state
    assert roundtrip.engine_verify_decision == {"status": "supported"}
    assert roundtrip.engine_terminal_projection_hash == "hash"
