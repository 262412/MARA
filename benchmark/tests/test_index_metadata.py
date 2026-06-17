from benchmark.docqa_evidence_projection import retrieved_hits_from_docqa_evidence
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
            "document_id": "paper-1",
            "source_id": "paper-1",
            "source_name": "paper.pdf",
            "page_label": "3",
            "text": "The method improves recall.",
            "source_backrefs": ["paper-1#page:3"],
        }
    ]
