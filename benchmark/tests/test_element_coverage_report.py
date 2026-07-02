from benchmark.element_coverage_report import element_coverage_report


def test_element_coverage_report_audits_answer_bearing_gold_elements():
    report = element_coverage_report(
        [
            {
                "example_id": "covered",
                "gold_evidence": [
                    {
                        "document_id": "annual_report",
                        "page": 12,
                        "element_type": "table",
                    }
                ],
                "evidence_metadata": {
                    "element_index": [
                        {
                            "file_name": "annual_report.pdf",
                            "page_number": 12,
                            "element_type": "table",
                        }
                    ]
                },
            },
            {
                "example_id": "wrong-page",
                "gold_evidence": [
                    {
                        "document_id": "annual_report",
                        "page": 64,
                        "element_type": "table",
                    }
                ],
                "evidence_metadata": {
                    "element_index": [
                        {
                            "file_name": "annual_report.pdf",
                            "page_number": 444,
                            "element_type": "table",
                        }
                    ]
                },
            },
            {
                "example_id": "missing-index",
                "gold_evidence": [
                    {
                        "document_id": "slides",
                        "page": 3,
                        "element_type": "image",
                    }
                ],
                "evidence_metadata": {},
            },
        ]
    )

    assert report["total_gold_element_references"] == 3
    assert report["gold_element_references_with_index"] == 1
    assert report["predictions_with_answer_bearing_element_index"] == 1
    assert report["predictions_without_answer_bearing_element_index"] == 2
    assert report["answer_bearing_coverage_by_status"] == {
        "covered": 1,
        "missing_index": 1,
        "wrong_page": 1,
    }
    assert report["missing_answer_bearing_example_ids"] == [
        "wrong-page",
        "missing-index",
    ]
    assert report["wrong_page_example_ids"] == ["wrong-page"]


def test_element_coverage_report_separates_locator_alias_alignment():
    report = element_coverage_report(
        [
            {
                "example_id": "visual-alias",
                "gold_evidence": [
                    {
                        "document_id": "annual_report",
                        "page": 12,
                        "element_id": "image4",
                        "element_type": "image",
                    }
                ],
                "evidence_metadata": {
                    "element_index": [
                        {
                            "file_name": "annual_report.pdf",
                            "page_number": 12,
                            "element_id": "text-12-4",
                            "element_id_aliases": ["image4"],
                            "element_type": "text",
                            "element_type_aliases": ["figure", "image"],
                        }
                    ]
                },
            }
        ]
    )

    assert report["gold_element_references_with_index"] == 0
    assert report["answer_bearing_coverage_by_status"] == {"wrong_element_type": 1}
    assert report["gold_element_references_with_locator_alignment"] == 1
    assert report["predictions_with_locator_aligned_element_index"] == 1
    assert report["answer_bearing_locator_alignment_by_status"] == {"covered": 1}
