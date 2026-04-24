from kotaemon.base import Document
from kotaemon.indices.extractors import ElementDocParser


def test_element_doc_parser_adds_page_parent_and_neighbors():
    documents = [
        Document(
            text="First paragraph.",
            metadata={
                "source_id": "source-1",
                "file_name": "paper.pdf",
                "page_number": 1,
            },
        ),
        Document(
            text="Second paragraph.",
            metadata={
                "source_id": "source-1",
                "file_name": "paper.pdf",
                "page_number": 1,
            },
        ),
        Document(
            text="Other page.",
            metadata={
                "source_id": "source-1",
                "file_name": "paper.pdf",
                "page_number": 2,
            },
        ),
    ]

    parsed = ElementDocParser().run(documents)

    normal_docs = [doc for doc in parsed if doc.metadata["element_type"] != "page"]
    page_docs = [doc for doc in parsed if doc.metadata["element_type"] == "page"]
    first, second, other_page = normal_docs
    page_one = next(doc for doc in page_docs if doc.metadata["page_number"] == 1)
    page_two = next(doc for doc in page_docs if doc.metadata["page_number"] == 2)

    assert len(page_docs) == 2
    assert page_one.text == "First paragraph.\nSecond paragraph."
    assert page_two.text == "Other page."
    assert page_one.metadata["type"] == "page"

    assert first.metadata["parent_element_id"] == page_one.metadata["element_id"]
    assert second.metadata["parent_element_id"] == page_one.metadata["element_id"]
    assert other_page.metadata["parent_element_id"] == page_two.metadata["element_id"]

    assert first.metadata["neighbor_element_ids"] == {
        "next": second.metadata["element_id"]
    }
    assert second.metadata["neighbor_element_ids"] == {
        "previous": first.metadata["element_id"]
    }
    assert "neighbor_element_ids" not in other_page.metadata


def test_element_doc_parser_preserves_existing_element_id_and_parent():
    document = Document(
        text="Existing element.",
        metadata={
            "element_id": "existing-id",
            "parent_element_id": "existing-parent",
            "source_id": "source-2",
            "file_name": "paper.pdf",
            "page_label": "iii",
        },
    )

    parsed = ElementDocParser().run([document])
    normal_doc = next(doc for doc in parsed if doc.metadata["element_type"] != "page")

    assert normal_doc.metadata["element_id"] == "existing-id"
    assert normal_doc.metadata["parent_element_id"] == "existing-parent"
