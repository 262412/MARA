from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.evidence_identity import canonicalize_and_dedupe_evidence


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


def test_text_dedup_merges_exact_text_across_sources_without_losing_provenance():
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

    assert len(items) == 1
    assert items[0]["source_backrefs"] == [
        "filing-a#page:2",
        "filing-b#page:8",
    ]
    assert items[0]["metadata"]["dedupe_source_ids"] == ["filing-a", "filing-b"]
    assert trace["exact_text_duplicate_count"] == 1


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
    assert trace["conflict_guard_count"] == 1


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
