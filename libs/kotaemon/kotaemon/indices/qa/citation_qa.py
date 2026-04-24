import logging
import threading
from collections import defaultdict
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Generator

import numpy as np
from decouple import config
from theflow.settings import settings as flowsettings

from kotaemon.base import (
    AIMessage,
    BaseComponent,
    Document,
    HumanMessage,
    Node,
    SystemMessage,
)
from kotaemon.llms import ChatLLM, PromptTemplate

from .citation import CitationPipeline
from .citation_refs import citation_target_from_document, citation_targets_from_spans
from .claim_verification import revise_or_abstain, verify_claims
from .format_context import (
    EVIDENCE_MODE_FIGURE,
    EVIDENCE_MODE_TABLE,
    EVIDENCE_MODE_TEXT,
)
from .utils import find_text

MAX_IMAGES = 10
CITATION_TIMEOUT = 5.0
CONTEXT_RELEVANT_WARNING_SCORE = config(
    "CONTEXT_RELEVANT_WARNING_SCORE", 0.3, cast=float
)
logger = logging.getLogger(__name__)

_PAGE_VISUAL_CONTEXT_KEYS = (
    "thumbnail_doc_id",
    "page_thumbnail_doc_id",
    "page_image_origin",
    "page_image",
    "preview_image",
    "rendered_page_image",
)
_VISUAL_CONTEXT_TERMS = (
    "figure",
    "fig.",
    "image",
    "diagram",
    "chart",
    "graph",
    "flowchart",
    "plot",
    "box",
    "arrow",
    "node",
    "edge",
    "layout",
    "visual",
    "\u56fe",
    "\u56fe\u7247",
    "\u56fe\u50cf",
    "\u56fe\u793a",
    "\u793a\u610f\u56fe",
    "\u6d41\u7a0b\u56fe",
    "\u7ed3\u6784\u56fe",
    "\u6846",
    "\u7ebf\u6846",
    "\u7bad\u5934",
    "\u8282\u70b9",
    "\u5e03\u5c40",
)


def _looks_like_visual_question_or_answer(*texts: str) -> bool:
    combined = " ".join(str(text or "").casefold() for text in texts)
    return any(term in combined for term in _VISUAL_CONTEXT_TERMS)


def _get_default_llm():
    try:
        from ktem.llms.manager import llms
    except ImportError as exc:
        raise ImportError(
            "Please install `ktem` to use the default QA runtime."
        ) from exc

    return llms.get_default()


def _create_default_mindmap_pipeline():
    try:
        from ktem.reasoning.prompt_optimization.mindmap import CreateMindmapPipeline
    except ImportError as exc:
        raise ImportError(
            "Please install `ktem` to enable mindmap generation."
        ) from exc

    return CreateMindmapPipeline(llm=_get_default_llm())


def _get_render():
    try:
        from ktem.utils.render import Render
    except ImportError as exc:
        raise ImportError("Please install `ktem` to render QA citations.") from exc

    return Render


DEFAULT_QA_TEXT_PROMPT = (
    "Use the following pieces of context to answer the question at the end in detail with clear explanation. "  # noqa: E501
    "If you don't know the answer, just say that you don't know, don't try to "
    "make up an answer. "
    "Use rich formatting in your answer: use markdown tables, bullet points, "
    "numbered lists, and headings where appropriate to make the answer clear and structured. "
    "For mathematical formulas and equations, ALWAYS use LaTeX format with $...$ for inline math (e.g., $w = (X^T X)^{{-1}} X^T d$) or $$...$$ for display math. "
    "Examples of correct LaTeX formatting: "
    "  - $w_{{n+1}} = (X_n^T X_n)^{{-1}} X_n^T d_n$ (subscripts and superscripts) "
    "  - $\\alpha^2$ (Greek letters) "
    "  - $\\frac{{a}}{{b}}$ (fractions) "
    "  - $||w||^2$ (norms) "
    "NEVER use plain text like w_(n+1) or (X^T X)^(-1) - always use proper LaTeX notation with dollar signs. "
    "Give answer in {lang}.\n\n"
    "{context}\n"
    "Question: {question}\n"
    "Helpful Answer:"
)

DEFAULT_QA_TABLE_PROMPT = (
    "Use the given context: texts, tables, and figures below to answer the question, "
    "then provide answer with clear explanation. "
    "If you don't know the answer, just say that you don't know, "
    "don't try to make up an answer. "
    "Use rich formatting in your answer: use markdown tables, bullet points, "
    "numbered lists, and headings where appropriate to make the answer clear and structured. "
    "For mathematical formulas and equations, ALWAYS use LaTeX format with $...$ for inline math (e.g., $w = (X^T X)^{{-1}} X^T d$) or $$...$$ for display math. "
    "Examples of correct LaTeX formatting: "
    "  - $w_{{n+1}} = (X_n^T X_n)^{{-1}} X_n^T d_n$ (subscripts and superscripts) "
    "  - $\\alpha^2$ (Greek letters) "
    "  - $\\frac{{a}}{{b}}$ (fractions) "
    "  - $||w||^2$ (norms) "
    "NEVER use plain text like w_(n+1) or (X^T X)^(-1) - always use proper LaTeX notation with dollar signs. "
    "Give answer in {lang}.\n\n"
    "Context:\n"
    "{context}\n"
    "Question: {question}\n"
    "Helpful Answer:"
)  # noqa

DEFAULT_QA_CHATBOT_PROMPT = (
    "Pick the most suitable chatbot scenarios to answer the question at the end, "
    "output the provided answer text. If you don't know the answer, "
    "just say that you don't know. Keep the answer as concise as possible. "
    "Give answer in {lang}.\n\n"
    "Context:\n"
    "{context}\n"
    "Question: {question}\n"
    "Answer:"
)  # noqa

DEFAULT_QA_FIGURE_PROMPT = (
    "Use the given context: texts, tables, and figures below to answer the question. "
    "If you don't know the answer, just say that you don't know. "
    "Use rich formatting in your answer: use markdown tables, bullet points, "
    "numbered lists, and headings where appropriate to make the answer clear and structured. "
    "For mathematical formulas and equations, ALWAYS use LaTeX format with $...$ for inline math (e.g., $w = (X^T X)^{{-1}} X^T d$) or $$...$$ for display math. "
    "Examples of correct LaTeX formatting: "
    "  - $w_{{n+1}} = (X_n^T X_n)^{{-1}} X_n^T d_n$ (subscripts and superscripts) "
    "  - $\\alpha^2$ (Greek letters) "
    "  - $\\frac{{a}}{{b}}$ (fractions) "
    "  - $||w||^2$ (norms) "
    "NEVER use plain text like w_(n+1) or (X^T X)^(-1) - always use proper LaTeX notation with dollar signs. "
    "Give answer in {lang}.\n\n"
    "Context: \n"
    "{context}\n"
    "Question: {question}\n"
    "Answer: "
)  # noqa


class AnswerWithContextPipeline(BaseComponent):
    """Answer the question based on the evidence

    Args:
        llm: the language model to generate the answer
        citation_pipeline: generates citation from the evidence
        qa_template: the prompt template for LLM to generate answer (refer to
            evidence_mode)
        qa_table_template: the prompt template for LLM to generate answer for table
            (refer to evidence_mode)
        qa_chatbot_template: the prompt template for LLM to generate answer for
            pre-made scenarios (refer to evidence_mode)
        lang: the language of the answer. Currently support English and Japanese
    """

    llm: ChatLLM = Node(default_callback=lambda _: _get_default_llm())
    vlm_endpoint: str = getattr(flowsettings, "KH_VLM_ENDPOINT", "")
    use_multimodal: bool = getattr(flowsettings, "KH_REASONINGS_USE_MULTIMODAL", True)
    citation_pipeline: CitationPipeline = Node(
        default_callback=lambda _: CitationPipeline(llm=_get_default_llm())
    )
    create_mindmap_pipeline: BaseComponent = Node(
        default_callback=lambda _: _create_default_mindmap_pipeline()
    )

    qa_template: str = DEFAULT_QA_TEXT_PROMPT
    qa_table_template: str = DEFAULT_QA_TABLE_PROMPT
    qa_chatbot_template: str = DEFAULT_QA_CHATBOT_PROMPT
    qa_figure_template: str = DEFAULT_QA_FIGURE_PROMPT

    enable_citation: bool = False
    enable_mindmap: bool = False
    enable_citation_viz: bool = False
    enable_claim_verification: bool = getattr(
        flowsettings, "KH_ENABLE_CLAIM_VERIFICATION", False
    )

    system_prompt: str = ""
    lang: str = "English"  # support English and Japanese
    n_last_interactions: int = 5

    def get_prompt(self, question, evidence, evidence_mode: int):
        """Prepare the prompt and other information for LLM"""
        if evidence_mode == EVIDENCE_MODE_TEXT:
            prompt_template = PromptTemplate(self.qa_template)
        elif evidence_mode == EVIDENCE_MODE_TABLE:
            prompt_template = PromptTemplate(self.qa_table_template)
        elif evidence_mode == EVIDENCE_MODE_FIGURE:
            if self.use_multimodal:
                prompt_template = PromptTemplate(self.qa_figure_template)
            else:
                prompt_template = PromptTemplate(self.qa_template)
        else:
            prompt_template = PromptTemplate(self.qa_chatbot_template)

        prompt = prompt_template.populate(
            context=evidence,
            question=question,
            lang=self.lang,
        )

        return prompt, evidence

    def run(
        self, question: str, evidence: str, evidence_mode: int = 0, **kwargs
    ) -> Document:
        return self.invoke(question, evidence, evidence_mode, **kwargs)

    def invoke(
        self,
        question: str,
        evidence: str,
        evidence_mode: int = 0,
        images: list[str] = [],
        **kwargs,
    ) -> Document:
        raise NotImplementedError

    async def ainvoke(  # type: ignore
        self,
        question: str,
        evidence: str,
        evidence_mode: int = 0,
        images: list[str] = [],
        **kwargs,
    ) -> Document:
        """Answer the question based on the evidence

        In addition to the question and the evidence, this method also take into
        account evidence_mode. The evidence_mode tells which kind of evidence is.
        The kind of evidence affects:
            1. How the evidence is represented.
            2. The prompt to generate the answer.

        By default, the evidence_mode is 0, which means the evidence is plain text with
        no particular semantic representation. The evidence_mode can be:
            1. "table": There will be HTML markup telling that there is a table
                within the evidence.
            2. "chatbot": There will be HTML markup telling that there is a chatbot.
                This chatbot is a scenario, extracted from an Excel file, where each
                row corresponds to an interaction.

        Args:
            question: the original question posed by user
            evidence: the text that contain relevant information to answer the question
                (determined by retrieval pipeline)
            evidence_mode: the mode of evidence, 0 for text, 1 for table, 2 for chatbot
        """
        raise NotImplementedError

    def stream(  # type: ignore
        self,
        question: str,
        evidence: str,
        evidence_mode: int = 0,
        images: list[str] = [],
        **kwargs,
    ) -> Generator[Document, None, Document]:
        history = kwargs.get("history", [])
        logger.debug("Got %s images", len(images))
        # check if evidence exists, use QA prompt
        if evidence:
            prompt, evidence = self.get_prompt(question, evidence, evidence_mode)
        else:
            prompt = question

        # retrieve the citation
        citation = None
        mindmap = None

        def citation_call():
            nonlocal citation
            citation = self.citation_pipeline(context=evidence, question=question)

        def mindmap_call():
            nonlocal mindmap
            mindmap = self.create_mindmap_pipeline(context=evidence, question=question)

        citation_thread = None
        mindmap_thread = None

        # execute function call in thread
        if evidence:
            if self.enable_citation:
                citation_thread = threading.Thread(target=citation_call)
                citation_thread.start()

            if self.enable_mindmap:
                mindmap_thread = threading.Thread(target=mindmap_call)
                mindmap_thread.start()

        output = ""
        logprobs = []

        messages = []
        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))

        for human, ai in history[-self.n_last_interactions :]:
            messages.append(HumanMessage(content=human))
            messages.append(AIMessage(content=ai))

        if self.use_multimodal and evidence_mode == EVIDENCE_MODE_FIGURE:
            # create image message:
            logger.debug(
                "Multimodal mode enabled. Preparing %s images",
                len(images[:MAX_IMAGES]),
            )
            image_messages = [
                {
                    "type": "image_url",
                    "image_url": {"url": image},
                }
                for image in images[:MAX_IMAGES]
            ]
            logger.debug("Image messages created: %s", len(image_messages))
            messages.append(
                HumanMessage(
                    content=[
                        {"type": "text", "text": prompt},
                    ]
                    + image_messages,
                )
            )
            logger.debug(
                "Total multimodal message content length: %s",
                len(messages[-1].content),
            )
        else:
            # append main prompt
            logger.debug(
                "Using text-only mode (use_multimodal=%s, evidence_mode=%s)",
                self.use_multimodal,
                evidence_mode,
            )
            messages.append(HumanMessage(content=prompt))

        try:
            # try streaming first
            logger.debug("Trying LLM streaming")
            for out_msg in self.llm.stream(messages):
                output += out_msg.text
                logprobs += out_msg.logprobs
                yield Document(channel="chat", content=out_msg.text)
        except NotImplementedError:
            logger.debug(
                "Streaming is not supported, falling back to normal processing"
            )
            output = self.llm(messages).text
            yield Document(channel="chat", content=output)

        if logprobs:
            qa_score = np.exp(np.average(logprobs))
        else:
            qa_score = None

        if citation_thread:
            citation_thread.join(timeout=CITATION_TIMEOUT)
        if mindmap_thread:
            mindmap_thread.join(timeout=CITATION_TIMEOUT)

        claim_verification = None
        if kwargs.get("enable_claim_verification", self.enable_claim_verification):
            source_documents = kwargs.get("source_documents") or []
            claim_verification, verified_output = self.verify_answer_claims(
                answer_text=output,
                evidence=evidence,
                source_documents=source_documents,
                claim_verifier=kwargs.get("claim_verifier"),
            )
            if verified_output != output:
                if self._should_keep_original_after_verification(
                    evidence_mode=evidence_mode,
                    images=images,
                    source_documents=source_documents,
                    question=question,
                    answer_text=output,
                ):
                    claim_verification["rewrite_skipped"] = True
                    claim_verification["rewrite_skip_reason"] = (
                        "multimodal_or_formula_evidence"
                    )
                else:
                    output = verified_output
                    yield Document(channel="chat", content=None)
                    yield Document(channel="chat", content=output)

        answer_metadata = {
            "citation_viz": self.enable_citation_viz,
            "mindmap": mindmap,
            "citation": citation,
            "qa_score": qa_score,
        }
        if claim_verification is not None:
            answer_metadata["claim_verification"] = claim_verification

        answer = Document(
            text=output,
            metadata=answer_metadata,
        )

        return answer

    def verify_answer_claims(
        self,
        *,
        answer_text: str,
        evidence: str,
        source_documents: list[Document] | None = None,
        claim_verifier=None,
    ) -> tuple[dict | None, str]:
        """Verify generated claims and return metadata plus a safe answer text."""

        if not answer_text.strip():
            return None, answer_text

        evidence_texts = [evidence] if evidence else []
        source_documents = source_documents or []
        verifier = claim_verifier or verify_claims

        if hasattr(verifier, "verify"):
            result = verifier.verify(
                answer=answer_text,
                evidence_texts=evidence_texts,
                source_documents=source_documents,
            )
        else:
            result = verifier(
                answer=answer_text,
                evidence_texts=evidence_texts,
                source_documents=source_documents,
            )

        metadata = self._claim_verification_to_metadata(result)
        revised_answer = metadata.get("revised_answer")

        if revised_answer is None and not isinstance(result, dict):
            revision = revise_or_abstain(result)
            revised_answer = revision.text
            metadata["revised_answer"] = revision.text
            metadata["abstained"] = revision.abstained
            if revision.verification_note:
                metadata["verification_note"] = revision.verification_note

        if not revised_answer:
            revised_answer = answer_text

        return metadata, str(revised_answer)

    @staticmethod
    def _should_keep_original_after_verification(
        *,
        evidence_mode: int,
        images: list[str],
        source_documents: list[Document],
        question: str = "",
        answer_text: str = "",
    ) -> bool:
        if evidence_mode == EVIDENCE_MODE_FIGURE or images:
            return True

        has_page_visual_context = False
        for document in source_documents:
            metadata = dict(getattr(document, "metadata", None) or {})
            kinds = {
                str(metadata.get("type") or "").strip().lower(),
                str(metadata.get("element_type") or "").strip().lower(),
            }
            if kinds & {"image", "figure", "formula", "formula_image", "thumbnail"}:
                return True
            if any(
                metadata.get(key)
                for key in (
                    "image_origin",
                    "formula_image",
                    "normalized_formula",
                    "formula_text",
                    "formula_json",
                    "formula_image_json",
                )
            ):
                return True
            if any(metadata.get(key) for key in _PAGE_VISUAL_CONTEXT_KEYS):
                has_page_visual_context = True

        if has_page_visual_context and _looks_like_visual_question_or_answer(
            question, answer_text
        ):
            return True

        return False

    @classmethod
    def _claim_verification_to_metadata(cls, result) -> dict:
        if isinstance(result, dict):
            return cls._metadata_value(result)
        return cls._metadata_value(result)

    @classmethod
    def _metadata_value(cls, value):
        if isinstance(value, Enum):
            return value.value
        if is_dataclass(value):
            return cls._metadata_value(asdict(value))
        if isinstance(value, dict):
            return {key: cls._metadata_value(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls._metadata_value(item) for item in value]
        return value

    def match_evidence_with_context(self, answer, docs) -> dict[str, list[dict]]:
        """Match the evidence with the context"""
        spans: dict[str, list[dict]] = defaultdict(list)

        if not answer.metadata["citation"]:
            return spans

        evidences = answer.metadata["citation"].evidences
        for quote in evidences:
            matched_excerpts = []
            for doc in docs:
                matches = find_text(quote, doc.text)

                for start, end in matches:
                    if "|" not in doc.text[start:end]:
                        spans[doc.doc_id].append(
                            {
                                "start": start,
                                "end": end,
                            }
                        )
                        matched_excerpts.append(doc.text[start:end])

            # print("Matched citation:", quote, matched_excerpts),
        return spans

    def prepare_citations(self, answer, docs) -> tuple[list[Document], list[Document]]:
        """Prepare the citations to show on the UI"""
        with_citation, without_citation = [], []
        has_llm_score = any("llm_trulens_score" in doc.metadata for doc in docs)
        render = _get_render()

        spans = self.match_evidence_with_context(answer, docs)
        citation_targets = [
            target.to_dict() for target in citation_targets_from_spans(spans, docs)
        ]
        answer.metadata["citation_targets"] = citation_targets
        targets_by_doc_id: dict[str, list[dict]] = defaultdict(list)
        for target in citation_targets:
            doc_id = target.get("doc_id")
            if doc_id:
                targets_by_doc_id[doc_id].append(target)

        id2docs = {doc.doc_id: doc for doc in docs}
        not_detected = set(id2docs.keys()) - set(spans.keys())

        # render highlight spans
        for _id, ss in spans.items():
            if not ss:
                not_detected.add(_id)
                continue
            cur_doc = id2docs[_id]
            highlight_text = ""

            ss = sorted(ss, key=lambda x: x["start"])
            last_end = 0
            text = cur_doc.text[: ss[0]["start"]]

            for idx, span in enumerate(ss):
                # prevent overlapping between span
                span_start = max(last_end, span["start"])
                span_end = max(last_end, span["end"])

                to_highlight = cur_doc.text[span_start:span_end]
                last_end = span_end

                # append to highlight on PDF viewer
                highlight_text += (" " if highlight_text else "") + to_highlight

                span_idx = span.get("idx", None)
                if span_idx is not None:
                    to_highlight = f"【{span_idx}】" + to_highlight

                text += render.highlight(
                    to_highlight,
                    elem_id=str(span_idx) if span_idx is not None else None,
                )
                if idx < len(ss) - 1:
                    text += cur_doc.text[span["end"] : ss[idx + 1]["start"]]

            text += cur_doc.text[ss[-1]["end"] :]
            # add to display list
            with_citation.append(
                Document(
                    channel="info",
                    metadata={"citation_targets": targets_by_doc_id.get(_id, [])},
                    content=render.collapsible_with_header_score(
                        cur_doc,
                        override_text=text,
                        highlight_text=highlight_text,
                        open_collapsible=True,
                    ),
                )
            )

        logger.debug("Got %s cited docs", len(with_citation))

        sorted_not_detected_items_with_scores = [
            (id_, id2docs[id_].metadata.get("llm_trulens_score", 0.0))
            for id_ in not_detected
        ]
        sorted_not_detected_items_with_scores.sort(key=lambda x: x[1], reverse=True)

        for id_, _ in sorted_not_detected_items_with_scores:
            doc = id2docs[id_]
            doc_score = doc.metadata.get("llm_trulens_score", 0.0)
            is_open = not has_llm_score or (
                doc_score
                > CONTEXT_RELEVANT_WARNING_SCORE
                # and len(with_citation) == 0
            )
            without_citation.append(
                Document(
                    channel="info",
                    metadata={
                        "citation_targets": [
                            citation_target_from_document(doc).to_dict()
                        ]
                    },
                    content=render.collapsible_with_header_score(
                        doc, open_collapsible=is_open
                    ),
                )
            )
        return with_citation, without_citation
