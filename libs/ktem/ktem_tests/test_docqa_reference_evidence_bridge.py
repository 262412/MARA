from ktem.docqa._runtime_mara import ResponseCapture
from ktem.docqa._runtime_models import DocQARequest


def test_response_capture_bridges_reference_text_when_evidence_items_are_missing():
    capture = ResponseCapture(
        DocQARequest(
            prompt="Summarize this source.",
            verification_mode="light",
        )
    )
    capture.ingest(
        "debug",
        {
            "mara_channel": "evidence_metadata",
            "payload": {"modalities": {"text": 1}},
        },
    )

    payload = capture.as_response_kwargs(
        answer="The proposal describes MARA as a document QA workbench.",
        references_text=(
            "The proposal describes MARA as a document QA workbench for mixed "
            "academic and technical documents."
        ),
    )

    assert payload["retrieve_decision"]["status"] == "good"
    assert payload["verify_decision"]["status"] == "supported"
    assert payload["evidence_bundle"]["items"][0]["evidence_level"] == "citation"
    assert payload["evidence_bundle"]["items"][0]["metadata"] == {
        "source": "references_html"
    }
    assert (
        payload["evidence_metadata"]["evidence"][0]["text"]
        == "The proposal describes MARA as a document QA workbench for mixed "
        "academic and technical documents."
    )


def test_response_capture_keeps_existing_evidence_when_reference_text_is_present():
    capture = ResponseCapture(DocQARequest(prompt="Summarize this source."))
    capture.ingest(
        "debug",
        {
            "mara_channel": "evidence_metadata",
            "payload": {
                "evidence": [
                    {
                        "evidence_id": "doc-1",
                        "text": "Existing retrieved evidence.",
                    }
                ]
            },
        },
    )

    payload = capture.as_response_kwargs(
        answer="Existing retrieved evidence.",
        references_text="Rendered citation refs.",
    )

    assert payload["evidence_metadata"]["evidence"] == [
        {"evidence_id": "doc-1", "text": "Existing retrieved evidence."}
    ]
    assert payload["evidence_bundle"]["items"][0]["evidence_id"] == "doc-1"


def test_response_capture_bridges_references_when_only_evidence_ids_exist():
    capture = ResponseCapture(DocQARequest(prompt="Summarize this source."))
    capture.ingest(
        "debug",
        {
            "mara_channel": "evidence_metadata",
            "payload": {"evidence_ids": ["doc-1"]},
        },
    )

    payload = capture.as_response_kwargs(
        answer="Rendered citation refs support this answer.",
        references_text="Rendered citation refs support this answer.",
    )

    assert payload["evidence_metadata"]["evidence_ids"] == ["doc-1"]
    assert payload["evidence_bundle"]["items"][0]["evidence_id"] == "citation-refs"


def test_response_capture_rebuilds_empty_execution_evidence_from_references():
    capture = ResponseCapture(
        DocQARequest(
            prompt="Summarize this source.",
            verification_mode="light",
        )
    )
    capture.ingest(
        "debug",
        {
            "mara_channel": "execution",
            "payload": {
                "controller_decision": {
                    "route": "text_rag",
                    "legacy_route": "doc_text",
                    "policy": "auto",
                    "controller_mode": "off",
                    "requires_retrieval": True,
                    "reason": "Default document text route.",
                },
                "route_decision": {
                    "route": "doc_text",
                    "policy": "auto",
                    "controller_mode": "off",
                    "requires_retrieval": True,
                    "reason": "Default document text route.",
                },
                "retrieve_decision": {
                    "status": "poor",
                    "reason": "No retrieved evidence was captured for this turn.",
                    "retry": True,
                },
                "verify_decision": {
                    "mode": "light",
                    "status": "not_enough_evidence",
                    "reason": "Light verification requested without sufficient evidence.",
                    "action": "retry",
                },
                "guardrail_decision": {
                    "status": "not_enough_evidence",
                    "action": "abstain",
                    "reason": "No retrieved evidence was captured for this turn.",
                },
                "evidence_bundle": {
                    "route": "doc_text",
                    "items": [],
                    "metadata": {"modalities": {"text": 1}},
                },
                "workflow_plan": {"route": "doc_text", "steps": []},
                "controller_trace": [],
            },
        },
    )

    payload = capture.as_response_kwargs(
        answer="The proposal describes MARA as a document QA workbench.",
        references_text=(
            "The proposal describes MARA as a document QA workbench for mixed "
            "academic and technical documents."
        ),
    )

    assert payload["retrieve_decision"]["status"] == "good"
    assert payload["verify_decision"]["status"] == "supported"
    assert payload["guardrail_decision"]["action"] == "return"
    assert payload["evidence_bundle"]["items"][0]["evidence_id"] == "citation-refs"


def test_response_capture_preserves_execution_evidence_items_with_references():
    capture = ResponseCapture(
        DocQARequest(
            prompt="Summarize this source.",
            verification_mode="light",
        )
    )
    capture.ingest(
        "debug",
        {
            "mara_channel": "execution",
            "payload": {
                "controller_decision": {
                    "route": "text_rag",
                    "legacy_route": "doc_text",
                },
                "route_decision": {"route": "doc_text"},
                "retrieve_decision": {"status": "good", "retry": False},
                "verify_decision": {
                    "mode": "light",
                    "status": "supported",
                    "action": "generate",
                },
                "guardrail_decision": {"status": "ok", "action": "return"},
                "evidence_bundle": {
                    "route": "doc_text",
                    "items": [
                        {
                            "evidence_id": "doc-1",
                            "modality": "text",
                            "text": "Existing execution evidence.",
                        }
                    ],
                    "metadata": {
                        "evidence": [
                            {
                                "evidence_id": "doc-1",
                                "modality": "text",
                                "text": "Existing execution evidence.",
                            }
                        ]
                    },
                },
            },
        },
    )

    payload = capture.as_response_kwargs(
        answer="Existing execution evidence.",
        references_text="Rendered citation refs.",
    )

    assert payload["evidence_bundle"]["items"] == [
        {
            "evidence_id": "doc-1",
            "modality": "text",
            "text": "Existing execution evidence.",
        }
    ]
    assert payload["retrieve_decision"] == {"status": "good", "retry": False}
