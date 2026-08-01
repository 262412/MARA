from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from kotaemon.base import Document, LLMInterface
from kotaemon.indices.qa.citation import (
    CitationPipeline,
    CitationToolCallConfigurationError,
)
from kotaemon.indices.qa.citation_qa import AnswerWithContextPipeline
from kotaemon.indices.qa.citation_qa_inline import AnswerWithInlineCitation
from kotaemon.indices.qa.format_context import EVIDENCE_MODE_FIGURE
from kotaemon.llms import ChatLLM


class FakeStreamingLLM(ChatLLM):
    chunks: list[str] = []

    def invoke(self, messages):
        return LLMInterface(content="".join(self.chunks), logprobs=[])

    def stream(self, messages):
        for chunk in self.chunks:
            yield LLMInterface(content=chunk, logprobs=[])


@dataclass
class FakeClaimVerifier:
    result: dict[str, Any]
    calls: list[dict[str, Any]]

    def __call__(self, *args, **kwargs):
        self.calls.append({"args": args, "kwargs": kwargs})
        return self.result

    def verify(self, *args, **kwargs):
        return self(*args, **kwargs)


def _pipeline_for(answer: str) -> AnswerWithContextPipeline:
    return AnswerWithContextPipeline(
        llm=FakeStreamingLLM(chunks=[answer[:12], answer[12:]]),
        citation_pipeline=lambda **kwargs: None,
        create_mindmap_pipeline=lambda **kwargs: None,
    )


def _inline_pipeline_for(answer: str) -> AnswerWithInlineCitation:
    inline_answer = f"FINAL ANSWER\n{answer}"
    return AnswerWithInlineCitation(
        llm=FakeStreamingLLM(chunks=[inline_answer[:12], inline_answer[12:]]),
        citation_pipeline=lambda **kwargs: None,
        create_mindmap_pipeline=lambda **kwargs: None,
    )


def _consume_stream(generator):
    streamed = []
    while True:
        try:
            streamed.append(next(generator))
        except StopIteration as exc:
            return streamed, exc.value


def _claim_verification_metadata(answer: Document) -> dict[str, Any]:
    metadata = answer.metadata or {}
    assert "claim_verification" in metadata, (
        "claim verification is enabled, so final answer metadata must include "
        "'claim_verification'"
    )
    claim_verification = metadata["claim_verification"]
    assert isinstance(
        claim_verification, dict
    ), "claim_verification metadata must be a dict with a 'claims' list"
    assert isinstance(
        claim_verification.get("claims"), list
    ), "claim_verification metadata must include a 'claims' list"
    return claim_verification


def _claims_with_status(
    claim_verification: dict[str, Any], status: str
) -> list[dict[str, Any]]:
    return [
        claim for claim in claim_verification["claims"] if claim.get("status") == status
    ]


def test_stream_surfaces_citation_tool_call_configuration_errors():
    class ToolCallBadRequest(Exception):
        status_code = 400

    class MisconfiguredLLM(ChatLLM):
        def invoke(self, _messages, **_kwargs):
            raise ToolCallBadRequest(
                'tool_choice="required" requires --tool-call-parser to be set'
            )

    pipeline = AnswerWithContextPipeline(
        llm=FakeStreamingLLM(chunks=["Supported answer."]),
        citation_pipeline=CitationPipeline(llm=MisconfiguredLLM()),
        create_mindmap_pipeline=lambda **kwargs: None,
        enable_citation=True,
        enable_claim_verification=False,
    )

    with pytest.raises(CitationToolCallConfigurationError):
        _consume_stream(
            pipeline.stream(
                question="What is supported?",
                evidence="Supported answer.",
            )
        )


def test_stream_records_supported_claim_when_claim_verification_enabled():
    answer_text = "Cinnamon AI is an enterprise AI company based in Japan."
    supported_claim = "Cinnamon AI is an enterprise AI company based in Japan."
    verifier = FakeClaimVerifier(
        result={
            "claims": [
                {
                    "text": supported_claim,
                    "status": "supported",
                    "evidence": [
                        "Cinnamon AI is an enterprise AI company based in Japan."
                    ],
                }
            ],
            "revised_answer": answer_text,
        },
        calls=[],
    )
    source_documents = [
        Document(
            text="Cinnamon AI is an enterprise AI company based in Japan.",
            metadata={"source": "company-profile"},
        )
    ]

    _, final_answer = _consume_stream(
        _pipeline_for(answer_text).stream(
            question="What is Cinnamon AI?",
            evidence=source_documents[0].text,
            source_documents=source_documents,
            enable_claim_verification=True,
            claim_verifier=verifier,
        )
    )

    assert final_answer.text == answer_text
    claim_verification = _claim_verification_metadata(final_answer)
    supported = _claims_with_status(claim_verification, "supported")
    assert any(
        claim.get("text") == supported_claim for claim in supported
    ), "claim_verification metadata must retain the supported claim"
    assert verifier.calls, "claim verifier must be invoked when verification is enabled"


def test_stream_revises_or_abstains_when_claim_verification_finds_unsupported_claim():
    unsupported_answer = "The refund policy allows refunds within 90 days."
    unsupported_claim = "The refund policy allows refunds within 90 days."
    revised_answer = "The refund policy allows refunds within 30 days."
    verifier = FakeClaimVerifier(
        result={
            "claims": [
                {
                    "text": unsupported_claim,
                    "status": "unsupported",
                    "evidence": [],
                }
            ],
            "revised_answer": revised_answer,
        },
        calls=[],
    )
    source_documents = [
        Document(
            text="The refund policy allows refunds within 30 days.",
            metadata={"source": "refund-policy"},
        )
    ]

    _, final_answer = _consume_stream(
        _pipeline_for(unsupported_answer).stream(
            question="What does the refund policy allow?",
            evidence=source_documents[0].text,
            source_documents=source_documents,
            enable_claim_verification=True,
            claim_verifier=verifier,
        )
    )

    claim_verification = _claim_verification_metadata(final_answer)
    unsupported = _claims_with_status(claim_verification, "unsupported")
    assert any(
        claim.get("text") == unsupported_claim for claim in unsupported
    ), "claim_verification metadata must record unsupported claims"
    assert unsupported_claim not in final_answer.text
    assert final_answer.text == revised_answer or any(
        phrase in final_answer.text.lower()
        for phrase in [
            "don't know",
            "do not know",
            "not enough evidence",
            "unable to answer",
        ]
    ), "unsupported claims must be revised away or the final answer must abstain"
    assert verifier.calls, "claim verifier must be invoked when verification is enabled"


def test_stream_omits_claim_verification_metadata_when_disabled():
    answer_text = "The refund policy allows refunds within 90 days."
    verifier = FakeClaimVerifier(
        result={
            "claims": [
                {
                    "text": answer_text,
                    "status": "unsupported",
                    "evidence": [],
                }
            ],
            "revised_answer": "The refund policy allows refunds within 30 days.",
        },
        calls=[],
    )
    source_documents = [
        Document(
            text="The refund policy allows refunds within 30 days.",
            metadata={"source": "refund-policy"},
        )
    ]

    streamed, final_answer = _consume_stream(
        _pipeline_for(answer_text).stream(
            question="What does the refund policy allow?",
            evidence=source_documents[0].text,
            source_documents=source_documents,
            enable_claim_verification=False,
            claim_verifier=verifier,
        )
    )

    assert "".join(chunk.content for chunk in streamed) == answer_text
    assert final_answer.text == answer_text
    assert "claim_verification" not in (final_answer.metadata or {})
    assert verifier.calls == []


def test_stream_does_not_replace_multimodal_answer_with_text_only_abstention():
    answer_text = "The figure shows an encoder feeding a decoder through attention."
    abstention = "文档证据无法支持该回答。"
    verifier = FakeClaimVerifier(
        result={
            "claims": [
                {
                    "text": answer_text,
                    "status": "unsupported",
                    "evidence": [],
                }
            ],
            "revised_answer": abstention,
        },
        calls=[],
    )
    source_documents = [
        Document(
            text="",
            metadata={
                "element_type": "figure",
                "image_origin": "data:image/png;base64,abc",
                "caption": "Architecture diagram",
            },
        )
    ]

    streamed, final_answer = _consume_stream(
        _pipeline_for(answer_text).stream(
            question="What does the figure show?",
            evidence="<b>Figure from paper.pdf</b>",
            evidence_mode=EVIDENCE_MODE_FIGURE,
            images=["data:image/png;base64,abc"],
            source_documents=source_documents,
            enable_claim_verification=True,
            claim_verifier=verifier,
        )
    )

    assert final_answer.text == answer_text
    assert all(chunk.content is not None for chunk in streamed)
    metadata = _claim_verification_metadata(final_answer)
    assert metadata["revised_answer"] == abstention
    assert metadata["rewrite_skipped"] is True
    assert metadata["rewrite_skip_reason"] == "multimodal_or_formula_evidence"


def test_inline_stream_does_not_replace_multimodal_answer_with_text_only_abstention():
    answer_text = "The figure shows an encoder feeding a decoder through attention."
    abstention = "Document evidence cannot support this answer."
    verifier = FakeClaimVerifier(
        result={
            "claims": [
                {
                    "text": answer_text,
                    "status": "unsupported",
                    "evidence": [],
                }
            ],
            "revised_answer": abstention,
        },
        calls=[],
    )
    source_documents = [
        Document(
            text="",
            metadata={
                "element_type": "figure",
                "image_origin": "data:image/png;base64,abc",
                "caption": "Architecture diagram",
            },
        )
    ]

    streamed, final_answer = _consume_stream(
        _inline_pipeline_for(answer_text).stream(
            question="What does the figure show?",
            evidence="<b>Figure from paper.pdf</b>",
            evidence_mode=EVIDENCE_MODE_FIGURE,
            images=["data:image/png;base64,abc"],
            source_documents=source_documents,
            enable_claim_verification=True,
            claim_verifier=verifier,
        )
    )

    assert final_answer.text == answer_text
    assert streamed[-1].content == answer_text
    metadata = _claim_verification_metadata(final_answer)
    assert metadata["revised_answer"] == abstention
    assert metadata["rewrite_skipped"] is True
    assert metadata["rewrite_skip_reason"] == "multimodal_or_formula_evidence"


def test_stream_does_not_replace_page_thumbnail_visual_answer_with_text_only_abstention():
    answer_text = "The diagram shows three labeled boxes connected by arrows."
    abstention = "Document evidence cannot support this answer."
    verifier = FakeClaimVerifier(
        result={
            "claims": [
                {
                    "text": answer_text,
                    "status": "unsupported",
                    "evidence": [],
                }
            ],
            "revised_answer": abstention,
        },
        calls=[],
    )
    source_documents = [
        Document(
            text="Input Encoder Decoder",
            metadata={
                "type": "text",
                "element_type": "text",
                "page_label": "1",
                "thumbnail_doc_id": "thumb-page-1",
            },
        )
    ]

    streamed, final_answer = _consume_stream(
        _pipeline_for(answer_text).stream(
            question="What does the diagram on this page show?",
            evidence="<b>Content from paper.pdf (Page 1):</b> Input Encoder Decoder",
            source_documents=source_documents,
            enable_claim_verification=True,
            claim_verifier=verifier,
        )
    )

    assert final_answer.text == answer_text
    assert all(chunk.content is not None for chunk in streamed)
    metadata = _claim_verification_metadata(final_answer)
    assert metadata["revised_answer"] == abstention
    assert metadata["rewrite_skipped"] is True
    assert metadata["rewrite_skip_reason"] == "multimodal_or_formula_evidence"


def test_inline_stream_does_not_replace_page_thumbnail_visual_answer_with_text_only_abstention():
    answer_text = "The flowchart has a start box, a decision box, and an output box."
    abstention = "Document evidence cannot support this answer."
    verifier = FakeClaimVerifier(
        result={
            "claims": [
                {
                    "text": answer_text,
                    "status": "unsupported",
                    "evidence": [],
                }
            ],
            "revised_answer": abstention,
        },
        calls=[],
    )
    source_documents = [
        Document(
            text="Start Decision Output",
            metadata={
                "type": "text",
                "element_type": "text",
                "page_label": "2",
                "thumbnail_doc_id": "thumb-page-2",
            },
        )
    ]

    streamed, final_answer = _consume_stream(
        _inline_pipeline_for(answer_text).stream(
            question="Explain the flowchart on this page.",
            evidence="<b>Content from paper.pdf (Page 2):</b> Start Decision Output",
            source_documents=source_documents,
            enable_claim_verification=True,
            claim_verifier=verifier,
        )
    )

    assert final_answer.text == answer_text
    assert streamed[-1].content == answer_text
    metadata = _claim_verification_metadata(final_answer)
    assert metadata["revised_answer"] == abstention
    assert metadata["rewrite_skipped"] is True
    assert metadata["rewrite_skip_reason"] == "multimodal_or_formula_evidence"


def test_stream_still_replaces_nonvisual_page_thumbnail_answer_when_unsupported():
    answer_text = "The refund policy allows refunds within 90 days."
    revised_answer = "The refund policy allows refunds within 30 days."
    verifier = FakeClaimVerifier(
        result={
            "claims": [
                {
                    "text": answer_text,
                    "status": "unsupported",
                    "evidence": [],
                }
            ],
            "revised_answer": revised_answer,
        },
        calls=[],
    )
    source_documents = [
        Document(
            text="The refund policy allows refunds within 30 days.",
            metadata={
                "type": "text",
                "element_type": "text",
                "page_label": "3",
                "thumbnail_doc_id": "thumb-page-3",
            },
        )
    ]

    _, final_answer = _consume_stream(
        _pipeline_for(answer_text).stream(
            question="What does the refund policy allow?",
            evidence=source_documents[0].text,
            source_documents=source_documents,
            enable_claim_verification=True,
            claim_verifier=verifier,
        )
    )

    assert final_answer.text == revised_answer
    metadata = _claim_verification_metadata(final_answer)
    assert "rewrite_skipped" not in metadata
