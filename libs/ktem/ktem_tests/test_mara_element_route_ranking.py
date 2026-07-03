from types import SimpleNamespace

import ktem.reasoning.mara_route_retrieval as route_retrieval
from ktem.reasoning.mara import MaraAgentPipeline
from ktem.reasoning.mara_element_answer import element_evidence_answer


def test_mara_element_route_uses_request_page_hint_for_ranking():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.docqa_request = SimpleNamespace(page_number=64)
    pipeline.element_index_records = [
        {
            "evidence_id": "element:file-b:444:training",
            "file_id": "file-b",
            "file_name": "tables.pdf",
            "page_label": "444",
            "element_id": "training",
            "element_type": "table",
            "modality": "table",
            "caption": "Depreciation training policy",
            "text": "Training policy uses depreciation charge terminology repeatedly.",
            "source_backrefs": ["file-b#page:444"],
        },
        {
            "evidence_id": "element:file-b:64:answer",
            "file_id": "file-b",
            "file_name": "tables.pdf",
            "page_label": "64",
            "element_id": "answer",
            "element_type": "table",
            "modality": "table",
            "caption": "Depreciation charge",
            "text": "Depreciation charge was 246 million.",
            "source_backrefs": ["file-b#page:64"],
        },
    ]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "What was the depreciation charge?",
        [],
        {"question": "What was the depreciation charge?", "modalities": ["table"]},
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert metadata["element_index"][0]["element_id"] == "answer"
    assert metadata["element_index"][0]["metadata"]["element_retriever_page_hint_match"]


def test_mara_element_answer_uses_text_element_evidence_concisely():
    bundle = SimpleNamespace(
        items=[
            {
                "modality": "text",
                "element_id": "text-64-1",
                "text": (
                    "Introductory governance paragraph. "
                    "Depreciation charge was 246 million in 2021. "
                    "Unrelated closing paragraph that should not dominate."
                ),
            },
            {
                "modality": "table",
                "element_id": "table-444-1",
                "text": "Training policy text.",
            },
        ]
    )

    answer = element_evidence_answer(bundle, prompt="What was the depreciation charge?")

    assert "Depreciation charge was 246 million" in answer
    assert "Training policy text" not in answer
    assert len(answer) < 180
