from copy import deepcopy
from pathlib import Path

from ktem.docqa._runtime_mara import ResponseCapture
from ktem.docqa._runtime_models import DocQARequest, DocQAResponse
from ktem.docqa._runtime_turn import create_stream_result, finalize_stream_result
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.execution import GuardrailDecision, _result
from ktem.docqa.route_selection import ControllerDecision
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
