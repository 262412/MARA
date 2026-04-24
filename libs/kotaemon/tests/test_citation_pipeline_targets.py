from kotaemon.base import Document
import kotaemon.indices.qa.citation_qa as citation_qa_module
from kotaemon.indices.qa.citation import CiteEvidence
from kotaemon.indices.qa.citation_qa import AnswerWithContextPipeline


class FakeRender:
    @staticmethod
    def highlight(text, elem_id=None):
        return f"<mark data-id='{elem_id}'>{text}</mark>"

    @staticmethod
    def collapsible_with_header_score(
        doc,
        override_text=None,
        highlight_text=None,
        open_collapsible=False,
    ):
        return override_text or doc.text


def test_prepare_citations_attaches_structured_page_bbox_element_targets(monkeypatch):
    monkeypatch.setattr(citation_qa_module, "_get_render", lambda: FakeRender)
    pipeline = AnswerWithContextPipeline(
        citation_pipeline=lambda **kwargs: None,
        create_mindmap_pipeline=lambda **kwargs: None,
    )
    answer = Document(
        text="The relevant phrase is beta gamma.",
        metadata={
            "citation": CiteEvidence(evidences=["beta gamma"]),
            "citation_viz": False,
            "mindmap": None,
            "qa_score": None,
        },
    )
    source_doc = Document(
        text="Alpha beta gamma delta",
        id_="doc-1",
        metadata={
            "source_id": "source-1",
            "file_name": "paper.pdf",
            "page_number": 3,
            "bbox": "[1, 2, 3, 4]",
            "element_id": "element-1",
            "element_type": "formula",
        },
    )

    with_citation, _ = pipeline.prepare_citations(answer, [source_doc])

    target = with_citation[0].metadata["citation_targets"][0]
    assert target["doc_id"] == "doc-1"
    assert target["source_id"] == "source-1"
    assert target["file_name"] == "paper.pdf"
    assert target["page_number"] == 3
    assert target["bbox"] == (1.0, 2.0, 3.0, 4.0)
    assert target["element_id"] == "element-1"
    assert target["element_type"] == "formula"
    assert target["span_start"] == 6
    assert target["span_end"] == 16
    assert target["highlight_text"] == "beta gamma"
    assert answer.metadata["citation_targets"] == [target]
