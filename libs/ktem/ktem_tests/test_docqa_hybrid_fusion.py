from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.hybrid_fusion import fuse_hybrid_evidence


def test_hybrid_route_uses_retriever_level_rrf_scores():
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

    assert bundle.items[0]["evidence_id"] == "text-b"
    assert bundle.metadata["hybrid_fusion_trace"]["ranker"] == (
        "retriever_reciprocal_rank_fusion_v2"
    )
    confidence = bundle.items[0]["metadata"]["evidence_confidence"]
    assert confidence["route"] == "text"
    assert confidence["normalized_score"] == 1.0
    assert confidence["pre_fusion_rank"] == 1


def test_rrf_accumulates_rank_contributions_for_shared_evidence_identity():
    fused, trace = fuse_hybrid_evidence(
        "What does the table show?",
        [
            {
                "evidence_id": "shared",
                "source_id": "report",
                "page_label": "4",
                "modality": "table",
                "text": "Revenue table.",
                "metadata": {
                    "visual_retriever_score": 0.8,
                    "element_retriever_score": 0.8,
                },
            },
            {
                "evidence_id": "visual-only",
                "source_id": "report",
                "page_label": "5",
                "modality": "page_image",
                "text": "Revenue image.",
                "metadata": {"visual_retriever_score": 0.9},
            },
            {
                "evidence_id": "element-only",
                "source_id": "report",
                "page_label": "6",
                "modality": "table",
                "text": "Revenue appendix.",
                "metadata": {"element_retriever_score": 0.7},
            },
        ],
    )

    assert fused[0]["evidence_id"] == "shared"
    assert trace["retriever_lists"] == ["element", "visual"]


def test_hybrid_item_scores_use_canonical_cell_identity():
    items = [
        {
            "evidence_id": "parent-table",
            "source_id": "report",
            "page_label": "4",
            "table_id": "balance-sheet",
            "cell_id": cell_id,
            "evidence_level": "cell",
            "modality": "table",
            "text": text,
        }
        for cell_id, text in (
            ("current-assets", "Current assets were 100."),
            ("current-liabilities", "Current liabilities were 50."),
        )
    ]

    for strategy in ("rrf", "weighted"):
        _fused, trace = fuse_hybrid_evidence(
            "What was the current ratio?",
            items,
            strategy=strategy,
        )
        assert set(trace["item_scores"]) == {
            "cell:report:current-assets",
            "cell:report:current-liabilities",
        }


def test_rrf_does_not_treat_reranker_score_as_first_stage_retrieval():
    fused, trace = fuse_hybrid_evidence(
        "revenue result",
        [
            {
                "evidence_id": "reranker-only",
                "source_id": "report",
                "page_label": "4",
                "text": "Unrelated appendix.",
                "metadata": {"reranker_score": 100.0},
            },
            {
                "evidence_id": "retrieval-match",
                "source_id": "report",
                "page_label": "5",
                "text": "The revenue result improved.",
            },
        ],
        strategy="rrf",
    )

    assert fused[0]["evidence_id"] == "retrieval-match"
    assert trace["retriever_lists"] == ["text"]


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
        "retriever_reciprocal_rank_fusion_v2"
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
    assert bundle.metadata["ranking_trace"]["backend_execution"] is True
    assert bundle.metadata["ranking_trace"]["backend"] == "fixture_learned_ranker"
    assert bundle.metadata["ranking_trace"]["score_field"] == "reranker_score"


def test_fused_lineage_records_the_actual_post_fusion_ranking_output():
    class PromoteLastRanker:
        name = "fixture_promote_last"

        def score(self, query, item):
            return 10.0 if item["evidence_id"] == "text-81" else 0.0

    request = DocQARequest(
        prompt="Find the promoted financial evidence.",
        route_policy="hybrid",
    )
    metadata = {
        "hybrid_fusion_ranker": PromoteLastRanker(),
        "evidence": [
            {
                "evidence_id": f"text-{index}",
                "source_id": "report",
                "page_label": str(index),
                "text": f"Distinct financial statement evidence row {index}.",
            }
            for index in range(1, 82)
        ],
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    candidate_ids = {
        item["evidence_id"] for item in bundle.metadata["candidate_evidence"]
    }
    fused_ids = {item["evidence_id"] for item in bundle.metadata["fused_evidence"]}
    assert len(candidate_ids) == 81
    assert "text-81" in candidate_ids
    assert "text-81" in fused_ids
    assert fused_ids <= candidate_ids
    assert "text-81" in {
        item["evidence_id"] for item in bundle.metadata["reranked_evidence"]
    }
    assert bundle.metadata["ranking_trace"]["backend_execution"] is True


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
    assert trace["ranker"] == "retriever_reciprocal_rank_fusion_v2"


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

    assert fused[0]["evidence_id"] == "text-income-balance-page"
    components = fused[0]["metadata"]["hybrid_fusion_components"]
    assert components["finance_statement_match"] == 0.0


def test_hybrid_fusion_keeps_wide_candidates_for_downstream_mmr_selection():
    fused, trace = fuse_hybrid_evidence(
        "What were the revenue growth risks?",
        [
            {
                "evidence_id": "text-risk",
                "source_id": "mmdoc",
                "page_label": "4",
                "modality": "text",
                "text": "Revenue growth risks include weaker renewal demand.",
            },
            {
                "evidence_id": "text-summary",
                "source_id": "mmdoc",
                "page_label": "5",
                "modality": "text",
                "text": "The report summarizes revenue growth and operating risk.",
            },
            {
                "evidence_id": "page-image:mmdoc:99",
                "source_id": "mmdoc",
                "page_label": "99",
                "modality": "page_image",
                "text": "Unrelated appendix image.",
                "metadata": {"visual_retriever_score": 0.99},
            },
            {
                "evidence_id": "page-image:mmdoc:4",
                "source_id": "mmdoc",
                "page_label": "4",
                "modality": "page_image",
                "ocr_text": "Revenue growth risks chart.",
                "metadata": {"visual_retriever_score": 0.7},
            },
        ],
    )

    assert [item["evidence_id"] for item in fused] == [
        "text-risk",
        "text-summary",
        "page-image:mmdoc:4",
        "page-image:mmdoc:99",
    ]
    assert trace["dropped_noise_count"] == 0
    assert "selected_top_k" not in trace


def test_hybrid_bundle_preserves_cross_page_visual_evidence():
    request = DocQARequest(
        prompt="What were the revenue growth risks?",
        route_policy="hybrid",
        verification_domain="document_complex",
    )
    metadata = {
        "evidence": [
            {
                "evidence_id": "text-risk",
                "source_id": "mmdoc",
                "file_id": "mmdoc",
                "file_name": "mmdoc.pdf",
                "page_label": "4",
                "modality": "text",
                "text": "Revenue growth risks include weaker renewal demand.",
            }
        ],
        "page_image_index": [
            {
                "evidence_id": "page-image:mmdoc:99",
                "source_id": "mmdoc",
                "file_id": "mmdoc",
                "file_name": "mmdoc.pdf",
                "page_label": "99",
                "modality": "page_image",
                "ocr_text": "Unrelated appendix image.",
            }
        ],
        "visual_retriever_scores": {"page-image:mmdoc:99": 0.99},
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert {item["evidence_id"] for item in bundle.items} == {
        "text-risk",
        "page-image:mmdoc:99",
    }
    assert bundle.metadata["hybrid_fusion_trace"]["fallback_route"] == ""
    assert bundle.metadata["hybrid_fusion_trace"]["best_single_route"] == "text"


def test_hybrid_fusion_drops_low_coverage_element_noise_for_document_complex():
    fused, trace = fuse_hybrid_evidence(
        "What value is in the revenue table?",
        [
            {
                "evidence_id": "text-table",
                "source_id": "mmdoc",
                "page_label": "4",
                "modality": "text",
                "text": "The revenue table reports $42 million.",
            },
            {
                "evidence_id": "element-missing-locator",
                "modality": "table",
                "element_id": "table-1",
                "metadata": {"element_retriever_score": 0.99},
            },
        ],
        domain="mmdocrag",
    )

    assert [item["evidence_id"] for item in fused] == ["text-table"]
    assert trace["dropped_low_coverage_element_count"] == 1


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
