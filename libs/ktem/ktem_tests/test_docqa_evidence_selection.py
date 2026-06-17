from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import build_evidence_bundle


def test_visual_route_limits_page_image_candidates_to_selected_evidence():
    request = DocQARequest(
        prompt="What does the revenue chart show?",
        route_policy="visual",
        selected_file_ids=["file-a"],
    )
    page_records = [
        {
            "evidence_id": f"page-image:file-a:{page}",
            "file_id": "file-a",
            "file_name": "visual.pdf",
            "page_label": str(page),
            "modality": "page_image",
            "text": f"Revenue visual page {page}.",
            "source_backrefs": [f"file-a#page:{page}"],
        }
        for page in range(1, 13)
    ]
    metadata = {
        "page_coverage": [str(page) for page in range(1, 13)],
        "page_image_index": page_records,
        "visual_retriever_scores": {
            record["evidence_id"]: 1.0 - index * 0.01
            for index, record in enumerate(page_records)
        },
    }

    bundle = build_evidence_bundle("doc_page_image", request, metadata)

    assert len(bundle.items) == 10
    assert [item["page_label"] for item in bundle.items] == [
        str(page) for page in range(1, 11)
    ]
    assert bundle.metadata["page_coverage"] == [str(page) for page in range(1, 11)]


def test_hybrid_route_page_coverage_tracks_selected_evidence_not_candidates():
    request = DocQARequest(
        prompt="Explain the revenue chart and table.",
        route_policy="hybrid",
        selected_file_ids=["file-a"],
    )
    metadata = {
        "page_coverage": ["1", "2", "3", "99"],
        "evidence": [
            {
                "evidence_id": "text-a",
                "file_id": "file-a",
                "file_name": "results.pdf",
                "page_label": "1",
                "text": "Revenue chart and table summarize growth.",
                "source_backrefs": ["file-a#page:1"],
            }
        ],
        "page_image_index": [
            {
                "evidence_id": "page-image:file-a:2",
                "file_id": "file-a",
                "file_name": "results.pdf",
                "page_label": "2",
                "modality": "page_image",
                "text": "Revenue chart visual.",
                "source_backrefs": ["file-a#page:2"],
            }
        ],
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert bundle.metadata["page_coverage"] == ["1", "2"]
    assert "99" not in bundle.metadata["page_coverage"]


def test_text_route_uses_selected_text_as_source_level_evidence():
    request = DocQARequest(
        prompt="Summarize this selected source.",
        route_policy="doc",
        active_file_id="file-a",
        active_file_name="source.txt",
        selected_file_ids=["file-a"],
        selected_text="The source explains that revenue rose because demand improved.",
    )

    bundle = build_evidence_bundle("doc", request, {"evidence": []})

    assert bundle.items == [
        {
            "evidence_id": "selected-text:file-a",
            "source_id": "file-a",
            "source_name": "source.txt",
            "page_label": "",
            "modality": "text",
            "element_id": "",
            "bbox": None,
            "caption": "",
            "text": "The source explains that revenue rose because demand improved.",
            "ocr_text": "",
            "vlm_text": "",
            "source_backrefs": ["file-a#source"],
            "evidence_level": "source",
            "metadata": {"route": "doc"},
        }
    ]
    assert bundle.metadata["source_ids"] == ["file-a"]
    assert bundle.metadata["evidence_ids"] == ["selected-text:file-a"]
