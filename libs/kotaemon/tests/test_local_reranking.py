from kotaemon.base import Document
from kotaemon.indices.rankings import LocalMultilingualReranking


def test_local_multilingual_reranking_scores_multilingual_element_fields():
    documents = [
        Document(
            text="Appendix with unrelated notes",
            metadata={"element_type": "text"},
        ),
        Document(
            text="Revenue increased in 2024",
            metadata={
                "element_type": "table",
                "caption": "\u5e74\u5ea6\u8425\u6536\u660e\u7ec6",
                "table_origin": "\u5730\u533a \u8425\u6536 2024",
            },
        ),
        Document(
            text="Only English revenue discussion",
            metadata={"element_type": "text"},
        ),
    ]

    reranked = LocalMultilingualReranking().run(
        documents, query="2024 \u8425\u6536 revenue"
    )

    assert reranked == [documents[1], documents[2], documents[0]]
    assert len(reranked) == len(documents)
    assert reranked[0].metadata["local_reranking_score"] > 0
    assert (
        reranked[1].metadata["local_reranking_score"]
        > reranked[2].metadata["local_reranking_score"]
    )


def test_local_multilingual_reranking_boosts_routed_element_types():
    documents = [
        Document(
            text="Revenue trend by region",
            metadata={"element_type": "text"},
        ),
        Document(
            text="Revenue trend by region",
            metadata={"type": "table"},
        ),
        Document(
            text="Revenue trend by region",
            metadata={"element_type": "figure"},
        ),
    ]

    reranked = LocalMultilingualReranking().run(
        documents, query="show revenue trend table"
    )

    assert reranked[0] is documents[1]
    assert reranked[1:] == [documents[0], documents[2]]


def test_local_multilingual_reranking_uses_formula_and_ocr_metadata_and_is_stable():
    documents = [
        Document(
            text="",
            metadata={
                "element_type": "formula",
                "normalized_formula": "E = mc 2",
            },
        ),
        Document(
            text="",
            metadata={
                "element_type": "figure",
                "ocr_text": "\u80fd\u91cf equation label",
            },
        ),
        Document(
            text="",
            metadata={
                "element_type": "figure",
                "ocr_text": "\u80fd\u91cf equation label",
            },
        ),
    ]

    reranked = LocalMultilingualReranking().run(
        documents, query="\u80fd\u91cf equation figure"
    )

    assert reranked == [documents[1], documents[2], documents[0]]
    assert (
        reranked[1].metadata["local_reranking_score"]
        == reranked[0].metadata["local_reranking_score"]
    )
