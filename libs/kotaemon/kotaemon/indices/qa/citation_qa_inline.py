import logging
import threading
from typing import Generator

import numpy as np

from kotaemon.base import Document
from kotaemon.llms import PromptTemplate

from .citation_qa import (
    CITATION_TIMEOUT,
    AnswerWithContextPipeline,
    _llm_generation_kwargs,
)
from .citation_qa_inline_helpers import (
    START_ANSWER,
    START_CITATION,
    InlineEvidence,
    answer_to_citations,
    build_inline_messages,
    match_evidence_with_context,
    replace_citation_with_link,
)

logger = logging.getLogger(__name__)

DEFAULT_QA_CITATION_PROMPT = """
Use the following pieces of context to answer the question at the end.
Provide DETAILED ansswer with clear explanation.
Return the FINAL ANSWER as Markdown, not raw HTML. Do not return one unbroken paragraph; put a blank line between paragraphs, headings, lists, formulas, and tables.
If the user asks for a table, comparison, matrix, or summary table, you MUST include a Markdown table with a header and separator row, e.g. | Aspect | Summary | and | --- | --- |.
Put a blank line before and after each table; never write pipe-delimited table rows inline inside a paragraph.
For mathematical formulas and equations, use LaTeX with $...$ for inline math and $$...$$ for display math. Do not use backticks for mathematical variables or equations.
For code, use fenced Markdown code blocks with triple backticks such as ```python when a language tag is clear.
If you don't know the answer, just say that you don't know, don't try to make up an answer.
Use the same language as the question to response.

CONTEXT:
----
{context}
----

Answer using this format:
CITATION LIST

// the index in this array
CITATION【number】

// output 2 phrase to mark start and end of the relevant span
// each has ~ 6 words
// MUST COPY EXACTLY from the CONTEXT
// NO CHANGE or REPHRASE
// RELEVANT_SPAN_FROM_CONTEXT
START_PHRASE: string
END_PHRASE: string

// When you answer, ensure to add citations from the documents
// in the CONTEXT with a number that corresponds to the answersInText array.
// (in the form [number])
// Try to include the number after each facts / statements you make.
// You can create as many citations as you need.
FINAL ANSWER
string

STRICTLY FOLLOW THIS EXAMPLE:
CITATION LIST

CITATION【1】

START_PHRASE: Known as fixed-size chunking , the traditional
END_PHRASE: not degrade the final retrieval performance.

CITATION【2】

START_PHRASE: Fixed-size Chunker This is our baseline chunker
END_PHRASE: this shows good retrieval quality.

FINAL ANSWER
An alternative to semantic chunking is fixed-size chunking. This traditional method involves splitting documents into chunks of a predetermined or user-specified size, regardless of semantic content, which is computationally efficient【1】. However, it may result in the fragmentation of semantically related content, thereby potentially degrading retrieval performance【1】【2】.

QUESTION: {question}\n
ANSWER:
"""  # noqa


class AnswerWithInlineCitation(AnswerWithContextPipeline):
    """Answer the question based on the evidence with inline citation"""

    qa_citation_template: str = DEFAULT_QA_CITATION_PROMPT

    def get_prompt(self, question, evidence, evidence_mode: int):
        """Prepare the prompt and other information for LLM"""
        prompt_template = PromptTemplate(self.qa_citation_template)

        prompt = prompt_template.populate(
            context=evidence,
            question=question,
            safe=False,
        )

        return prompt, evidence

    def answer_to_citations(self, answer) -> list[InlineEvidence]:
        return answer_to_citations(answer)

    def replace_citation_with_link(self, answer: str):
        return replace_citation_with_link(answer)

    def stream(  # type: ignore
        self,
        question: str,
        evidence: str,
        evidence_mode: int = 0,
        images: list[str] = [],
        **kwargs,
    ) -> Generator[Document, None, Document]:
        history = kwargs.get("history", [])
        logger.debug("Got %d images for inline citation QA", len(images))
        # check if evidence exists, use QA prompt
        if evidence:
            prompt, evidence = self.get_prompt(question, evidence, evidence_mode)
        else:
            prompt = question

        output = ""
        logprobs = []

        citation = None
        mindmap = None

        def mindmap_call():
            nonlocal mindmap
            mindmap = self.create_mindmap_pipeline(context=evidence, question=question)

        mindmap_thread = None

        # execute function call in thread
        if evidence:
            if self.enable_mindmap:
                mindmap_thread = threading.Thread(target=mindmap_call)
                mindmap_thread.start()

        messages = build_inline_messages(self, history, prompt, evidence_mode, images)

        final_answer = ""

        try:
            # try streaming first
            logger.debug("Trying LLM streaming for inline citation QA")
            generation_kwargs = _llm_generation_kwargs(kwargs)
            for out_msg in self.llm.stream(messages, **generation_kwargs):
                if evidence:
                    if START_ANSWER in output:
                        if not final_answer:
                            try:
                                left_over_answer = output.split(START_ANSWER)[
                                    1
                                ].lstrip()
                            except IndexError:
                                left_over_answer = ""
                            if left_over_answer:
                                out_msg.text = left_over_answer + out_msg.text

                        final_answer += (
                            out_msg.text.lstrip() if not final_answer else out_msg.text
                        )
                        yield Document(channel="chat", content=out_msg.text)

                        # check for the edge case of citation list is repeated
                        # with smaller LLMs
                        if START_CITATION in out_msg.text:
                            break
                else:
                    yield Document(channel="chat", content=out_msg.text)

                output += out_msg.text
                logprobs += out_msg.logprobs
        except NotImplementedError:
            logger.debug(
                "Streaming is not supported for inline citation QA; falling back"
            )
            output = self.llm(messages, **generation_kwargs).text
            yield Document(channel="chat", content=output)

        if logprobs:
            qa_score = np.exp(np.average(logprobs))
        else:
            qa_score = None

        citation = self.answer_to_citations(output)

        if mindmap_thread:
            mindmap_thread.join(timeout=CITATION_TIMEOUT)

        claim_verification = None
        answer_text = final_answer or output
        if kwargs.get("enable_claim_verification", self.enable_claim_verification):
            source_documents = kwargs.get("source_documents") or []
            claim_verification, verified_answer = self.verify_answer_claims(
                answer_text=answer_text,
                evidence=evidence,
                source_documents=source_documents,
                claim_verifier=kwargs.get("claim_verifier"),
            )
            if verified_answer != answer_text:
                if self._should_keep_original_after_verification(
                    evidence_mode=evidence_mode,
                    images=images,
                    source_documents=source_documents,
                    question=question,
                    answer_text=answer_text,
                ):
                    if claim_verification is None:
                        claim_verification = {}
                    claim_verification["rewrite_skipped"] = True
                    claim_verification[
                        "rewrite_skip_reason"
                    ] = "multimodal_or_formula_evidence"
                else:
                    final_answer = verified_answer
                    answer_text = verified_answer

        answer_metadata = {
            "citation_viz": self.enable_citation_viz,
            "mindmap": mindmap,
            "citation": citation,
            "qa_score": qa_score,
        }
        if claim_verification is not None:
            answer_metadata["claim_verification"] = claim_verification

        # convert citation to link
        answer = Document(
            text=answer_text,
            metadata=answer_metadata,
        )

        # yield the final answer
        final_answer = self.replace_citation_with_link(answer_text)

        if final_answer:
            yield Document(channel="chat", content=None)
            yield Document(channel="chat", content=final_answer)

        return answer

    def match_evidence_with_context(self, answer, docs) -> dict[str, list[dict]]:
        """Match the evidence with the context."""
        return match_evidence_with_context(answer, docs)
