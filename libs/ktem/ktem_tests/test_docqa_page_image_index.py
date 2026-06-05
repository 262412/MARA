from ktem.docqa.multimodal_index import page_image_records_from_documents

from kotaemon.base import RetrievedDocument


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
            metadata={"file_id": "file-1", "file_name": "deck.pdf", "page_label": "2"},
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
            "rendered_page_image": "/tmp/deck-page-2.png",
            "page_visual_embedding": [0.1, 0.2, 0.3],
            "visual_embedding": [0.1, 0.2, 0.3],
            "late_interaction_tokens": ["revenue", "chart"],
            "multi_vector_representation": ["revenue", "chart"],
            "page_level_score": None,
            "retrieved_page_evidence": {
                "text": "Paragraph on page 2.",
                "source_backrefs": ["file-1#page:2"],
            },
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
                "multi_vector_representation": ["revenue", "chart"],
                "retrieved_page_evidence": {
                    "text": "Paragraph on page 2.",
                    "source_backrefs": ["file-1#page:2"],
                },
            },
        }
    ]


def test_page_image_index_persists_colpali_multivector_fields():
    docs = [
        RetrievedDocument(
            text="",
            id_="thumb-7",
            metadata={
                "type": "thumbnail",
                "file_id": "file-1",
                "file_name": "deck.pdf",
                "page_label": "7",
                "rendered_page_image": "/tmp/deck-page-7.png",
                "visual_embedding": [0.7, 0.1],
                "multi_vector_representation": [[0.1, 0.2], [0.3, 0.4]],
                "page_level_score": 0.82,
                "visual_retriever": "colpali",
                "visual_backend_type": "colvision_multi_vector",
            },
        ),
        RetrievedDocument(
            text="Figure evidence on page 7.",
            id_="chunk-7",
            metadata={"file_id": "file-1", "file_name": "deck.pdf", "page_label": "7"},
        ),
    ]

    record = page_image_records_from_documents(docs)[0]

    assert record["rendered_page_image"] == "/tmp/deck-page-7.png"
    assert record["visual_embedding"] == [0.7, 0.1]
    assert record["multi_vector_representation"] == [[0.1, 0.2], [0.3, 0.4]]
    assert record["page_level_score"] == 0.82
    assert record["retrieved_page_evidence"] == {
        "text": "Figure evidence on page 7.",
        "source_backrefs": ["file-1#page:7"],
    }
    assert record["metadata"]["visual_retriever"] == "colpali"
