import html
import logging
from functools import partial

import tiktoken

from kotaemon.base import BaseComponent, Document, RetrievedDocument
from kotaemon.indices.splitters import TokenSplitter

logger = logging.getLogger(__name__)

EVIDENCE_MODE_TEXT = 0
EVIDENCE_MODE_TABLE = 1
EVIDENCE_MODE_CHATBOT = 2
EVIDENCE_MODE_FIGURE = 3


def _metadata_kind(metadata: dict) -> set[str]:
    return {
        str(metadata.get("type", "")).lower(),
        str(metadata.get("element_type", "")).lower(),
    }


def _is_figure(metadata: dict) -> bool:
    return bool(_metadata_kind(metadata) & {"image", "figure"})


def _is_formula(metadata: dict) -> bool:
    return "formula" in _metadata_kind(metadata)


def _figure_text_parts(item: RetrievedDocument) -> list[tuple[str, str]]:
    fields = [
        ("Caption", item.metadata.get("caption", "")),
        ("OCR", item.metadata.get("ocr_text", "")),
        ("Content", item.get_content()),
    ]
    return [
        (label, str(value).strip()) for label, value in fields if str(value).strip()
    ]


def _format_figure_alt(item: RetrievedDocument, source: str) -> str:
    text_parts = [
        f"{label}: {value}" if label != "Content" else value
        for label, value in _figure_text_parts(item)
    ]
    alt_text = " ".join(text_parts).strip() or f"Figure from {source}"
    return html.escape(alt_text, quote=True)


def _format_figure_text(item: RetrievedDocument) -> str:
    return "\n".join(
        f"{label}: {html.escape(value)}" for label, value in _figure_text_parts(item)
    )


def _format_formula_metadata(item: RetrievedDocument, page: str | None) -> str:
    metadata = item.metadata
    fields = [
        ("Normalized formula", metadata.get("normalized_formula") or item.text),
        ("Raw PDF text", metadata.get("raw_pdf_text")),
        ("Formula kind", metadata.get("formula_kind")),
        ("Page", page or metadata.get("page") or metadata.get("page_number")),
        ("Bbox", metadata.get("bbox")),
    ]
    return "\n".join(
        f"{label}: {html.escape(str(value))}"
        for label, value in fields
        if value not in (None, "")
    )


class PrepareEvidencePipeline(BaseComponent):
    """Prepare the evidence text from the list of retrieved documents

    This step usually happens after `DocumentRetrievalPipeline`.

    Args:
        trim_func: a callback function or a BaseComponent, that splits a large
            chunk of text into smaller ones. The first one will be retained.
    """

    max_context_length: int = 32000
    trim_func: TokenSplitter | None = None

    def run(self, docs: list[RetrievedDocument]) -> Document:
        evidence = ""
        images = []
        table_found = 0
        evidence_modes = []
        seen_doc_ids: set = set()

        evidence_trim_func = (
            self.trim_func
            if self.trim_func
            else TokenSplitter(
                chunk_size=self.max_context_length,
                chunk_overlap=0,
                separator=" ",
                tokenizer=partial(
                    tiktoken.encoding_for_model("gpt-3.5-turbo").encode,
                    allowed_special=set(),
                    disallowed_special="all",
                ),
            )
        )

        logger.debug("PrepareEvidence processing %d docs", len(docs))
        for _idx, retrieved_item in enumerate(docs):
            # skip duplicate documents by doc_id
            if retrieved_item.doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(retrieved_item.doc_id)

            retrieved_content = ""
            page = retrieved_item.metadata.get("page_label", None)
            source = filename = retrieved_item.metadata.get("file_name", "-")
            metadata = retrieved_item.metadata
            doc_type = metadata.get("type") or metadata.get("element_type", "text")
            logger.debug(
                "PrepareEvidence doc %d page=%s type=%s file=%s text_len=%d",
                _idx,
                page,
                doc_type,
                filename,
                len(retrieved_item.text),
            )
            if page:
                source += f" (Page {page})"
            if metadata.get("type", "") == "table":
                evidence_modes.append(EVIDENCE_MODE_TABLE)
                if table_found < 20:
                    retrieved_content = metadata.get(
                        "table_origin", retrieved_item.text
                    )
                    if retrieved_content not in evidence:
                        table_found += 1
                        evidence += (
                            f"<br><b>Table from {source}</b>\n"
                            + retrieved_content
                            + "\n<br>"
                        )
            elif metadata.get("type", "") == "chatbot":
                evidence_modes.append(EVIDENCE_MODE_CHATBOT)
                retrieved_content = metadata["window"]
                evidence += (
                    f"<br><b>Chatbot scenario from {filename} (Row {page})</b>\n"
                    + retrieved_content
                    + "\n<br>"
                )
            elif _is_figure(metadata):
                evidence_modes.append(EVIDENCE_MODE_FIGURE)
                retrieved_content = metadata.get("image_origin", "")
                figure_text = _format_figure_text(retrieved_item)
                retrieved_caption = _format_figure_alt(retrieved_item, source)
                evidence += (
                    f"<br><b>Figure from {source}</b>\n"
                    + (figure_text + "\n" if figure_text else "")
                    + "<img width='85%' src='<src>' "
                    + f"alt='{retrieved_caption}'/>"
                    + "\n<br>"
                )
                images.append(retrieved_content)
            elif _is_formula(metadata):
                retrieved_content = _format_formula_metadata(retrieved_item, page)
                evidence += (
                    f"<br><b>Formula from {source}</b>\n" + retrieved_content + "\n<br>"
                )
            else:
                if "window" in metadata:
                    retrieved_content = metadata["window"]
                else:
                    retrieved_content = retrieved_item.text
                retrieved_content = retrieved_content.replace("\n", " ")
                evidence += (
                    f"<br><b>Content from {source}: </b> "
                    + retrieved_content
                    + " \n<br>"
                )

        # resolve evidence mode
        evidence_mode = EVIDENCE_MODE_TEXT
        if EVIDENCE_MODE_FIGURE in evidence_modes:
            evidence_mode = EVIDENCE_MODE_FIGURE
        elif EVIDENCE_MODE_TABLE in evidence_modes:
            evidence_mode = EVIDENCE_MODE_TABLE

        # trim context by trim_len
        logger.debug("PrepareEvidence original length=%d", len(evidence))
        if evidence:
            texts = evidence_trim_func([Document(text=evidence)])
            evidence = texts[0].text
            logger.debug("PrepareEvidence trimmed length=%d", len(evidence))

        return Document(content=(evidence_mode, evidence, images))
