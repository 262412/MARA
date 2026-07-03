from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle


def test_doc_element_evidence_bundle_limits_selected_ranked_items():
    request = DocQARequest(
        prompt="What was the depreciation charge?",
        active_file_id="file-1",
        page_number=64,
    )
    records = [
        {
            "evidence_id": f"element:file-1:{page}:table-{index}",
            "file_id": "file-1",
            "file_name": "report.pdf",
            "page_label": str(page),
            "element_id": f"table-{index}",
            "modality": "table",
            "text": text,
            "metadata": {"element_retriever_score": score},
        }
        for index, (page, text, score) in enumerate(
            [
                (444, "Depreciation charge policy training text.", 0.2),
                (64, "Depreciation charge was 246 million.", 1.0),
                *[
                    (64, f"Other page 64 table row {item}.", 0.8 - item / 100)
                    for item in range(12)
                ],
            ],
            start=1,
        )
    ]

    bundle = build_evidence_bundle(
        "doc_element",
        request,
        {"element_index": records, "element_retriever_scores": {}},
    )

    assert len(bundle.items) == 10
    assert bundle.items[0]["element_id"] == "table-2"
    assert "table-1" not in {item["element_id"] for item in bundle.items}
