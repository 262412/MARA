import types

from ktem.docqa._runtime_mara import ResponseCapture


def test_response_capture_preserves_mara_execution_payload():
    request = types.SimpleNamespace(
        prompt="What is revenue?",
        controller_mode="llm",
        route_policy="doc",
        allowed_routes=["doc_text"],
        verification_mode="light",
    )
    capture = ResponseCapture(request)

    capture.ingest(
        "debug",
        {"mara_channel": "execution", "payload": _execution_payload()},
    )
    response_kwargs = capture.as_response_kwargs("10")

    assert response_kwargs["guardrail_decision"] == {
        "status": "ok",
        "action": "return",
        "reason": "Evidence observed.",
    }
    assert response_kwargs["retrieve_decision"]["status"] == "good"
    assert response_kwargs["evidence_bundle"]["items"][0]["evidence_id"] == "hit-1"
    assert response_kwargs["evidence_metadata"]["generation_backend"] == (
        "local_docqa_generator"
    )
    assert response_kwargs["backend_metadata"]["generator_backend"] == (
        "local_docqa_generator"
    )


def _execution_payload():
    return {
        "controller_decision": {
            "route": "text_rag",
            "legacy_route": "doc_text",
            "policy": "doc",
            "controller_mode": "llm",
            "requires_retrieval": True,
            "reason": "Requested document text route.",
        },
        "retrieve_decision": {
            "status": "good",
            "reason": "Retrieved evidence is sufficient for generation.",
            "retry": False,
        },
        "verify_decision": {
            "mode": "light",
            "status": "supported",
            "reason": "Evidence observed.",
            "action": "generate",
            "claims": [],
            "unsupported_claims": [],
            "verified_citations": ["doc#page:2"],
        },
        "guardrail_decision": {
            "status": "ok",
            "action": "return",
            "reason": "Evidence observed.",
        },
        "evidence_bundle": {
            "route": "doc_text",
            "items": [_evidence_item()],
            "metadata": {
                "evidence": [_evidence_item()],
                "generation_backend": "local_docqa_generator",
            },
        },
        "workflow_plan": {"route": "doc_text", "steps": []},
        "controller_trace": [{"stage": "guardrail", "action": "return"}],
        "answer": "10",
    }


def _evidence_item():
    return {
        "evidence_id": "hit-1",
        "source_id": "doc",
        "page_label": "2",
        "text": "Revenue was 10.",
    }
