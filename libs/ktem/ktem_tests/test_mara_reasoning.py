from ktem.reasoning.mara import MARA_ABSTAIN_MESSAGE, MaraAgentPipeline
from ktem.reasoning.mara_controller import planner_decision
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


def test_mara_planner_decision_routes_global_compare_to_graph():
    decision = planner_decision(
        {"task_type": "compare", "modalities": ["text"], "scope": "document"}
    )

    assert decision == {
        "route": "graph_global",
        "reason": "Global compare and study tasks use graph evidence.",
        "evidence_types": ["graph"],
        "verify": True,
    }


def test_mara_planner_decision_routes_visual_question_to_hybrid_evidence():
    decision = planner_decision(
        {"task_type": "qa", "modalities": ["figure"], "scope": "page"}
    )

    assert decision["route"] == "hybrid"
    assert decision["evidence_types"] == ["text", "page_image", "element"]


def test_mara_planner_decision_routes_table_question_to_hybrid_evidence():
    decision = planner_decision(
        {"task_type": "qa", "modalities": ["table"], "scope": "document"}
    )

    assert decision["route"] == "hybrid"
    assert decision["evidence_types"] == ["text", "page_image", "element"]


def test_mara_pipeline_reads_agent_mode_from_settings():
    pipeline = MaraAgentPipeline.prepare_pipeline_instance(
        {"reasoning.options.mara.agent_mode": "thorough"},
        retrievers=[],
    )

    assert pipeline.agent_mode == "thorough"


def _sample_multimodal_docs():
    return [
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


def _expected_table_evidence():
    return {
        "evidence_id": "doc-1",
        "file_id": "file-1",
        "file_name": "report.pdf",
        "page_label": "3",
        "element_type": "table",
        "element_id": "table-7",
        "bbox": [1, 2, 3, 4],
        "caption": "Revenue table",
        "text": "Table evidence",
        "ocr_text": "Revenue FY2026",
        "table_origin": "camelot",
        "formula_normalized": "",
        "slide_number": None,
        "retrieval_path": "hybrid",
        "source_backrefs": ["file-1#page:3"],
    }


def test_mara_evidence_metadata_tracks_modalities_sources_and_pages():
    metadata = MaraAgentPipeline.build_evidence_metadata(
        _sample_multimodal_docs(),
        {"modalities": ["table", "figure"]},
    )

    assert metadata["requested_modalities"] == ["table", "figure"]
    assert metadata["modality_counts"] == {"table": 1, "figure": 1}
    assert metadata["page_coverage"] == ["3", "4"]
    assert metadata["source_ids"] == ["file-1"]
    assert metadata["evidence_ids"] == ["doc-1", "doc-2"]
    assert metadata["evidence"][0] == _expected_table_evidence()
    assert metadata["evidence"][1]["element_type"] == "figure"
    assert metadata["evidence"][1]["source_backrefs"] == ["file-1#page:4"]
    assert metadata["element_index"][0]["evidence_id"] == ("element:file-1:3:table-7")


def test_mara_evidence_metadata_includes_text_for_verifier_support():
    docs = [
        RetrievedDocument(
            text="Revenue increased in 2026.",
            id_="doc-1",
            metadata={"file_id": "file-1", "page_label": "3"},
        )
    ]

    metadata = MaraAgentPipeline.build_evidence_metadata(
        docs,
        {"modalities": ["text"]},
    )

    assert metadata["evidence"][0]["text"] == "Revenue increased in 2026."


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


def test_mara_new_studio_artifact_types_are_generated_from_evidence():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.artifact_type = "data_table"
    pipeline._mara_last_docs = [
        RetrievedDocument(
            text="Evaluation compares MARA fast and thorough modes.",
            id_="table-evidence",
            metadata={
                "file_id": "deck-1",
                "file_name": "thesis.pptx",
                "page_label": "7",
            },
        )
    ]

    artifact = pipeline.build_artifact({"task_type": "qa", "modalities": ["text"]})

    assert artifact is not None
    assert artifact["type"] == "data_table"
    assert artifact["rows"] == [
        ["thesis.pptx", "7", "Evaluation compares MARA fast and thorough modes."]
    ]
    assert artifact["row_citations"] == [
        {"row": 0, "citation_refs": ["table-evidence"], "source_ids": ["deck-1"]}
    ]


def test_mara_media_artifact_generates_script_plan_without_adapter():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.artifact_type = "audio_overview"
    pipeline._mara_last_docs = [
        RetrievedDocument(
            text="Verifier checks answer support before final response.",
            id_="audio-evidence",
            metadata={"file_id": "file-2", "file_name": "agent.md"},
        )
    ]

    artifact = pipeline.build_artifact({"task_type": "qa", "modalities": ["text"]})

    assert artifact is not None
    assert artifact["type"] == "audio_overview"
    assert artifact["media_status"] == "script_only"
    assert artifact["script"][0]["text"] == (
        "Verifier checks answer support before final response."
    )


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
    assert any(
        event.get("event") == "retrieval_evaluator" and event.get("status") == "poor"
        for event in trace_payloads
    )
    assert any(
        event.get("event") == "guardrail" and event.get("action") == "abstain"
        for event in trace_payloads
    )


def test_mara_stream_emits_planner_output_for_controller_trace(monkeypatch):
    def fake_stream(_self, _message, _conv_id, _history, **_kwargs):
        yield Document(channel="chat", content="grounded answer")
        return Document(channel="chat", content="grounded answer")

    monkeypatch.setattr(FullQAPipeline, "stream", fake_stream)
    pipeline = MaraAgentPipeline(retrievers=[])

    events = list(pipeline.stream("Compare the source themes.", "conv-1", []))
    trace_payloads = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "agent_trace"
    ]

    assert {
        "event": "planner_output",
        "decision": {
            "route": "graph_global",
            "reason": "Global compare and study tasks use graph evidence.",
            "evidence_types": ["graph"],
            "verify": True,
        },
    } in trace_payloads


def test_mara_graph_route_uses_graph_context_without_text_rag(monkeypatch):
    def fail_if_text_rag_runs(_self, _message, _conv_id, _history, **_kwargs):
        raise AssertionError("Graph route should not call the text RAG chain")
        yield

    monkeypatch.setattr(FullQAPipeline, "stream", fail_if_text_rag_runs)
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.graph_context = {
        "node_id": "component::strategy",
        "label": "Strategy",
        "summary": "Strategy connects pricing and product roadmap themes.",
        "support_pages": {"file-a": ["2"], "file-b": ["5"]},
        "support_chunk_ids": {"file-a": ["chunk-a"], "file-b": ["chunk-b"]},
    }

    events = list(pipeline.stream("Compare the source themes.", "conv-1", []))

    assert [event.content for event in events if event.channel == "chat"] == [
        "Strategy connects pricing and product roadmap themes."
    ]
    evidence_payloads = [
        event.content["payload"]
        for event in events
        if event.channel == "debug"
        and event.content.get("mara_channel") == "evidence_metadata"
    ]
    assert len(evidence_payloads) == 1
    metadata = evidence_payloads[0]
    assert metadata["requested_modalities"] == ["text"]
    assert metadata["modality_counts"] == {"graph": 1}
    assert metadata["page_coverage"] == ["2", "5"]
    assert metadata["source_ids"] == ["file-a", "file-b"]
    assert metadata["evidence_ids"] == ["graph:component::strategy"]
    assert metadata["graph_evidence"] == [
        {
            "evidence_id": "graph:component::strategy",
            "id": "component::strategy",
            "label": "Strategy",
            "summary": "Strategy connects pricing and product roadmap themes.",
            "source_ids": ["file-a", "file-b"],
            "support_pages": {"file-a": ["2"], "file-b": ["5"]},
            "support_chunk_ids": {
                "file-a": ["chunk-a"],
                "file-b": ["chunk-b"],
            },
        }
    ]
    assert metadata["evidence"][0]["evidence_id"] == "graph:component::strategy"
