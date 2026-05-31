from ktem.reasoning.mara import MARA_ABSTAIN_MESSAGE, MaraAgentPipeline
from ktem.reasoning.simple import FullQAPipeline

from kotaemon.base import Document, RetrievedDocument


def test_mara_reasoning_info_is_public_product_name():
    assert MaraAgentPipeline.get_info() == {
        "id": "mara",
        "name": "MARA Agentic Multimodal QA",
        "description": (
            "Routes each DocQA request through MARA query understanding, "
            "modality-aware planning, evidence retrieval, and verification."
        ),
    }


def test_mara_query_understanding_classifies_task_and_modalities():
    understanding = MaraAgentPipeline.understand_query(
        "Compare the table on page 3 with the figure in slide 5"
    )

    assert understanding["task_type"] == "compare"
    assert understanding["modalities"] == ["table", "figure", "slide"]
    assert understanding["scope"] == "page"


def test_mara_planner_keeps_fast_mode_to_one_retrieval_step():
    understanding = {
        "task_type": "qa",
        "modalities": ["text"],
        "scope": "document",
    }

    plan = MaraAgentPipeline.plan_steps(understanding, agent_mode="fast")

    assert plan == [
        {
            "tool": "source_retriever",
            "purpose": "Retrieve text evidence for document-scoped qa.",
        }
    ]


def test_mara_pipeline_reads_agent_mode_from_settings():
    pipeline = MaraAgentPipeline.prepare_pipeline_instance(
        {"reasoning.options.mara.agent_mode": "thorough"},
        retrievers=[],
    )

    assert pipeline.agent_mode == "thorough"


def test_mara_evidence_metadata_tracks_modalities_sources_and_pages():
    docs = [
        RetrievedDocument(
            text="Table evidence",
            id_="doc-1",
            metadata={
                "element_type": "table",
                "element_id": "table-7",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "3",
                "bbox": [1, 2, 3, 4],
                "caption": "Revenue table",
                "ocr_text": "Revenue FY2026",
                "table_origin": "camelot",
                "retrieval_path": "hybrid",
            },
        ),
        RetrievedDocument(
            text="Figure evidence",
            id_="doc-2",
            metadata={
                "element_type": "figure",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "formula_normalized": "x^2",
                "slide_number": 5,
            },
        ),
    ]

    metadata = MaraAgentPipeline.build_evidence_metadata(
        docs,
        {"modalities": ["table", "figure"]},
    )

    assert metadata == {
        "requested_modalities": ["table", "figure"],
        "modality_counts": {"table": 1, "figure": 1},
        "page_coverage": ["3", "4"],
        "source_ids": ["file-1"],
        "evidence_ids": ["doc-1", "doc-2"],
        "evidence": [
            {
                "evidence_id": "doc-1",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "3",
                "element_type": "table",
                "element_id": "table-7",
                "bbox": [1, 2, 3, 4],
                "caption": "Revenue table",
                "ocr_text": "Revenue FY2026",
                "table_origin": "camelot",
                "formula_normalized": "",
                "slide_number": None,
                "retrieval_path": "hybrid",
            },
            {
                "evidence_id": "doc-2",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "element_type": "figure",
                "element_id": "",
                "bbox": None,
                "caption": "",
                "ocr_text": "",
                "table_origin": "",
                "formula_normalized": "x^2",
                "slide_number": 5,
                "retrieval_path": "",
            },
        ],
    }


def test_mara_study_guide_artifact_contains_source_grounded_sections():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.artifact_type = "study_guide"
    pipeline._mara_last_docs = [
        RetrievedDocument(
            text="MARA retrieves table evidence and verifies claims before answering.",
            id_="evidence-1",
            metadata={
                "file_id": "file-1",
                "file_name": "paper.pdf",
                "page_label": "4",
                "element_type": "table",
            },
        )
    ]

    artifact = pipeline.build_artifact({"task_type": "qa", "modalities": ["table"]})

    assert artifact is not None
    assert artifact["type"] == "study_guide"
    assert artifact["status"] == "ready"
    assert artifact["overview"].startswith("MARA retrieves table evidence")
    assert artifact["key_concepts"] == ["paper.pdf p.4"]
    assert artifact["key_questions"] == ["What does paper.pdf p.4 show about MARA?"]
    assert artifact["cited_evidence"][0] == {
        "evidence_id": "evidence-1",
        "file_id": "file-1",
        "file_name": "paper.pdf",
        "page_label": "4",
        "excerpt": "MARA retrieves table evidence and verifies claims before answering.",
    }


def test_mara_quiz_artifact_uses_evidence_for_answers_and_explanations():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.artifact_type = ""
    pipeline._mara_last_docs = [
        RetrievedDocument(
            text="Claim verification reduces unsupported answers.",
            id_="evidence-2",
            metadata={"file_id": "file-2", "file_name": "notes.md"},
        )
    ]

    artifact = pipeline.build_artifact({"task_type": "quiz", "modalities": ["text"]})

    assert artifact is not None
    assert artifact["type"] == "quiz"
    assert artifact["multiple_choice"][0]["source_ids"] == ["file-2"]
    assert artifact["answer_key"][0]["explanation"] == (
        "Claim verification reduces unsupported answers."
    )
    assert artifact["short_answer"][0]["answer"] == (
        "Claim verification reduces unsupported answers."
    )


def test_mara_flashcards_artifact_preserves_source_links():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.artifact_type = "flashcards"
    pipeline._mara_last_docs = [
        RetrievedDocument(
            text="A modality router chooses table evidence for table questions.",
            id_="evidence-3",
            metadata={"file_id": "file-3", "file_name": "routing.pdf"},
        )
    ]

    artifact = pipeline.build_artifact({"task_type": "qa", "modalities": ["table"]})

    assert artifact is not None
    assert artifact["type"] == "flashcards"
    assert artifact["cards"] == [
        {
            "front": "What is the key point from routing.pdf?",
            "back": "A modality router chooses table evidence for table questions.",
            "source_ids": ["file-3"],
        }
    ]
    assert artifact["cited_evidence"][0]["evidence_id"] == "evidence-3"


def test_mara_mindmap_artifact_traces_nodes_to_sources():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.artifact_type = "mindmap"
    pipeline._mara_last_docs = [
        RetrievedDocument(
            text="Planner routes through retrieval and verification.",
            id_="planner",
            metadata={"file_id": "file-1", "file_name": "agent.md"},
        ),
        RetrievedDocument(
            text="Verifier checks answer support before final response.",
            id_="verifier",
            metadata={"file_id": "file-2", "file_name": "agent.md"},
        ),
    ]

    artifact = pipeline.build_artifact({"task_type": "mindmap", "modalities": ["text"]})

    assert artifact is not None
    assert artifact["type"] == "mindmap"
    assert artifact["nodes"][0] == {
        "id": "planner",
        "label": "agent.md",
        "summary": "Planner routes through retrieval and verification.",
        "source_ids": ["file-1"],
    }
    assert artifact["edges"] == [{"source": "planner", "target": "verifier"}]


def test_mara_slide_outline_artifact_builds_evidence_backed_slides():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.artifact_type = "slide_outline"
    pipeline._mara_last_docs = [
        RetrievedDocument(
            text="Evaluation compares MARA fast and thorough modes.",
            id_="slide-evidence",
            metadata={
                "file_id": "deck-1",
                "file_name": "thesis.pptx",
                "page_label": "7",
            },
        )
    ]

    artifact = pipeline.build_artifact(
        {"task_type": "slide_outline", "modalities": ["slide"]}
    )

    assert artifact is not None
    assert artifact["type"] == "slide_outline"
    assert artifact["title"] == "Source-grounded MARA outline"
    assert artifact["sections"][0]["slides"] == [
        {
            "title": "thesis.pptx p.7",
            "bullets": ["Evaluation compares MARA fast and thorough modes."],
            "source_ids": ["deck-1"],
        }
    ]


def test_mara_thorough_mode_retries_once_when_first_retrieval_has_no_evidence(
    monkeypatch,
):
    calls = []
    retry_doc = RetrievedDocument(
        text="Recovered evidence",
        id_="retry-doc",
        metadata={"file_id": "file-1", "page_label": "2"},
    )

    def fake_retrieve(_self, message, history):
        calls.append((message, history))
        if len(calls) == 1:
            return [], []
        return [retry_doc], [Document(channel="info", content="Recovered evidence")]

    monkeypatch.setattr(FullQAPipeline, "retrieve", fake_retrieve)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.agent_mode = "thorough"

    docs, info = pipeline.retrieve("What changed?", [("Earlier", "Context")])

    assert docs == [retry_doc]
    assert [(item.channel, item.content) for item in info] == [
        ("info", "Recovered evidence")
    ]
    assert len(calls) == 2
    assert pipeline._mara_retrieval_attempts == [
        {"attempt": 1, "evidence_count": 0, "retry_reason": ""},
        {"attempt": 2, "evidence_count": 1, "retry_reason": "insufficient_evidence"},
    ]


def test_mara_thorough_mode_abstains_when_retry_still_has_no_evidence(monkeypatch):
    calls = []

    def fake_retrieve(_self, message, history):
        calls.append((message, history))
        return [], []

    def fail_if_answering_chain_runs(_self, _message, _conv_id, _history, **_kwargs):
        raise AssertionError("MARA should abstain before unsupported answer generation")
        yield

    monkeypatch.setattr(FullQAPipeline, "retrieve", fake_retrieve)
    monkeypatch.setattr(FullQAPipeline, "stream", fail_if_answering_chain_runs)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.agent_mode = "thorough"

    events = list(pipeline.stream("Unsupported claim?", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        MARA_ABSTAIN_MESSAGE
    ]
    assert len(calls) == 2
    trace_payloads = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "agent_trace"
    ]
    assert {
        "event": "verify",
        "result": "insufficient",
        "evidence_count": 0,
        "decision": "abstain",
    } in trace_payloads
