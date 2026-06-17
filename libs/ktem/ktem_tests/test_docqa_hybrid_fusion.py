from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.hybrid_fusion import fuse_hybrid_evidence


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


def test_hybrid_fusion_prioritizes_financial_statement_text_over_irrelevant_visual_score():
    fused, trace = fuse_hybrid_evidence(
        "Calculate inventory turnover using cost of sales and inventories.",
        [
            {
                "evidence_id": "visual-derivative-page",
                "source_id": "aes-2022",
                "page_label": "152",
                "modality": "page_image",
                "text": "Derivative credit ratings and counterparty exposure.",
                "metadata": {"visual_retriever_score": 0.95},
            },
            {
                "evidence_id": "text-income-balance-page",
                "source_id": "aes-2022",
                "page_label": "132",
                "modality": "text",
                "text": (
                    "Consolidated Statements of Operations. Cost of sales "
                    "$10,230. Consolidated Balance Sheets. Inventories $1,077."
                ),
            },
        ],
        domain="finance",
    )

    assert fused[0]["evidence_id"] == "text-income-balance-page"
    components = fused[0]["metadata"]["hybrid_fusion_components"]
    assert components["finance_statement_match"] > 0
    assert trace["ranker"] == "weighted_cross_modal_v1"


def test_hybrid_fusion_does_not_apply_finance_statement_boost_by_default():
    fused, _trace = fuse_hybrid_evidence(
        "Calculate inventory turnover using cost of sales and inventories.",
        [
            {
                "evidence_id": "visual-derivative-page",
                "source_id": "paper",
                "page_label": "152",
                "modality": "page_image",
                "text": "Derivative credit ratings and counterparty exposure.",
                "metadata": {"visual_retriever_score": 0.95},
            },
            {
                "evidence_id": "text-income-balance-page",
                "source_id": "paper",
                "page_label": "132",
                "modality": "text",
                "text": (
                    "Consolidated Statements of Operations. Cost of sales "
                    "$10,230. Consolidated Balance Sheets. Inventories $1,077."
                ),
            },
        ],
    )

    assert fused[0]["evidence_id"] == "visual-derivative-page"
    components = fused[1]["metadata"]["hybrid_fusion_components"]
    assert components["finance_statement_match"] == 0.0


def test_hybrid_fusion_applies_finance_statement_boost_when_opted_in():
    fused, _trace = fuse_hybrid_evidence(
        "Calculate inventory turnover using cost of sales and inventories.",
        [
            {
                "evidence_id": "visual-derivative-page",
                "source_id": "aes-2022",
                "page_label": "152",
                "modality": "page_image",
                "text": "Derivative credit ratings and counterparty exposure.",
                "metadata": {"visual_retriever_score": 0.95},
            },
            {
                "evidence_id": "text-income-balance-page",
                "source_id": "aes-2022",
                "page_label": "132",
                "modality": "text",
                "text": (
                    "Consolidated Statements of Operations. Cost of sales "
                    "$10,230. Consolidated Balance Sheets. Inventories $1,077."
                ),
            },
        ],
        domain="finance",
    )

    assert fused[0]["evidence_id"] == "text-income-balance-page"
    components = fused[0]["metadata"]["hybrid_fusion_components"]
    assert components["finance_statement_match"] > 0
