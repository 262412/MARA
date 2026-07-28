from ktem.docqa.evidence_identity import identity_of

from benchmark.docqa_evidence_projection import (
    evidence_element_ids,
    retrieved_hits_from_docqa_evidence,
)
from benchmark.index_metadata import normalize_retrieved_hit


def test_text_hit_metadata_has_source_identity_and_optional_locator():
    hit = normalize_retrieved_hit(
        {
            "text": "The method improves recall.",
            "metadata": {"source_id": "paper-1", "page_label": "3"},
        }
    )

    assert hit["source_id"] == "paper-1"
    assert hit["document_id"] == "paper-1"
    assert hit["page_label"] == "3"
    assert hit["text"] == "The method improves recall."


def test_docqa_projection_uses_nested_metadata_for_source_backrefs():
    hits = retrieved_hits_from_docqa_evidence(
        {
            "items": [
                {
                    "doc_id": "chunk-1",
                    "content": "The method improves recall.",
                    "metadata": {
                        "source_id": "paper-1",
                        "page_number": 3,
                        "file_name": "paper.pdf",
                    },
                }
            ]
        },
        {},
    )

    assert hits == [
        {
            "evidence_id": "chunk-1",
            "canonical_id": "evidence:paper-1:chunk-1",
            "document_id": "paper-1",
            "source_id": "paper-1",
            "source_name": "paper.pdf",
            "page_label": "3",
            "text": "The method improves recall.",
            "identity": {
                "source_id": "paper-1",
                "kind": "evidence",
                "local_id": "chunk-1",
            },
            "source_backrefs": ["paper-1#page:3"],
        }
    ]


def test_runtime_evidence_projection_is_lossless_for_identity_and_numeric_fields():
    hit = normalize_retrieved_hit(
        {
            "evidence_id": "table-1",
            "canonical_id": "cell:report:revenue-2023",
            "source_id": "report",
            "source_aliases": ["report.pdf"],
            "page_label": "12",
            "dataset_page": "14",
            "parser_page_index": 11,
            "page_aliases": ["12", "14"],
            "element_id": "table-1",
            "cell_id": "revenue-2023",
            "parent_element_id": "table-1",
            "table_id": "table-1",
            "row_index": 4,
            "column_index": 2,
            "row_label": "Revenue",
            "column_label": "2023",
            "period": "2023",
            "period_kind": "fiscal_year",
            "value": "12.5",
            "unit": "USD",
            "scale": "million",
            "currency": "USD",
            "statement_kind": "income_statement",
            "financial_scope": "consolidated",
            "evidence_level": "cell",
            "section_id": "section-2",
            "continuation_id": "table-series-1",
            "chunk_start": 120,
            "chunk_end": 160,
            "normalized_text_hash": "sha256:record",
            "duplicate_evidence_ids": ["cell-alias"],
            "neighbor_element_ids": ["revenue-2022"],
            "retrieval_lineage": [
                {
                    "round_id": 2,
                    "query_id": "round2:revenue",
                    "slot_id": "operand:revenue",
                    "retriever_name": "dense",
                    "raw_rank": 3,
                    "raw_score": 0.82,
                    "score_type": "cosine",
                }
            ],
            "source_backrefs": ["report#page:12#cell:revenue-2023"],
            "bbox": [10.0, 20.0, 200.0, 120.0],
            "caption": "Revenue table",
            "ocr_text": "Revenue 2023 12.5",
            "vlm_text": "A highlighted revenue cell.",
            "section_title": "Financial results",
            "table_title": "Revenue by year",
            "text": "Revenue 2023 12.5 million",
        }
    )

    _assert_lossless_projection(hit)
    assert identity_of(hit).key == "cell:report:revenue-2023"


def _assert_lossless_projection(hit):
    assert hit == {
        "evidence_id": "table-1",
        "canonical_id": "cell:report:revenue-2023",
        "identity": {
            "source_id": "report",
            "kind": "cell",
            "local_id": "revenue-2023",
        },
        "document_id": "report",
        "source_id": "report",
        "source_aliases": ["report.pdf"],
        "page_label": "12",
        "dataset_page": "14",
        "parser_page_index": 11,
        "page_aliases": ["12", "14"],
        "element_id": "table-1",
        "cell_id": "revenue-2023",
        "parent_element_id": "table-1",
        "table_id": "table-1",
        "row_index": 4,
        "column_index": 2,
        "row_label": "Revenue",
        "column_label": "2023",
        "period": "2023",
        "period_kind": "fiscal_year",
        "value": "12.5",
        "unit": "USD",
        "scale": "million",
        "currency": "USD",
        "statement_kind": "income_statement",
        "financial_scope": "consolidated",
        "evidence_level": "cell",
        "section_id": "section-2",
        "continuation_id": "table-series-1",
        "chunk_start": 120,
        "chunk_end": 160,
        "normalized_text_hash": "sha256:record",
        "duplicate_evidence_ids": ["cell-alias"],
        "neighbor_element_ids": ["revenue-2022"],
        "retrieval_lineage": [
            {
                "round_id": 2,
                "query_id": "round2:revenue",
                "slot_id": "operand:revenue",
                "retriever_name": "dense",
                "raw_rank": 3,
                "raw_score": 0.82,
                "score_type": "cosine",
            }
        ],
        "bbox": [10.0, 20.0, 200.0, 120.0],
        "caption": "Revenue table",
        "ocr_text": "Revenue 2023 12.5",
        "vlm_text": "A highlighted revenue cell.",
        "section_title": "Financial results",
        "table_title": "Revenue by year",
        "text": "Revenue 2023 12.5 million",
        "source_backrefs": ["report#page:12#cell:revenue-2023"],
    }


def test_projection_normalizes_float_like_indexes_without_crashing():
    hit = normalize_retrieved_hit(
        {
            "evidence_id": "table-1",
            "source_id": "report",
            "page_label": "page-5",
            "parser_page_index": "5.0",
            "row_index": "2.0",
            "column_index": "not-an-index",
            "text": "Revenue table.",
        }
    )

    assert hit["page_label"] == "page-5"
    assert hit["parser_page_index"] == 5
    assert hit["row_index"] == 2
    assert "column_index" not in hit


def test_element_projection_prefers_atomic_cell_identity_over_parent_element():
    assert evidence_element_ids(
        [
            {
                "source_id": "report",
                "element_id": "table-1",
                "cell_id": "revenue-2023",
            }
        ]
    ) == ["revenue-2023"]


def test_span_identity_projection_is_lossless():
    hit = normalize_retrieved_hit(
        {
            "evidence_id": "paragraph-1",
            "source_id": "paper",
            "page_label": "4",
            "span_id": "span:conclusion",
            "evidence_level": "span",
            "text": "The experiment supports the conclusion.",
        }
    )

    assert hit["span_id"] == "span:conclusion"
    assert hit["identity"] == {
        "source_id": "paper",
        "kind": "span",
        "local_id": "span:conclusion",
    }


def test_projection_preserves_namespaced_extension_metadata():
    hit = normalize_retrieved_hit(
        {
            "evidence_id": "figure-1",
            "source_id": "paper",
            "metadata": {
                "parser_confidence": 0.87,
                "layout_engine": "marker",
            },
            "text": "A figure.",
        }
    )

    assert hit["extension_metadata"] == {
        "parser_confidence": 0.87,
        "layout_engine": "marker",
    }
