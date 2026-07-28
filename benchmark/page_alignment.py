from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ktem.docqa.evidence_locators import (
    normalized_page_aliases,
    normalized_source_aliases,
    normalized_source_page_locators,
)

PageExtractor = Callable[[Path, tuple[int, ...]], list[tuple[int, str]]]
PAGE_LABEL_KEYS = ("page_label", "page_number_label", "source_page_label")
PAGE_INDEX_KEYS = ("parser_page_index", "page", "page_index")
GOLD_TEXT_KEYS = ("span", "text", "quote", "evidence", "image_quote", "visual_quote")
EVIDENCE_TEXT_KEYS = ("text", "snippet", "caption", "ocr_text", "vlm_text")
SOURCE_ID_KEYS = ("document_id", "source_id", "doc_id", "file_id")
PAGE_REF_RE = re.compile(r"(?:^|[#\s:_-])page\s*[:=]?\s*(\d+)\b", re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-zA-Z0-9]+")
STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "are",
        "as",
        "at",
        "be",
        "been",
        "being",
        "by",
        "for",
        "from",
        "in",
        "include",
        "includes",
        "including",
        "is",
        "it",
        "its",
        "of",
        "on",
        "or",
        "s",
        "that",
        "the",
        "their",
        "this",
        "to",
        "was",
        "were",
        "with",
    }
)
SHORT_GOLD_TEXT_TOKENS = 40
SHORT_TEXT_OVERLAP_THRESHOLD = 0.65
LONG_TEXT_OVERLAP_THRESHOLD = 0.35
MIN_SHORT_SHARED_TOKENS = 5
MIN_LONG_SHARED_TOKENS = 12
PAGE_ALIGNMENT_WINDOW = 2


@dataclass(frozen=True, slots=True)
class LocatorAlignment:
    locator_applicable: bool
    page_exact: bool | None
    parser_page_index: int | None


def align_gold_page(
    gold_page: int | str,
    parser_pages: list[dict[str, Any]],
) -> int | None:
    gold = str(gold_page).strip()
    if not gold:
        return None

    for page in parser_pages:
        page_label = str(page.get("page_label") or "").strip()
        if page_label and page_label == gold:
            return int(page["page_index"])

    if gold.isdigit():
        zero_based_page = int(gold) - 1
        for page in parser_pages:
            if int(page.get("page_index", -1)) == zero_based_page:
                return zero_based_page
    return None


def align_locator(
    *,
    gold_page: int | str | None,
    retrieved_metadata: dict[str, Any],
) -> LocatorAlignment:
    gold = _metadata_text(gold_page)
    if gold is None:
        return LocatorAlignment(
            locator_applicable=False,
            page_exact=None,
            parser_page_index=None,
        )

    page_label = _first_metadata_text(retrieved_metadata, PAGE_LABEL_KEYS)
    parser_page_index = _first_metadata_int(retrieved_metadata, PAGE_INDEX_KEYS)
    return LocatorAlignment(
        locator_applicable=True,
        page_exact=page_label == gold if page_label is not None else False,
        parser_page_index=parser_page_index,
    )


def align_span_to_parser_page(
    document_path: Path | None,
    page: int | str | None,
    span: str,
    *,
    extract_pages: PageExtractor,
    window: int = 2,
) -> tuple[int | str | None, str]:
    if document_path is None or page is None or not span:
        return page, ""

    needle = normalize_span_for_alignment(span)
    if not needle:
        return page, ""

    for parser_page, text in extract_pages(
        document_path, page_candidates(page, window)
    ):
        if needle in normalize_span_for_alignment(text):
            if parser_page == page:
                return page, ""
            return parser_page, "span_to_parser_page"
    return page, ""


def page_candidates(page: int | str, window: int = 2) -> tuple[int, ...]:
    try:
        center = int(str(page).strip())
    except ValueError:
        return ()
    start = max(1, center - window)
    end = max(start, center + window)
    return tuple(range(start, end + 1))


def normalize_span_for_alignment(value: str) -> str:
    return " ".join(re.findall(r"[a-zA-Z0-9]+", str(value or "").lower()))


def evidence_text_supports_gold_locator(
    gold_record: dict[str, Any],
    evidence_text: str,
) -> bool:
    gold_text = gold_locator_text(gold_record)
    if not gold_text or not evidence_text:
        return False

    normalized_gold = normalize_span_for_alignment(gold_text)
    normalized_evidence = normalize_span_for_alignment(evidence_text)
    if not normalized_gold or not normalized_evidence:
        return False
    if normalized_gold in normalized_evidence:
        return True

    gold_tokens = _locator_tokens(gold_text)
    evidence_tokens = _locator_tokens(evidence_text)
    if not gold_tokens or not evidence_tokens:
        return False
    shared_tokens = gold_tokens & evidence_tokens
    if len(gold_tokens) <= SHORT_GOLD_TEXT_TOKENS:
        return (
            len(shared_tokens) >= MIN_SHORT_SHARED_TOKENS
            and len(shared_tokens) / len(gold_tokens) >= SHORT_TEXT_OVERLAP_THRESHOLD
        )
    return (
        len(shared_tokens) >= MIN_LONG_SHARED_TOKENS
        and len(shared_tokens) / len(gold_tokens) >= LONG_TEXT_OVERLAP_THRESHOLD
    )


def evidence_aligned_page_hit_score(
    predicted_pages: list[int | str],
    gold_pages: list[int | str],
    *,
    gold_evidence: list[dict[str, Any]],
    evidence_bundle: dict[str, Any],
    retrieved_hits: list[dict[str, Any]],
) -> float | None:
    exact_score = _exact_page_hit_score(predicted_pages, gold_pages)
    if exact_score != 0.0:
        return exact_score

    predicted = {str(page).strip() for page in predicted_pages if str(page).strip()}
    if not predicted or not gold_pages:
        return exact_score

    evidence_items = _combined_evidence_items(evidence_bundle, retrieved_hits)
    for gold_record in gold_evidence:
        if not _gold_record_has_page(gold_record):
            continue
        for item in evidence_items:
            page_label = item_page_label(item)
            if page_label not in predicted:
                continue
            if not locator_pages_are_alignment_candidates(
                gold_record_page_label(gold_record),
                page_label,
            ):
                continue
            if not item_matches_gold_source(item, gold_record):
                continue
            if evidence_text_supports_gold_locator(
                gold_record, evidence_item_text(item)
            ):
                return 1.0
    return exact_score


def gold_locator_text(record: dict[str, Any]) -> str:
    return _first_metadata_text(record, GOLD_TEXT_KEYS) or ""


def evidence_item_text(item: dict[str, Any]) -> str:
    values = [str(item.get(key) or "") for key in EVIDENCE_TEXT_KEYS]
    nested = item.get("retrieved_page_evidence")
    if isinstance(nested, dict):
        values.extend(str(nested.get(key) or "") for key in EVIDENCE_TEXT_KEYS)
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        nested_metadata = metadata.get("retrieved_page_evidence")
        if isinstance(nested_metadata, dict):
            values.extend(
                str(nested_metadata.get(key) or "") for key in EVIDENCE_TEXT_KEYS
            )
    return " ".join(value for value in values if value)


def item_matches_citation(item: dict[str, Any], citation: str) -> bool:
    citation_text = str(citation or "").strip()
    if not citation_text:
        return False
    citation_source = citation_source_id(citation_text)
    citation_page = citation_page_label(citation_text)
    source = citation_source.strip().lower()
    page = str(citation_page or "").strip().lower()
    return any(
        (not source or source == candidate_source)
        and (not page or page == candidate_page)
        for candidate_source, candidate_page in normalized_source_page_locators(item)
    )


def locator_pages_are_alignment_candidates(
    gold_page: Any,
    predicted_page: Any,
    *,
    window: int = PAGE_ALIGNMENT_WINDOW,
) -> bool:
    gold = _metadata_text(gold_page)
    predicted = _metadata_text(predicted_page)
    if gold is None or predicted is None:
        return True
    if gold == predicted:
        return True
    try:
        return abs(int(gold) - int(predicted)) <= window
    except ValueError:
        return False


def gold_record_page_label(record: dict[str, Any]) -> str | None:
    page = _metadata_text(record.get("page"))
    if page is not None:
        return page
    page_label = _metadata_text(record.get("page_label"))
    if page_label is not None:
        return page_label
    citation_page = citation_page_label(str(record.get("citation") or ""))
    if citation_page is not None:
        return citation_page
    return citation_page_label(str(record.get("source") or ""))


def item_matches_gold_source(item: dict[str, Any], gold_record: dict[str, Any]) -> bool:
    gold_sources = {
        source
        for source in (
            _first_metadata_text(gold_record, SOURCE_ID_KEYS),
            citation_source_id(str(gold_record.get("citation") or "")),
            citation_source_id(str(gold_record.get("source") or "")),
        )
        if source
    }
    if not gold_sources:
        return True
    normalized_gold = {source.strip().lower() for source in gold_sources}
    return bool(normalized_source_aliases(item) & normalized_gold)


def item_page_label(item: dict[str, Any]) -> str | None:
    aliases = normalized_page_aliases(item)
    page_label = _first_metadata_text(
        item,
        ("page_label", "page_number_label", "source_page_label", "page"),
    )
    if page_label is not None:
        return page_label
    if aliases:
        return sorted(aliases)[0]
    for ref in _item_source_backrefs(item):
        page_label = citation_page_label(ref)
        if page_label is not None:
            return page_label
    return None


def item_source_id(item: dict[str, Any]) -> str | None:
    direct = _first_metadata_text(item, SOURCE_ID_KEYS)
    if direct is not None:
        return direct
    aliases = normalized_source_aliases(item)
    return sorted(aliases)[0] if aliases else None


def citation_page_label(citation: str) -> str | None:
    match = PAGE_REF_RE.search(str(citation or ""))
    if match:
        return match.group(1)
    return None


def citation_source_id(citation: str) -> str:
    text = str(citation or "").strip()
    if not text:
        return ""
    return text.split("#", 1)[0].strip()


def _exact_page_hit_score(
    predicted_pages: list[int | str],
    gold_pages: list[int | str],
) -> float | None:
    if not gold_pages:
        return None
    predicted = {str(page) for page in predicted_pages}
    gold = {str(page) for page in gold_pages}
    return float(bool(predicted & gold))


def _first_metadata_text(
    metadata: dict[str, Any],
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        text = _metadata_text(metadata.get(key))
        if text is not None:
            return text
    return None


def _first_metadata_int(
    metadata: dict[str, Any],
    keys: tuple[str, ...],
) -> int | None:
    for key in keys:
        text = _metadata_text(metadata.get(key))
        if text is None:
            continue
        try:
            return int(text)
        except ValueError:
            continue
    return None


def _metadata_text(value: Any) -> str | None:
    if value in (None, ""):
        return None
    text = str(value).strip()
    return text or None


def _item_source_backrefs(item: dict[str, Any]) -> set[str]:
    return {str(ref).strip() for ref in item.get("source_backrefs") or [] if ref}


def _locator_tokens(text: str) -> set[str]:
    return {
        token
        for token in TOKEN_RE.findall(str(text or "").lower())
        if len(token) > 1 and token not in STOPWORDS
    }


def _combined_evidence_items(
    evidence_bundle: dict[str, Any],
    retrieved_hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    bundle_items = (
        evidence_bundle.get("items") if isinstance(evidence_bundle, dict) else []
    )
    evidence_items = bundle_items if isinstance(bundle_items, list) else []
    return [
        item for item in [*evidence_items, *retrieved_hits] if isinstance(item, dict)
    ]


def _gold_record_has_page(record: dict[str, Any]) -> bool:
    for key in ("page", "page_label"):
        if key in record and str(record.get(key)).strip():
            return True
    citation = str(record.get("citation") or record.get("source") or "")
    return "#page" in citation.lower()
