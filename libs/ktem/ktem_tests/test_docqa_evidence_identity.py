import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.evidence_identity import (
    EvidenceIdentityConflictError,
    canonicalize_and_dedupe_evidence,
    identity_of,
)


def test_structure_dedup_merges_same_element_and_preserves_all_backrefs():
    items, trace = canonicalize_and_dedupe_evidence(
        [
            {
                "evidence_id": "dense-1",
                "source_id": "report",
                "page_label": "10",
                "element_id": "table-1-cell-r2-c3",
                "text": "Revenue was $10 million.",
                "source_backrefs": ["report#page:10"],
                "metadata": {"retriever": "dense", "rank": 1},
            },
            {
                "evidence_id": "sparse-7",
                "source_id": "report",
                "page_label": "10",
                "element_id": "table-1-cell-r2-c3",
                "text": "Revenue was $10 million.",
                "source_backrefs": ["report#cell:r2c3"],
                "metadata": {"retriever": "sparse", "rank": 7},
            },
        ]
    )

    assert len(items) == 1
    assert items[0]["canonical_id"].startswith("element:")
    assert items[0]["duplicate_evidence_ids"] == ["sparse-7"]
    assert items[0]["source_backrefs"] == [
        "report#page:10",
        "report#cell:r2c3",
    ]
    assert trace["structure_duplicate_count"] == 1


def test_identical_text_across_sources_remains_distinct():
    items, trace = canonicalize_and_dedupe_evidence(
        [
            {
                "evidence_id": "a",
                "source_id": "filing-a",
                "page_label": "2",
                "text": "Net income was $5 million.",
                "source_backrefs": ["filing-a#page:2"],
            },
            {
                "evidence_id": "b",
                "source_id": "filing-b",
                "page_label": "8",
                "text": "Net income was $5 million.",
                "source_backrefs": ["filing-b#page:8"],
            },
        ]
    )

    assert len(items) == 2
    assert [item["source_backrefs"] for item in items] == [
        ["filing-a#page:2"],
        ["filing-b#page:8"],
    ]
    assert trace["exact_text_duplicate_count"] == 0


def test_cells_with_same_parent_remain_distinct():
    items, trace = canonicalize_and_dedupe_evidence(
        [
            {
                "evidence_id": "table-1",
                "source_id": "report",
                "page_label": "10",
                "element_id": "table-1",
                "table_id": "table-1",
                "cell_id": "table-1#row:revenue#column:2022",
                "row_index": 2,
                "column_index": 1,
                "period": "2022",
                "value": "10",
                "text": "Revenue 2022 10",
            },
            {
                "evidence_id": "table-1",
                "source_id": "report",
                "page_label": "10",
                "element_id": "table-1",
                "table_id": "table-1",
                "cell_id": "table-1#row:revenue#column:2023",
                "row_index": 2,
                "column_index": 2,
                "period": "2023",
                "value": "12",
                "text": "Revenue 2023 12",
            },
        ]
    )

    assert len(items) == 2
    assert {identity_of(item).local_id for item in items} == {
        "table-1#row:revenue#column:2022",
        "table-1#row:revenue#column:2023",
    }
    assert {identity_of(item).kind for item in items} == {"cell"}
    assert trace["structure_duplicate_count"] == 0


def test_dedupe_rejects_same_identity_with_conflicting_structured_fact():
    with pytest.raises(EvidenceIdentityConflictError, match="value"):
        canonicalize_and_dedupe_evidence(
            [
                {
                    "evidence_id": "dense",
                    "source_id": "report",
                    "cell_id": "revenue-2023",
                    "period": "2023",
                    "value": "10",
                    "text": "Revenue 2023 10",
                },
                {
                    "evidence_id": "sparse",
                    "source_id": "report",
                    "cell_id": "revenue-2023",
                    "period": "2023",
                    "value": "12",
                    "text": "Revenue 2023 12 million",
                },
            ]
        )


def test_dedupe_never_overwrites_representative_structured_text():
    items, _trace = canonicalize_and_dedupe_evidence(
        [
            {
                "evidence_id": "dense",
                "source_id": "report",
                "cell_id": "revenue-2023",
                "period": "2023",
                "value": "10",
                "text": "Revenue 2023 10",
            },
            {
                "evidence_id": "sparse",
                "source_id": "report",
                "cell_id": "revenue-2023",
                "period": "2023",
                "value": "10",
                "text": "Revenue for fiscal year 2023 was 10 million.",
            },
        ]
    )

    assert len(items) == 1
    assert items[0]["text"] == "Revenue 2023 10"
    assert items[0]["normalized_text_hash"]


def test_semantic_dedup_does_not_merge_conflicting_numbers():
    items, trace = canonicalize_and_dedupe_evidence(
        [
            {
                "evidence_id": "a",
                "source_id": "report",
                "page_label": "2",
                "text": "Revenue increased to 10 million in 2022.",
                "metadata": {"semantic_embedding": [1.0, 0.0]},
            },
            {
                "evidence_id": "b",
                "source_id": "report",
                "page_label": "3",
                "text": "Revenue increased to 12 million in 2022.",
                "metadata": {"semantic_embedding": [0.999, 0.001]},
            },
        ]
    )

    assert len(items) == 2
    assert trace["semantic_duplicate_count"] == 0
    assert trace["conflict_guard_count"] == 0


def test_overlapping_chunks_merge_when_same_parent_and_overlap_is_high():
    items, trace = canonicalize_and_dedupe_evidence(
        [
            {
                "evidence_id": "chunk-1",
                "source_id": "report",
                "page_label": "5",
                "parent_element_id": "page-5",
                "chunk_start": 0,
                "chunk_end": 100,
                "text": "alpha revenue growth demand outlook",
            },
            {
                "evidence_id": "chunk-2",
                "source_id": "report",
                "page_label": "5",
                "parent_element_id": "page-5",
                "chunk_start": 20,
                "chunk_end": 110,
                "text": "revenue growth demand outlook guidance",
            },
        ]
    )

    assert len(items) == 1
    assert trace["overlap_duplicate_count"] == 1


def test_evidence_bundle_preserves_dataset_parser_and_cell_identity_fields():
    bundle = build_evidence_bundle(
        "doc",
        DocQARequest(
            prompt="What were current assets in 2021?",
            route_policy="doc",
            selected_file_ids=["runtime-file-id"],
        ),
        {
            "evidence": [
                {
                    "evidence_id": "dense-1",
                    "file_id": "runtime-file-id",
                    "source_name": "LOCKHEEDMARTIN_2021_10K.pdf",
                    "page_label": "68",
                    "dataset_page": "68",
                    "parser_page_index": 67,
                    "page_aliases": ["68", "30"],
                    "element_id": "balance-sheet",
                    "table_id": "balance-sheet",
                    "cell_id": "balance-sheet#row:current-assets#column:2021",
                    "row_label": "Current assets",
                    "column_label": "2021",
                    "period": "2021",
                    "scale": "million",
                    "currency": "USD",
                    "text": "Current assets 20,991",
                }
            ]
        },
    )

    item = bundle.items[0]
    assert item["dataset_page"] == "68"
    assert item["parser_page_index"] == 67
    assert item["page_aliases"] == ["68", "30"]
    assert item["cell_id"].endswith("column:2021")
    assert item["row_label"] == "Current assets"
    assert item["column_label"] == "2021"
    assert item["period"] == "2021"
    assert item["scale"] == "million"
    assert item["currency"] == "USD"


def test_bundle_does_not_publish_reranked_stage_without_backend_execution():
    bundle = build_evidence_bundle(
        "doc",
        DocQARequest(prompt="What happened?", route_policy="doc"),
        {
            "evidence": [
                {
                    "evidence_id": "chunk-1",
                    "source_id": "report",
                    "page_label": "2",
                    "text": "Revenue increased.",
                }
            ]
        },
    )

    assert "reranked_evidence" not in bundle.metadata
    assert bundle.metadata["ranking_trace"]["backend_execution"] is False


def test_bundle_publishes_reranked_stage_when_scores_have_backend_lineage():
    bundle = build_evidence_bundle(
        "doc",
        DocQARequest(prompt="What happened?", route_policy="doc"),
        {
            "reranker_backend": "local-bge-reranker-v2-m3",
            "evidence": [
                {
                    "evidence_id": "low",
                    "source_id": "report",
                    "page_label": "2",
                    "text": "Background.",
                    "metadata": {"reranking_score": 0.1},
                },
                {
                    "evidence_id": "high",
                    "source_id": "report",
                    "page_label": "3",
                    "text": "Revenue increased.",
                    "metadata": {"reranking_score": 0.9},
                },
            ],
        },
    )

    assert [item["evidence_id"] for item in bundle.metadata["reranked_evidence"]] == [
        "high",
        "low",
    ]
    assert bundle.metadata["ranking_trace"]["backend_execution"] is True
    assert bundle.metadata["ranking_trace"]["backend"] == ("local-bge-reranker-v2-m3")


def test_required_slot_can_restore_candidate_below_real_reranker_output_cutoff():
    evidence = [
        {
            "evidence_id": f"background-{index}",
            "source_id": "report",
            "page_label": str(index),
            "text": f"Background material {index}.",
            "metadata": {"reranking_score": 1.0 - index / 100},
        }
        for index in range(35)
    ]
    evidence.append(
        {
            "evidence_id": "revenue-atom",
            "source_id": "report",
            "page_label": "40",
            "text": "Revenue was 42 million.",
            "metadata": {"reranking_score": 0.01},
        }
    )

    bundle = build_evidence_bundle(
        "doc",
        DocQARequest(
            prompt="What was revenue?",
            task_type="numeric",
            route_policy="doc",
        ),
        {
            "reranker_backend": "local-bge-reranker-v2-m3",
            "evidence": evidence,
        },
    )

    assert "revenue-atom" not in {
        item["evidence_id"] for item in bundle.metadata["reranked_evidence"]
    }
    assert "revenue-atom" in {item["evidence_id"] for item in bundle.items}
    assert (
        bundle.metadata["evidence_selection_trace"]["required_slot_candidates_restored"]
        == 1
    )
