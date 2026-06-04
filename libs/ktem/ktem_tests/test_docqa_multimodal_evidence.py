from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence import EvidenceElement, build_evidence_bundle
from ktem.docqa.multimodal_index import (
    build_local_page_image_records,
    element_records_from_documents,
    page_image_records_from_documents,
)
from ktem.docqa.visual_retriever import (
    LocalLateInteractionVisualRetriever,
    rank_page_image_records,
)

from kotaemon.base import RetrievedDocument


def test_evidence_element_preserves_multimodal_identity_fields():
    element = EvidenceElement(
        evidence_id="table-hit",
        source_id="file-1",
        source_name="report.pdf",
        page_label="7",
        modality="table",
        element_id="table-7",
        bbox=[1, 2, 3, 4],
        caption="Revenue table",
        text="Revenue increased.",
        ocr_text="Revenue FY2026",
        vlm_text="A table of yearly revenue.",
    )

    assert element.as_dict() == {
        "evidence_id": "table-hit",
        "source_id": "file-1",
        "source_name": "report.pdf",
        "page_label": "7",
        "modality": "table",
        "element_id": "table-7",
        "bbox": [1, 2, 3, 4],
        "caption": "Revenue table",
        "text": "Revenue increased.",
        "ocr_text": "Revenue FY2026",
        "vlm_text": "A table of yearly revenue.",
        "source_backrefs": [],
        "evidence_level": "page",
        "metadata": {},
    }


def test_visual_route_synthesizes_page_image_evidence_from_request_context():
    request = DocQARequest(
        prompt="What does the chart show?",
        route_policy="visual",
        active_file_id="file-1",
        active_file_name="chart.pdf",
        page_number=4,
        selected_text="The chart compares revenue growth.",
    )

    bundle = build_evidence_bundle("doc_page_image", request, {})

    assert bundle.route == "doc_page_image"
    assert bundle.items == [
        {
            "evidence_id": "page-image:file-1:4",
            "source_id": "file-1",
            "source_name": "chart.pdf",
            "page_label": "4",
            "modality": "page_image",
            "element_id": "",
            "bbox": None,
            "caption": "",
            "text": "The chart compares revenue growth.",
            "ocr_text": "The chart compares revenue growth.",
            "vlm_text": "",
            "source_backrefs": ["file-1#page:4"],
            "evidence_level": "page",
            "metadata": {"route": "doc_page_image"},
        }
    ]


def test_hybrid_route_normalizes_text_page_image_and_element_evidence():
    request = DocQARequest(
        prompt="Compare the paragraph with the table.",
        route_policy="hybrid",
        active_file_id="file-1",
        active_file_name="report.pdf",
        page_number=2,
        selected_text="Page OCR text.",
    )
    metadata = {
        "evidence": [
            {
                "evidence_id": "text-1",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "2",
                "element_type": "text",
                "text": "Text paragraph.",
            }
        ],
        "elements": [
            {
                "evidence_id": "table-1",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "2",
                "element_id": "table-a",
                "modality": "table",
                "bbox": [10, 20, 30, 40],
                "caption": "Revenue",
            }
        ],
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert [item["modality"] for item in bundle.items] == [
        "text",
        "page_image",
        "table",
    ]
    assert bundle.metadata["modality_counts"] == {
        "page_image": 1,
        "table": 1,
        "text": 1,
    }


def test_page_image_index_records_use_thumbnail_metadata():
    docs = [
        RetrievedDocument(
            text="",
            id_="thumb-2",
            metadata={
                "type": "thumbnail",
                "file_id": "file-1",
                "file_name": "deck.pdf",
                "page_label": "2",
                "image_origin": "/tmp/deck-page-2.png",
                "visual_embedding": [0.1, 0.2, 0.3],
                "late_interaction_tokens": ["revenue", "chart"],
            },
        ),
        RetrievedDocument(
            text="Paragraph on page 2.",
            id_="chunk-2",
            metadata={
                "file_id": "file-1",
                "file_name": "deck.pdf",
                "page_label": "2",
                "thumbnail_doc_id": "thumb-2",
            },
        ),
    ]

    records = page_image_records_from_documents(docs)

    assert records == [
        {
            "evidence_id": "page-image:file-1:2",
            "file_id": "file-1",
            "file_name": "deck.pdf",
            "page_label": "2",
            "page_number": 2,
            "page_image_path": "/tmp/deck-page-2.png",
            "page_visual_embedding": [0.1, 0.2, 0.3],
            "late_interaction_tokens": ["revenue", "chart"],
            "modality": "page_image",
            "text": "Paragraph on page 2.",
            "ocr_text": "Paragraph on page 2.",
            "source_backrefs": ["file-1#page:2"],
            "metadata": {
                "image_ref": "/tmp/deck-page-2.png",
                "thumbnail_doc_id": "thumb-2",
                "visual_embedding": [0.1, 0.2, 0.3],
                "visual_backend_type": "local_smoke",
                "late_interaction_tokens": ["revenue", "chart"],
            },
        }
    ]


def test_local_page_image_index_renders_pages_and_smoke_embeddings(tmp_path):
    pdf_path = tmp_path / "deck.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n% smoke fixture\n")

    def fake_renderer(path, pages, dpi):
        assert path == pdf_path
        assert pages == [0, 2]
        assert dpi == 120
        return [f"data:image/png;base64,page-{page}" for page in pages]

    records = build_local_page_image_records(
        [
            {
                "file_id": "file-1",
                "file_name": "deck.pdf",
                "path": str(pdf_path),
            }
        ],
        page_numbers=[1, 3],
        renderer=fake_renderer,
        text_extractor=lambda _path, page: f"Revenue chart page {page}.",
    )

    assert [record["page_label"] for record in records] == ["1", "3"]
    assert records[0]["page_image_path"] == "data:image/png;base64,page-0"
    assert records[0]["page_visual_embedding"]
    assert records[0]["late_interaction_tokens"] == ["chart", "page", "revenue"]
    assert records[0]["metadata"]["visual_backend_type"] == "local_smoke"
    assert records[0]["metadata"]["visual_embedding_model"] == (
        "deterministic_token_hash_v1"
    )


def test_visual_route_ranks_query_matching_page_images_across_documents():
    request = DocQARequest(
        prompt="What does the revenue chart show?",
        route_policy="visual",
        selected_file_ids=["file-a", "file-b"],
    )
    metadata = {
        "page_image_index": [
            {
                "evidence_id": "page-image:file-a:1",
                "file_id": "file-a",
                "file_name": "costs.pdf",
                "page_label": "1",
                "modality": "page_image",
                "text": "Cost trend figure.",
                "source_backrefs": ["file-a#page:1"],
            },
            {
                "evidence_id": "page-image:file-b:5",
                "file_id": "file-b",
                "file_name": "revenue.pdf",
                "page_label": "5",
                "modality": "page_image",
                "text": "Revenue chart shows product growth.",
                "source_backrefs": ["file-b#page:5"],
            },
        ]
    }

    bundle = build_evidence_bundle("doc_page_image", request, metadata)

    assert bundle.items[0]["evidence_id"] == "page-image:file-b:5"
    assert bundle.items[0]["modality"] == "page_image"
    assert bundle.metadata["modality_counts"] == {"page_image": 2}


def test_visual_route_uses_retriever_scores_and_late_interaction_tokens():
    request = DocQARequest(
        prompt="What does the revenue chart show?",
        route_policy="visual",
        selected_file_ids=["file-a", "file-b"],
    )
    metadata = {
        "page_image_index": [
            {
                "evidence_id": "page-image:file-a:1",
                "file_id": "file-a",
                "file_name": "hard-negative.pdf",
                "page_label": "1",
                "modality": "page_image",
                "text": "Revenue policy text without chart evidence.",
                "source_backrefs": ["file-a#page:1"],
            },
            {
                "evidence_id": "page-image:file-b:5",
                "file_id": "file-b",
                "file_name": "visual.pdf",
                "page_label": "5",
                "modality": "page_image",
                "text": "Visual page.",
                "source_backrefs": ["file-b#page:5"],
                "metadata": {
                    "late_interaction_tokens": ["revenue", "chart"],
                    "visual_retriever": "colpali-style",
                },
            },
        ],
        "visual_retriever_scores": {"page-image:file-b:5": 0.91},
    }

    bundle = build_evidence_bundle("doc_page_image", request, metadata)

    assert bundle.items[0]["evidence_id"] == "page-image:file-b:5"
    assert bundle.items[0]["metadata"]["visual_retriever_score"] == 0.91
    assert bundle.items[0]["metadata"]["visual_retriever"] == "colpali-style"


def test_local_late_interaction_visual_retriever_scores_page_tokens():
    records = [
        {
            "evidence_id": "page-image:file-a:1",
            "file_id": "file-a",
            "page_label": "1",
            "modality": "page_image",
            "text": "Revenue policy text hard negative.",
            "metadata": {"late_interaction_tokens": ["policy"]},
        },
        {
            "evidence_id": "page-image:file-b:5",
            "file_id": "file-b",
            "page_label": "5",
            "modality": "page_image",
            "text": "Visual page.",
            "metadata": {"late_interaction_tokens": ["revenue", "chart"]},
        },
    ]

    ranked, scores = rank_page_image_records(
        "What does the revenue chart show?",
        records,
        retriever=LocalLateInteractionVisualRetriever(),
    )

    assert ranked[0]["evidence_id"] == "page-image:file-b:5"
    assert scores["page-image:file-b:5"] > scores["page-image:file-a:1"]
    assert ranked[0]["metadata"]["visual_retriever"] == "local_late_interaction"
    assert ranked[0]["metadata"]["visual_retriever_backend_type"] == (
        "deterministic_smoke"
    )
    assert (
        ranked[0]["metadata"]["visual_retriever_score"] == scores["page-image:file-b:5"]
    )


def test_custom_visual_retriever_backend_can_override_page_ranking():
    class PreferFirstBackend:
        name = "fixture_visual_backend"

        def score(self, query, record):
            return 1.0 if record["evidence_id"] == "page-image:file-a:1" else 0.1

    records = [
        {
            "evidence_id": "page-image:file-a:1",
            "file_id": "file-a",
            "page_label": "1",
            "modality": "page_image",
            "text": "Visual page A.",
        },
        {
            "evidence_id": "page-image:file-b:5",
            "file_id": "file-b",
            "page_label": "5",
            "modality": "page_image",
            "text": "Visual page B.",
        },
    ]

    ranked, scores = rank_page_image_records(
        "question",
        records,
        retriever=PreferFirstBackend(),
    )

    assert ranked[0]["evidence_id"] == "page-image:file-a:1"
    assert scores == {"page-image:file-a:1": 1.0, "page-image:file-b:5": 0.1}
    assert ranked[0]["metadata"]["visual_retriever"] == "fixture_visual_backend"


def test_element_route_ranks_requested_element_type_before_other_elements():
    request = DocQARequest(
        prompt="Which table lists revenue by region?",
        route_policy="element",
        selected_file_ids=["file-1"],
    )
    metadata = {
        "element_index": [
            {
                "evidence_id": "element:file-1:2:figure-a",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "2",
                "element_id": "figure-a",
                "modality": "figure",
                "caption": "Revenue chart",
            },
            {
                "evidence_id": "element:file-1:4:table-a",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "element_id": "table-a",
                "modality": "table",
                "bbox": [10, 20, 30, 40],
                "caption": "Revenue by region",
            },
        ]
    }

    bundle = build_evidence_bundle("doc_element", request, metadata)

    assert bundle.items[0]["evidence_id"] == "element:file-1:4:table-a"
    assert bundle.items[0]["modality"] == "table"
    assert bundle.items[0]["bbox"] == [10, 20, 30, 40]


def test_element_index_records_preserve_layout_identity():
    docs = [
        RetrievedDocument(
            text="Revenue grew by region.",
            id_="table-doc",
            metadata={
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "4",
                "element_id": "table-4-a",
                "element_type": "table",
                "bbox": [10, 20, 30, 40],
                "caption": "Regional revenue",
            },
        )
    ]

    records = element_records_from_documents(docs)

    assert records == [
        {
            "evidence_id": "element:file-1:4:table-4-a",
            "file_id": "file-1",
            "file_name": "report.pdf",
            "page_label": "4",
            "element_id": "table-4-a",
            "modality": "table",
            "bbox": [10, 20, 30, 40],
            "caption": "Regional revenue",
            "text": "Revenue grew by region.",
            "source_backrefs": ["file-1#page:4"],
            "metadata": {},
        }
    ]


def test_hybrid_bundle_consumes_multimodal_index_metadata():
    request = DocQARequest(
        prompt="Compare the figure and table.", route_policy="hybrid"
    )
    metadata = {
        "evidence": [
            {
                "evidence_id": "text-1",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "3",
                "text": "Text evidence.",
            }
        ],
        "page_image_index": [
            {
                "evidence_id": "page-image:file-1:3",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "3",
                "modality": "page_image",
                "text": "Page OCR.",
                "source_backrefs": ["file-1#page:3"],
            }
        ],
        "element_index": [
            {
                "evidence_id": "element:file-1:3:figure-a",
                "file_id": "file-1",
                "file_name": "report.pdf",
                "page_label": "3",
                "element_id": "figure-a",
                "modality": "figure",
                "caption": "Growth chart",
                "text": "Figure evidence.",
            }
        ],
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert [item["modality"] for item in bundle.items] == [
        "text",
        "page_image",
        "figure",
    ]
    assert bundle.metadata["modality_counts"] == {
        "figure": 1,
        "page_image": 1,
        "text": 1,
    }


def test_hybrid_route_selects_page_first_multimodal_evidence_across_documents():
    request = DocQARequest(
        prompt="Explain the revenue chart and table.",
        route_policy="hybrid",
        selected_file_ids=["file-a", "file-b"],
    )
    metadata = {
        "evidence": [
            {
                "evidence_id": "text-a",
                "file_id": "file-a",
                "file_name": "policy.pdf",
                "page_label": "1",
                "text": "Revenue policy background.",
            },
            {
                "evidence_id": "text-b",
                "file_id": "file-b",
                "file_name": "results.pdf",
                "page_label": "5",
                "text": "Revenue chart and table summarize growth.",
            },
        ],
        "page_image_index": [
            {
                "evidence_id": "page-image:file-a:1",
                "file_id": "file-a",
                "file_name": "policy.pdf",
                "page_label": "1",
                "modality": "page_image",
                "text": "Policy page.",
            },
            {
                "evidence_id": "page-image:file-b:5",
                "file_id": "file-b",
                "file_name": "results.pdf",
                "page_label": "5",
                "modality": "page_image",
                "text": "Revenue chart visual.",
                "metadata": {"late_interaction_tokens": ["revenue", "chart"]},
            },
        ],
        "element_index": [
            {
                "evidence_id": "element:file-b:5:table-a",
                "file_id": "file-b",
                "file_name": "results.pdf",
                "page_label": "5",
                "element_id": "table-a",
                "modality": "table",
                "caption": "Revenue table",
            },
            {
                "evidence_id": "element:file-a:1:figure-a",
                "file_id": "file-a",
                "file_name": "policy.pdf",
                "page_label": "1",
                "element_id": "figure-a",
                "modality": "figure",
                "caption": "Policy figure",
            },
        ],
    }

    bundle = build_evidence_bundle("hybrid", request, metadata)

    assert bundle.metadata["m3docrag_trace"]["selected_pages"][0] == {
        "source_id": "file-b",
        "page_label": "5",
    }
    assert [item["evidence_id"] for item in bundle.items[:3]] == [
        "text-b",
        "page-image:file-b:5",
        "element:file-b:5:table-a",
    ]
