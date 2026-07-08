import ktem.reasoning.mara_route_retrieval as route_retrieval
from ktem.reasoning.mara import MaraAgentPipeline


def _page_record(page: int, text: str) -> dict:
    return {
        "evidence_id": f"page-image:file-b:{page}",
        "file_id": "file-b",
        "file_name": "visual.pdf",
        "page_label": str(page),
        "page_number": page,
        "page_image_path": f"/tmp/page-{page}.png",
        "rendered_page_image": f"/tmp/page-{page}.png",
        "late_interaction_tokens": text.split(),
        "multi_vector_representation": text.split(),
        "modality": "page_image",
        "text": text,
        "ocr_text": text,
        "source_backrefs": [f"file-b#page:{page}"],
        "metadata": {
            "visual_backend_type": "local_smoke",
            "late_interaction_tokens": text.split(),
        },
    }


def test_mara_page_image_route_caps_visual_scoring_candidates():
    class CountingVisualRetriever:
        name = "counting_visual_retriever"
        backend_type = "unit_test"

        def __init__(self):
            self.scored_ids = []

        def score(self, _query, record):
            self.scored_ids.append(record["evidence_id"])
            return 1.0 if "target" in str(record.get("text") or "") else 0.1

    records = [
        _page_record(
            page,
            (
                "target amortisation depreciation charges"
                if page == 6
                else f"background page {page}"
            ),
        )
        for page in range(1, 9)
    ]
    retriever = CountingVisualRetriever()
    pipeline = MaraAgentPipeline(retrievers=[])
    pipeline.page_image_index_records = records
    pipeline.page_image_rank_candidate_limit = 3
    pipeline.visual_retriever = retriever

    metadata = route_retrieval.route_retrieval_metadata(
        pipeline,
        "page_image_rag",
        "What is the target amortisation charge?",
        [],
        {
            "question": "What is the target amortisation charge?",
            "modalities": ["table"],
        },
        text_retrieve=lambda: (_ for _ in ()).throw(
            AssertionError("visual route must not use text retrieval")
        ),
        metadata_builder=lambda _docs, _understanding: {},
    )

    assert len(retriever.scored_ids) == 3
    assert "page-image:file-b:6" in retriever.scored_ids
    assert metadata["page_image_candidate_count"] == 8
    assert metadata["page_image_scored_candidate_count"] == 3
    assert metadata["page_image_candidate_selection"] == "lightweight_text_overlap_cap"
