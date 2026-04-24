from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, Literal

from kotaemon.base import Document
from kotaemon.indices.elements import normalize_formula_text

FormulaKind = Literal["inline", "display"]


@dataclass(frozen=True)
class FormulaMatch:
    raw_text: str
    normalized_formula: str
    formula_kind: FormulaKind
    start: int
    end: int


_DELIMITER_PATTERNS: tuple[tuple[re.Pattern[str], FormulaKind], ...] = (
    (re.compile(r"\$\$(?P<body>.+?)\$\$", re.DOTALL), "display"),
    (re.compile(r"\\\[(?P<body>.+?)\\\]", re.DOTALL), "display"),
    (re.compile(r"\\\((?P<body>.+?)\\\)", re.DOTALL), "inline"),
    (re.compile(r"(?<!\$)\$(?!\$)(?P<body>.+?)(?<!\$)\$(?!\$)", re.DOTALL), "inline"),
)
_ENVIRONMENT_PATTERN = re.compile(
    r"\\begin\{(?P<env>align\*?|aligned|equation\*?|gather\*?)\}"
    r"(?P<body>.+?)"
    r"\\end\{(?P=env)\}",
    re.DOTALL,
)

_EQUATION_PATTERN = re.compile(
    r"(?<![\w\\])"
    r"(?P<formula>"
    r"(?:\\?[A-Za-z][A-Za-z0-9_{}\\]*|\d+(?:\.\d+)?)"
    r"(?:\s*[+\-*/^]\s*(?:\\?[A-Za-z][A-Za-z0-9_{}\\]*|\d+(?:\.\d+)?))*"
    r"\s*=\s*"
    r"(?:\\?[A-Za-z][A-Za-z0-9_{}\\]*|\d+(?:\.\d+)?)"
    r"(?:\s*[+\-*/^]\s*(?:\\?[A-Za-z][A-Za-z0-9_{}\\]*|\d+(?:\.\d+)?))*"
    r")"
    r"(?![\w\\])"
)

_DELIMITED_MATH_SIGNAL_PATTERN = re.compile(r"(\\[A-Za-z]+|[_^=+\-*/])")
_LETTER_PATTERN = re.compile(r"[A-Za-z\\]")


def extract_formula_elements(document: Any) -> list[Document]:
    """Extract lightweight formula Documents from a source document.

    This intentionally avoids OCR and only inspects text already present on the
    document. Source metadata is copied so later ingestion steps can preserve page,
    bbox, file/document IDs, and parser-specific provenance.
    """

    text = _document_text(document)
    metadata = dict(getattr(document, "metadata", None) or {})
    matches = detect_formulas(text)
    return [_match_to_document(match, metadata) for match in matches]


def expand_documents_with_formula_elements(documents: Iterable[Any]) -> list[Any]:
    """Return original documents followed by formula element documents."""

    originals = list(documents)
    formula_documents: list[Document] = []
    for document in originals:
        formula_documents.extend(extract_formula_elements(document))
    return originals + formula_documents


def detect_formulas(text: str) -> list[FormulaMatch]:
    """Find delimited formulas and simple equation-like text spans."""

    matches = _detect_environment_formulas(text)
    occupied_spans = [(match.start, match.end) for match in matches]
    matches.extend(_detect_delimited_formulas(text, occupied_spans))
    occupied_spans = [(match.start, match.end) for match in matches]
    matches.extend(_detect_equation_like_formulas(text, occupied_spans))
    return sorted(matches, key=lambda match: match.start)


def _detect_delimited_formulas(
    text: str, occupied_spans: list[tuple[int, int]] | None = None
) -> list[FormulaMatch]:
    matches: list[FormulaMatch] = []
    occupied_spans = list(occupied_spans or [])

    for pattern, formula_kind in _DELIMITER_PATTERNS:
        for regex_match in pattern.finditer(text):
            start, end = regex_match.span()
            if _overlaps_any(start, end, occupied_spans):
                continue

            raw_text = regex_match.group(0)
            body = regex_match.group("body")
            normalized = normalize_formula_text(body)
            if not _looks_like_formula(normalized):
                continue

            matches.append(
                FormulaMatch(
                    raw_text=raw_text,
                    normalized_formula=normalized,
                    formula_kind=formula_kind,
                    start=start,
                    end=end,
                )
            )
            occupied_spans.append((start, end))

    return matches


def _detect_environment_formulas(text: str) -> list[FormulaMatch]:
    matches: list[FormulaMatch] = []
    for regex_match in _ENVIRONMENT_PATTERN.finditer(text):
        body = regex_match.group("body")
        body_start = regex_match.start("body")
        for row_start, raw_row in _iter_environment_rows(body):
            cleaned_row = _clean_environment_row(raw_row)
            normalized = normalize_formula_text(cleaned_row)
            if not _looks_like_equation(normalized):
                continue

            start = body_start + row_start
            end = start + len(raw_row)
            matches.append(
                FormulaMatch(
                    raw_text=raw_row.strip(),
                    normalized_formula=normalized,
                    formula_kind="display",
                    start=start,
                    end=end,
                )
            )
    return matches


def _iter_environment_rows(body: str) -> Iterable[tuple[int, str]]:
    cursor = 0
    for raw_row in re.split(r"\\\\", body):
        row_start = body.find(raw_row, cursor)
        if row_start < 0:
            row_start = cursor
        cursor = row_start + len(raw_row)
        if raw_row.strip():
            yield row_start, raw_row


def _clean_environment_row(row: str) -> str:
    row = re.sub(r"\\(?:notag|nonumber)\b", "", row)
    row = re.sub(r"\\tag\{[^}]*\}", "", row)
    return row.replace("&", "").strip()


def _detect_equation_like_formulas(
    text: str, occupied_spans: list[tuple[int, int]]
) -> list[FormulaMatch]:
    matches: list[FormulaMatch] = []
    for regex_match in _EQUATION_PATTERN.finditer(text):
        start, end = regex_match.span("formula")
        if _overlaps_any(start, end, occupied_spans):
            continue

        raw_text = regex_match.group("formula")
        normalized = normalize_formula_text(raw_text)
        if not _looks_like_equation(normalized):
            continue

        matches.append(
            FormulaMatch(
                raw_text=raw_text,
                normalized_formula=normalized,
                formula_kind="inline",
                start=start,
                end=end,
            )
        )
    return matches


def _match_to_document(
    match: FormulaMatch, source_metadata: dict[str, Any]
) -> Document:
    metadata = dict(source_metadata)
    metadata.update(
        {
            "type": "formula",
            "formula_kind": match.formula_kind,
            "raw_pdf_text": match.raw_text,
            "normalized_formula": match.normalized_formula,
        }
    )

    formula_image = _metadata_first(source_metadata, "formula_image", "image_origin")
    if formula_image is not None:
        metadata["formula_image"] = formula_image

    return Document(text=match.normalized_formula, metadata=metadata)


def _looks_like_formula(text: str) -> bool:
    if len(text) < 3:
        return False
    if not _LETTER_PATTERN.search(text):
        return False
    return bool(_DELIMITED_MATH_SIGNAL_PATTERN.search(text))


def _looks_like_equation(text: str) -> bool:
    if len(text) > 160 or "=" not in text:
        return False
    left, right = (part.strip() for part in text.split("=", 1))
    if not left or not right:
        return False
    if not _LETTER_PATTERN.search(left) or not _LETTER_PATTERN.search(right):
        return False
    return bool(re.search(r"(\\[A-Za-z]+|[_^+\-*/]|\d)", text))


def _overlaps_any(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < span_end and end > span_start for span_start, span_end in spans)


def _metadata_first(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _document_text(document: Any) -> str:
    text = getattr(document, "text", None)
    if text is not None:
        return str(text)
    content = getattr(document, "content", "")
    return "" if content is None else str(content)
