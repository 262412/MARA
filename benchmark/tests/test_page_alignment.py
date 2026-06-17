from benchmark.page_alignment import (
    align_gold_page,
    align_locator,
    evidence_text_supports_gold_locator,
    item_matches_citation,
    item_page_label,
)


def test_aligns_numeric_gold_page_to_parser_page_label():
    parser_pages = [
        {"page_index": 0, "page_label": "i"},
        {"page_index": 1, "page_label": "1"},
        {"page_index": 2, "page_label": "2"},
    ]

    assert align_gold_page("2", parser_pages) == 2


def test_aligns_one_based_gold_page_when_labels_are_missing():
    parser_pages = [{"page_index": 0}, {"page_index": 1}, {"page_index": 2}]

    assert align_gold_page(2, parser_pages) == 1


def test_returns_none_for_unaligned_gold_page():
    parser_pages = [{"page_index": 0, "page_label": "A-1"}]

    assert align_gold_page("99", parser_pages) is None


def test_aligns_gold_page_label_to_parser_page_index():
    metadata = {"page_label": "58", "page": 57}

    aligned = align_locator(gold_page="58", retrieved_metadata=metadata)

    assert aligned.locator_applicable is True
    assert aligned.page_exact is True
    assert aligned.parser_page_index == 57


def test_source_level_locator_does_not_require_page():
    metadata = {"source_id": "14864"}

    aligned = align_locator(gold_page=None, retrieved_metadata=metadata)

    assert aligned.locator_applicable is False
    assert aligned.page_exact is None
    assert aligned.parser_page_index is None


def test_visual_quote_support_aligns_parser_locator_text():
    assert evidence_text_supports_gold_locator(
        {
            "page": 58,
            "element_type": "table",
            "image_quote": (
                "The Zone AMS table reports sales of CHF 34.0 billion, "
                "organic growth of 4.8%, and real internal growth of 4.1%."
            ),
        },
        (
            "Zone AMS in millions of CHF. Sales 2020 34.0 billion. "
            "Organic growth 4.8% and real internal growth 4.1%."
        ),
    )


def test_citation_matching_uses_source_backrefs_when_top_level_page_is_missing():
    item = {
        "document_id": "doc",
        "text": "Relevant page text.",
        "source_backrefs": ["doc#page:59"],
    }

    assert item_page_label(item) == "59"
    assert item_matches_citation(item, "doc#page:59")
