from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ensure_list, load_jsonl, pick, write_v2_manifest


def normalize_mmdocrag_manifest(
    source_path: str | Path,
    output_path: str | Path,
    documents_root: str | Path | None = None,
) -> Path:
    source_path = Path(source_path).resolve()
    documents_root = (
        Path(documents_root).resolve() if documents_root else source_path.parent
    )
    documents: dict[str, dict[str, Any]] = {}
    examples: list[dict[str, Any]] = []

    for index, record in enumerate(load_jsonl(source_path)):
        document_id = str(
            pick(record, "doc_name", "document_id", default=f"doc_{index}")
        )
        document = documents.setdefault(
            document_id,
            _document_record(document_id, documents_root),
        )
        _merge_element_catalog(document, record)
        examples.append(_example(record, document_id, index))

    return write_v2_manifest(
        output_path,
        dataset_name="mmdocrag",
        documents=list(documents.values()),
        examples=examples,
    )


def _document_record(document_id: str, documents_root: Path) -> dict[str, Any]:
    return {
        "document_id": document_id,
        "path": str(_document_path(document_id, documents_root)),
        "format_type": "pdf",
        "modality": "mixed",
        "metadata": {"dataset_family": "multimodal_doc_qa"},
    }


def _document_path(document_id: str, documents_root: Path) -> Path:
    for suffix in ("", ".pdf"):
        candidate = documents_root / f"{document_id}{suffix}"
        if candidate.exists():
            return candidate
    return documents_root / f"{document_id}.pdf"


def _example(record: dict[str, Any], document_id: str, index: int) -> dict[str, Any]:
    gold_evidence = _gold_evidence(record, document_id)
    evidence_pages = _ordered_pages(gold_evidence)
    modality_types = [
        str(item).strip().lower()
        for item in ensure_list(record.get("evidence_modality_type"))
        if str(item).strip()
    ]
    return {
        "example_id": str(pick(record, "q_id", "id", default=index)),
        "document_ids": [document_id],
        "scope": "document",
        "modality": "multimodal"
        if len(set(modality_types)) > 1
        else (modality_types[0] if modality_types else "multimodal"),
        "answer_type": str(record.get("question_type") or "descriptive").lower(),
        "question": str(record.get("question") or "").strip(),
        "answers": _answers(record),
        "evidence_pages": evidence_pages,
        "gold_evidence": gold_evidence,
        "metadata": {
            "dataset_family": "multimodal_doc_qa",
            "domain": record.get("domain"),
            "evidence_modality_type": modality_types,
        },
    }


def _answers(record: dict[str, Any]) -> list[str]:
    for key in ("answer_short", "answer", "answer_interleaved"):
        value = str(record.get(key) or "").strip()
        if value:
            return [value]
    return []


def _gold_evidence(record: dict[str, Any], document_id: str) -> list[dict[str, Any]]:
    quotes = _quote_index(record)
    evidence: list[dict[str, Any]] = []
    for quote_id in ensure_list(record.get("gold_quotes")):
        quote = quotes.get(str(quote_id))
        if quote is not None:
            evidence.append(_evidence_item(document_id, quote))
    return evidence


def _quote_index(record: dict[str, Any]) -> dict[str, dict[str, Any]]:
    quotes: dict[str, dict[str, Any]] = {}
    for key in ("text_quotes", "img_quotes"):
        for quote in ensure_list(record.get(key)):
            if isinstance(quote, dict) and quote.get("quote_id"):
                quotes[str(quote["quote_id"])] = quote
    return quotes


def _merge_element_catalog(
    document: dict[str, Any],
    record: dict[str, Any],
) -> None:
    metadata = document["metadata"]
    elements = metadata.setdefault("element_index_records", [])
    seen = {
        (str(item.get("element_id") or ""), str(item.get("page_label") or ""))
        for item in elements
    }
    for quote in _quote_index(record).values():
        element = _catalog_element(quote)
        if element is None:
            continue
        key = (
            str(element["element_id"]),
            str(element["page_label"]),
        )
        if key not in seen:
            seen.add(key)
            elements.append(element)


def _catalog_element(quote: dict[str, Any]) -> dict[str, Any] | None:
    element_id = str(quote.get("quote_id") or "").strip()
    page_label = quote.get("page_id")
    text = str(quote.get("text") or quote.get("img_description") or "").strip()
    if not element_id or page_label is None or not text:
        return None
    element_metadata = {
        "layout_id": quote.get("layout_id"),
        "index_source": "mmdocrag_quote_catalog",
    }
    image_path = str(quote.get("img_path") or "").strip()
    if image_path:
        element_metadata["image_path"] = image_path
    return {
        "page_label": page_label,
        "element_id": element_id,
        "element_type": str(quote.get("type") or "text"),
        "parent_element_id": f"page:{page_label}",
        "text": text,
        "metadata": element_metadata,
    }


def _evidence_item(document_id: str, quote: dict[str, Any]) -> dict[str, Any]:
    page = quote.get("page_id")
    item = {
        "document_id": document_id,
        "page": page,
        "element_id": str(quote.get("quote_id")),
        "element_type": str(quote.get("type") or "text"),
        "citation": f"{document_id}#page:{page}",
    }
    text = str(quote.get("text") or "").strip()
    image_quote = str(quote.get("img_description") or "").strip()
    if text:
        item["span"] = text
    if image_quote:
        item["image_quote"] = image_quote
    return item


def _ordered_pages(gold_evidence: list[dict[str, Any]]) -> list[Any]:
    pages: list[Any] = []
    for item in gold_evidence:
        page = item.get("page")
        if page is not None and page not in pages:
            pages.append(page)
    return pages
