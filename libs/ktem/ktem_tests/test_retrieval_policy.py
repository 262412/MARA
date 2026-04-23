from kotaemon.base import RetrievedDocument

from ktem.reasoning.retrieval_policy import apply_retrieval_policy


def _doc(
    doc_id: str,
    file_id: str,
    page_label: int | str,
    text: str | None = None,
    file_name: str | None = None,
) -> RetrievedDocument:
    return RetrievedDocument(
        text=text or f"{file_id} page {page_label}",
        id_=doc_id,
        metadata={
            "file_id": file_id,
            "file_name": file_name or f"{file_id}.pdf",
            "page_label": str(page_label),
        },
    )


def test_page_scope_prefers_active_file_current_page_then_active_file_fallback():
    docs = [
        _doc("other-page", "other", 2),
        _doc("active-page-1", "active", 1),
        _doc("active-page-2", "active", 2),
    ]

    scoped = apply_retrieval_policy(
        docs,
        qa_scope="page",
        active_file_id="active",
        active_file_name="active.pdf",
        page_number=2,
    )

    assert [doc.doc_id for doc in scoped] == ["active-page-2"]

    fallback = apply_retrieval_policy(
        docs,
        qa_scope="page",
        active_file_id="active",
        active_file_name="active.pdf",
        page_number=9,
    )

    assert [doc.doc_id for doc in fallback] == ["active-page-1", "active-page-2"]


def test_document_scope_prefers_active_file_without_current_page_lock():
    docs = [
        _doc("active-page-1", "active", 1),
        _doc("active-page-2", "active", 2),
        _doc("other-page-2", "other", 2),
    ]

    scoped = apply_retrieval_policy(
        docs,
        qa_scope="document",
        active_file_id="active",
        active_file_name="active.pdf",
        page_number=2,
    )

    assert [doc.doc_id for doc in scoped] == ["active-page-1", "active-page-2"]


def test_multi_document_round_robins_by_file_without_dropping_results_by_default():
    docs = [
        _doc("a1", "a", 1),
        _doc("a2", "a", 2),
        _doc("a3", "a", 3),
        _doc("b1", "b", 1),
        _doc("c1", "c", 1),
    ]

    scoped = apply_retrieval_policy(docs, qa_scope="multi_document")

    assert [doc.doc_id for doc in scoped] == ["a1", "b1", "c1", "a2", "a3"]

    top_k = apply_retrieval_policy(docs, qa_scope="multi_document", top_k=3)

    assert [doc.doc_id for doc in top_k] == ["a1", "b1", "c1"]


def test_selected_text_replaces_matching_scoped_doc_or_synthesizes_doc():
    docs = [
        _doc("active-1", "active", 1, text="alpha selected passage beta"),
        _doc("active-2", "active", 2, text="different text"),
    ]

    scoped = apply_retrieval_policy(
        docs,
        qa_scope="document",
        active_file_id="active",
        selected_text="selected passage",
    )

    assert len(scoped) == 1
    assert scoped[0].doc_id == "active-1"
    assert scoped[0].text == "selected passage"
    assert docs[0].text == "alpha selected passage beta"

    synthesized = apply_retrieval_policy(
        [],
        qa_scope="document",
        active_file_id="active",
        active_file_name="active.pdf",
        selected_text="selected passage",
    )

    assert len(synthesized) == 1
    assert synthesized[0].text == "selected passage"
    assert synthesized[0].metadata["file_id"] == "active"
