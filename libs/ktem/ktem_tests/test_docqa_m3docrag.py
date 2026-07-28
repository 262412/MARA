from ktem.docqa.m3docrag import select_page_first_evidence


def test_page_first_evidence_ranks_pages_without_pruning_candidates():
    items = [
        {
            "evidence_id": "text-1",
            "source_id": "file-a",
            "page_label": "1",
            "modality": "text",
            "text": "Background policy.",
        },
        {
            "evidence_id": "text-2",
            "source_id": "file-b",
            "page_label": "5",
            "modality": "text",
            "text": "Revenue chart and table summarize growth.",
        },
        {
            "evidence_id": "page-image-2",
            "source_id": "file-b",
            "page_label": "5",
            "modality": "page_image",
            "text": "Revenue chart visual.",
        },
        {
            "evidence_id": "text-3",
            "source_id": "file-c",
            "page_label": "9",
            "modality": "text",
            "text": "Unrelated appendix.",
        },
        {
            "evidence_id": "graph-1",
            "source_id": "",
            "page_label": "",
            "modality": "graph",
            "text": "Revenue is connected to the chart.",
        },
        {
            "evidence_id": "graph-2",
            "source_id": "",
            "page_label": "",
            "modality": "graph",
            "text": "Second graph item should be pruned.",
        },
    ]

    selected, trace = select_page_first_evidence(
        "Explain the revenue chart and table.",
        items,
        max_pages=1,
        max_unpaged_items=1,
    )

    assert selected == items
    assert trace["ranked_pages"] == [{"source_id": "file-b", "page_label": "5"}]
    assert trace["pruned_item_count"] == 0
    assert trace["candidate_preservation"] == "all"


def test_page_rank_does_not_reward_duplicate_chunk_count_linearly():
    critical = {
        "evidence_id": "critical-table",
        "source_id": "report",
        "page_label": "8",
        "modality": "table",
        "text": "Revenue was 42 million.",
        "metadata": {"hybrid_fusion_score": 0.9},
    }
    duplicated = [
        {
            "evidence_id": f"duplicate-{index}",
            "source_id": "report",
            "page_label": "2",
            "modality": "text",
            "text": "Revenue background.",
            "metadata": {"hybrid_fusion_score": 0.1},
        }
        for index in range(12)
    ]

    selected, trace = select_page_first_evidence(
        "What was revenue?",
        [*duplicated, critical],
        max_pages=1,
    )

    assert len(selected) == 13
    assert trace["ranked_pages"] == [{"source_id": "report", "page_label": "8"}]
