from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

SIDECAR_SUFFIX = ".mara-elements.json"
PARSER_BACKEND = "pymupdf_text_blocks"


def build_pdf_ocr_layout_sidecar(
    pdf_path: str | Path,
    *,
    document_id: str | None = None,
    fitz_module: Any | None = None,
) -> dict[str, Any]:
    path = Path(pdf_path)
    fitz = fitz_module or _import_fitz()
    document = fitz.open(str(path))
    try:
        records = [
            record
            for page_number in range(1, len(document) + 1)
            for record in _page_records(
                document.load_page(page_number - 1),
                page_number,
            )
        ]
    finally:
        close = getattr(document, "close", None)
        if callable(close):
            close()

    return {
        "schema_version": "1",
        "parser_backend": PARSER_BACKEND,
        "source_document_id": document_id or path.stem,
        "source_file_name": path.name,
        "layout_elements": records,
    }


def write_pdf_ocr_layout_sidecar(
    pdf_path: str | Path,
    output_dir: str | Path,
    *,
    document_id: str | None = None,
    fitz_module: Any | None = None,
) -> Path:
    path = Path(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sidecar = build_pdf_ocr_layout_sidecar(
        path,
        document_id=document_id,
        fitz_module=fitz_module,
    )
    out_path = sidecar_path_for_pdf(path, out_dir)
    out_path.write_text(
        json.dumps(sidecar, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return out_path


def sidecar_path_for_pdf(pdf_path: str | Path, output_dir: str | Path) -> Path:
    return Path(output_dir) / f"{Path(pdf_path).name}{SIDECAR_SUFFIX}"


def _page_records(page: Any, page_number: int) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for block_index, block in enumerate(_text_blocks(page), start=1):
        text = _block_text(block)
        if not text:
            continue
        element_type = _infer_element_type(text)
        visual_extractions = _table_cells(
            text,
            page_number=page_number,
            table_id=f"table-{page_number}-{block_index}",
        )
        metadata = {
            "parser_backend": PARSER_BACKEND,
            "block_index": block_index,
            "element_id_aliases": _element_id_aliases(element_type, block_index),
            "element_type_aliases": _element_type_aliases(element_type),
        }
        if visual_extractions:
            metadata["visual_extractions"] = visual_extractions
        records.append(
            {
                "page_label": str(page_number),
                "element_id": f"{element_type}-{page_number}-{block_index}",
                "element_id_aliases": _element_id_aliases(element_type, block_index),
                "element_type": element_type,
                "element_type_aliases": _element_type_aliases(element_type),
                "type": element_type,
                "text": text,
                "bbox": _block_bbox(block),
                "metadata": metadata,
            }
        )
    _attach_vertical_table_cells(records, page_number)
    return records


def _table_cells(
    text: str,
    *,
    page_number: int,
    table_id: str,
) -> list[dict[str, Any]]:
    rows = [_split_table_row(line) for line in str(text).splitlines() if line.strip()]
    if len(rows) < 2 or len(rows[0]) < 2:
        return []
    headers = rows[0]
    cells: list[dict[str, Any]] = []
    for row_index, row in enumerate(rows[1:], start=1):
        value_count = min(len(headers) - 1, len(row) - 1)
        if value_count <= 0:
            continue
        values = row[-value_count:]
        row_label = " ".join(row[: len(row) - value_count]).strip()
        if not row_label:
            continue
        for column_index, value in enumerate(values, start=1):
            if not _is_numeric_cell(value):
                continue
            column_label = headers[column_index].strip()
            cells.append(
                {
                    "cell_id": f"{table_id}:cell:{row_index}:{column_index}",
                    "element_id": table_id,
                    "table_id": table_id,
                    "row_index": row_index,
                    "column_index": column_index,
                    "row_label": row_label,
                    "column_label": column_label,
                    "period": column_label,
                    "period_kind": "fiscal_year"
                    if _looks_like_year(column_label)
                    else "",
                    "cell_role": "data",
                    "value": value,
                    "text": f"{row_label} {column_label} {value}",
                    "modality": "table",
                    "evidence_level": "cell",
                    "extraction_source": PARSER_BACKEND,
                }
            )
    return cells


def _attach_vertical_table_cells(
    records: list[dict[str, Any]],
    page_number: int,
) -> None:
    period_groups = [
        (index, record, periods)
        for index, record in enumerate(records)
        if (periods := _vertical_periods(str(record.get("text") or "")))
    ]
    for group_number, (header_index, header, periods) in enumerate(
        period_groups, start=1
    ):
        next_header_index = next(
            (
                candidate_index
                for candidate_index, _candidate, _candidate_periods in period_groups
                if candidate_index > header_index
            ),
            len(records),
        )
        for row_index, row in enumerate(records):
            if not _vertical_row_in_region(
                header,
                row,
                header_index=header_index,
                row_index=row_index,
                next_header_index=next_header_index,
            ):
                continue
            values, row_label, unit = _vertical_numeric_row(str(row.get("text") or ""))
            if len(values) != len(periods) or not row_label:
                continue
            table_id = f"vertical-table-{page_number}-{group_number}-{row_index + 1}"
            metadata = dict(row.get("metadata") or {})
            existing = list(metadata.get("visual_extractions") or [])
            existing.extend(
                _vertical_cell_records(
                    table_id,
                    periods,
                    values,
                    row_label,
                    unit,
                )
            )
            metadata["visual_extractions"] = existing
            row["metadata"] = metadata


def _vertical_row_in_region(
    header: dict[str, Any],
    row: dict[str, Any],
    *,
    header_index: int,
    row_index: int,
    next_header_index: int,
) -> bool:
    if row_index <= header_index or row_index >= next_header_index:
        return False
    header_bbox = header.get("bbox")
    row_bbox = row.get("bbox")
    if not isinstance(header_bbox, list) or not isinstance(row_bbox, list):
        return True
    if len(header_bbox) != 4 or len(row_bbox) != 4:
        return True
    if row_bbox[1] < header_bbox[3]:
        return False
    return min(header_bbox[2], row_bbox[2]) > max(header_bbox[0], row_bbox[0])


def _vertical_periods(text: str) -> list[str]:
    periods: list[str] = []
    for line in str(text or "").splitlines():
        match = re.fullmatch(r"((?:FY\s*)?(?:19|20)\d{2})(?:/\d+)?", line.strip(), re.I)
        if match:
            periods.append(match.group(1).replace(" ", ""))
    return periods


def _vertical_numeric_row(text: str) -> tuple[list[str], str, str]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    values = [line.replace(",", "") for line in lines if _is_numeric_cell(line)]
    if not values:
        return [], "", ""
    labels = [line for line in lines if not _is_numeric_cell(line)]
    unit = next(
        (
            line.strip("() ")
            for line in labels
            if line.startswith("(") and line.endswith(")")
        ),
        "",
    )
    row_label = next((line for line in labels if line != f"({unit})"), "")
    return values, row_label, unit


def _vertical_cell_records(
    table_id: str,
    periods: list[str],
    values: list[str],
    row_label: str,
    unit: str,
) -> list[dict[str, Any]]:
    return [
        {
            "cell_id": f"{table_id}:cell:1:{index}",
            "element_id": table_id,
            "table_id": table_id,
            "row_index": 1,
            "column_index": index,
            "row_label": row_label,
            "column_label": period,
            "period": period,
            "period_kind": "fiscal_year",
            "cell_role": "data",
            "value": value,
            "unit": unit,
            "text": f"{row_label} {period} {value} {unit}".strip(),
            "modality": "table",
            "evidence_level": "cell",
            "extraction_source": PARSER_BACKEND,
        }
        for index, (period, value) in enumerate(zip(periods, values), start=1)
    ]


def _split_table_row(line: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\t+|\s{2,}", line.strip())]
    parts = [part for part in parts if part]
    return parts or str(line).split()


def _is_numeric_cell(value: str) -> bool:
    return bool(re.fullmatch(r"[$(+-]?\d[\d,]*(?:\.\d+)?%?\)?", str(value).strip()))


def _looks_like_year(value: str) -> bool:
    return bool(re.fullmatch(r"(?:FY\s*)?(?:19|20)\d{2}", str(value).strip(), re.I))


def _text_blocks(page: Any) -> Iterable[Any]:
    return page.get_text("blocks", sort=True) or []


def _block_text(block: Any) -> str:
    if isinstance(block, dict):
        raw_text = block.get("text", "")
    elif isinstance(block, (list, tuple)) and len(block) >= 5:
        raw_text = block[4]
    else:
        raw_text = ""
    lines = [line.strip() for line in str(raw_text or "").splitlines()]
    return "\n".join(line for line in lines if line)


def _block_bbox(block: Any) -> list[float] | None:
    if isinstance(block, dict):
        bbox = block.get("bbox")
    elif isinstance(block, (list, tuple)) and len(block) >= 4:
        bbox = block[:4]
    else:
        bbox = None
    if not isinstance(bbox, (list, tuple)) or len(bbox) != 4:
        return None
    return [float(value) for value in bbox]


def _infer_element_type(text: str) -> str:
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    numeric_tokens = re.findall(r"[$(]?\d[\d,]*(?:\.\d+)?%?\)?", text)
    if len(lines) >= 2 and len(numeric_tokens) >= 4:
        return "table"
    return "text"


def _element_id_aliases(element_type: str, block_index: int) -> list[str]:
    aliases = [f"{element_type}{block_index}", f"text{block_index}"]
    aliases.append(f"image{block_index}")
    return _unique(aliases)


def _element_type_aliases(element_type: str) -> list[str]:
    aliases = [element_type]
    if element_type in {"table", "text"}:
        aliases.extend(["figure", "image"])
    return _unique(aliases)


def _unique(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output


def _import_fitz() -> Any:
    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is required to build PDF OCR/layout sidecars."
        ) from exc
    return fitz


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build non-gold OCR/layout sidecars from PDF text blocks.",
    )
    parser.add_argument("pdfs", nargs="+", help="PDF files to process.")
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Directory where .mara-elements.json sidecars will be written.",
    )
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    for raw_pdf in args.pdfs:
        path = Path(raw_pdf)
        written = write_pdf_ocr_layout_sidecar(
            path,
            output_dir,
            document_id=path.stem,
        )
        print(written)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
