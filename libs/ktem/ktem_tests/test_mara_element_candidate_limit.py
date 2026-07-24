import ktem.reasoning.mara_route_retrieval as route_retrieval
from ktem.reasoning.mara import MaraAgentPipeline


def test_mara_element_route_caps_candidates_before_evidence_normalization():
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.element_index_records = [
        {
            "evidence_id": f"element:file-b:{index}:text-{index}",
            "file_id": "file-b",
            "file_name": "report.pdf",
            "page_label": str(index),
            "element_id": f"text-{index}",
            "element_type": "text",
            "text": f"Revenue evidence row {index}.",
        }
        for index in range(40)
    ]

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "element_rag",
        "What does the revenue evidence show?",
        [],
        {
            "question": "What does the revenue evidence show?",
            "modalities": ["text"],
        },
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("element route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert len(metadata["element_index"]) == 20
    assert metadata["element_candidate_count"] == 40
    assert metadata["element_selected_candidate_count"] == 20
