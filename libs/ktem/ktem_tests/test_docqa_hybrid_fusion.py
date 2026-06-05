from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle


def test_hybrid_route_uses_weighted_cross_modal_fusion_scores():
    request = DocQARequest(
        prompt="Explain the revenue chart and table.",
        route_policy="hybrid",
        selected_file_ids=["file-b"],
    )
    metadata = {
        "evidence": [
            {
                "evidence_id": "text-b",
                "file_id": "file-b",
                "file_name": "results.pdf",
                "page_label": "5",
                "text": "Revenue chart and table summarize growth.",
            }
        ],
        "page_image_index": [
            {
                "evidence_id": "page-image:file-b:5",
                "file_id": "file-b",
                "file_name": "results.pdf",
                "page_label": "5",
                "modality": "page_image",
                "text": "Revenue chart visual.",
            }
        ],
        "visual_retriever_scores": {"page-image:file-b:5": 0.95},
        "element_index": [
            {
                "evidence_id": "element:file-b:5:table-a",
                "file_id": "file-b",
                "file_name": "results.pdf",
                "page_label": "5",
                "element_id": "table-a",
                "modality": "table",
                "caption": "Revenue table",
            }
        ],
        "element_retriever_scores": {"element:file-b:5:table-a": 0.4},
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert bundle.items[0]["evidence_id"] == "page-image:file-b:5"
    assert bundle.items[0]["metadata"]["hybrid_fusion_score"] > (
        bundle.items[1]["metadata"]["hybrid_fusion_score"]
    )
    assert bundle.metadata["hybrid_fusion_trace"]["ranker"] == (
        "weighted_cross_modal_v1"
    )
    assert (
        bundle.metadata["hybrid_fusion_trace"]["item_scores"]["page-image:file-b:5"]
        > bundle.metadata["hybrid_fusion_trace"]["item_scores"]["text-b"]
    )


def test_hybrid_route_can_use_rrf_fusion_strategy():
    request = DocQARequest(
        prompt="Explain revenue chart and table.", route_policy="hybrid"
    )
    metadata = {
        "hybrid_fusion_strategy": "rrf",
        "evidence": [
            {
                "evidence_id": "text-b",
                "file_id": "file-b",
                "page_label": "5",
                "text": "Revenue chart and table summarize growth.",
                "metadata": {"retriever_score": 0.5},
            }
        ],
        "page_image_index": [
            {
                "evidence_id": "page-image:file-b:5",
                "file_id": "file-b",
                "page_label": "5",
                "modality": "page_image",
                "text": "Revenue chart visual.",
            }
        ],
        "visual_retriever_scores": {"page-image:file-b:5": 0.9},
        "element_index": [
            {
                "evidence_id": "element:file-b:5:table-a",
                "file_id": "file-b",
                "page_label": "5",
                "element_id": "table-a",
                "modality": "table",
                "caption": "Revenue table",
            }
        ],
        "element_retriever_scores": {"element:file-b:5:table-a": 0.8},
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert bundle.metadata["hybrid_fusion_trace"]["ranker"] == (
        "reciprocal_rank_fusion_v1"
    )
    assert all(
        "rrf_score" in item["metadata"]["hybrid_fusion_components"]
        for item in bundle.items
    )


def test_hybrid_route_can_use_learned_cross_modal_ranker():
    class FixtureRanker:
        name = "fixture_learned_ranker"

        def score(self, query, item):
            return 3.0 if item["evidence_id"] == "element:file-b:5:table-a" else 0.1

    request = DocQARequest(
        prompt="Explain revenue chart and table.", route_policy="hybrid"
    )
    metadata = {
        "hybrid_fusion_ranker": FixtureRanker(),
        "evidence": [
            {
                "evidence_id": "text-b",
                "file_id": "file-b",
                "page_label": "5",
                "text": "Revenue chart and table summarize growth.",
            }
        ],
        "page_image_index": [
            {
                "evidence_id": "page-image:file-b:5",
                "file_id": "file-b",
                "page_label": "5",
                "modality": "page_image",
                "text": "Revenue chart visual.",
            }
        ],
        "element_index": [
            {
                "evidence_id": "element:file-b:5:table-a",
                "file_id": "file-b",
                "page_label": "5",
                "element_id": "table-a",
                "modality": "table",
                "caption": "Revenue table",
            }
        ],
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert bundle.items[0]["evidence_id"] == "element:file-b:5:table-a"
    assert bundle.metadata["hybrid_fusion_trace"]["ranker"] == (
        "fixture_learned_ranker"
    )
    assert (
        bundle.items[0]["metadata"]["hybrid_fusion_components"]["learned_score"] == 3.0
    )
